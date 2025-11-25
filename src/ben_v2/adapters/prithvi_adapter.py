import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Any, Dict, Tuple, List
from transformers import AutoModelForSemanticSegmentation, AutoConfig
from ..adapters.base import BaseAdapter
from ..adapters.wrappers import MetadataPassingWrapper
from ..data import _read_s2_bands_for_chunk, cut_into_patches

class PrithviAdapter(BaseAdapter):
    def __init__(self, params: Dict[str, Any]):
        super().__init__(params)
        model_name = self.params.get('model_name_or_path', "ibm-nasa-geospatial/Prithvi-100M-sen1floods11")
        self.model_config = AutoConfig.from_pretrained(model_name)

    def build_model(self) -> nn.Module:
        model_name = self.params.get('model_name_or_path', "ibm-nasa-geospatial/Prithvi-100M-sen1floods11")
        
        # Load Model
        # trust_remote_code might be needed for some geospatial models, but Prithvi uses Segformer architecture usually supported.
        model = AutoModelForSemanticSegmentation.from_pretrained(
            model_name, 
            config=self.model_config,
            trust_remote_code=True
        )
        
        # Prithvi expects 6 channels.
        # We need to ensure the input layer matches.
        # AutoModel usually handles this if the checkpoint has 6 channels.
        
        device_str = self.params.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        device = torch.device(device_str)
        
        # Normalization Stats
        # Prithvi sen1floods11 expects input in [0, 1] range (reflectance).
        # It does not typically use ImageNet mean/std.
        # We will pass 0 mean and 1 std for the wrapper to effectively just divide by 1 (if data is already 0-1)
        # OR we can use the wrapper to divide by 10000 if data is raw DN.
        # Our _read_s2_bands_for_chunk usually returns reflectance (0-1) if we implemented it that way?
        # Let's check data.py. If it uses rasterio reading, it might return raw DNs or scaled.
        # Standard S2 is 0-10000.
        # BigEarthNet loader usually converts to Float.
        # Let's assume the data loader returns raw values and we normalize.
        # If _read_s2_bands_for_chunk returns 0-10000, we need to divide by 10000.
        
        # Wrapper handles (batch - mean) / std.
        # To achieve batch / 10000: mean=0, std=10000.
        
        norm_m = torch.zeros((6, 1, 1), dtype=torch.float32)
        norm_s = torch.ones((6, 1, 1), dtype=torch.float32) # * 10000 if input is raw.
        
        batch_size = self.params.get('batch_size', 8)
        
        # Wrap HF model to return logits tensor
        wrapped_model = PrithviOutputWrapper(model)
        
        return MetadataPassingWrapper(wrapped_model, batch_size, norm_m, norm_s, device, activation='softmax')

    def preprocess(self, raw_input: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
        tile_folder = Path(raw_input['tile_folder'])
        r = raw_input['r_start']
        c = raw_input['c_start']
        w = raw_input['w_read']
        h = raw_input['h_read']
        
        # Prithvi Bands: Blue, Green, Red, Narrow NIR (B8A), SWIR 1, SWIR 2
        bands_needed = self.params.get('bands', ['B02', 'B03', 'B04', 'B8A', 'B11', 'B12'])
        
        # Read Data
        # _read_s2_bands_for_chunk returns (C, H, W)
        s2_data, s2_crs, s2_transform, s2_size = _read_s2_bands_for_chunk(
            tile_folder, r, c, w, h, pad_if_needed=True, bands_list=bands_needed
        )
        
        # Check range. If max > 100, likely 0-10000.
        if s2_data.max() > 100:
             s2_data = s2_data.astype(np.float32) / 10000.0
        
        # Cut into patches
        patch_size = self.params.get('patch_size', 224)
        stride = self.params.get('stride', 112)
        
        patches, coords, H_crop, W_crop, _ = cut_into_patches(s2_data, patch_size, stride=stride)
        
        metadata = {
            'coords': coords, 
            'H_crop': H_crop, 
            'W_crop': W_crop,
            'original_r': r,
            'original_c': c,
            'shape': s2_data.shape
        }
        
        return patches, metadata

    def postprocess(self, model_output: Tuple[torch.Tensor, Dict[str, Any]]) -> Dict[str, Any]:
        probs_tensor, metadata = model_output
        
        # Probs are already Softmaxed on GPU
        
        # Upsample if needed to match patch size
        patch_size = self.params.get('patch_size', 224)
        
        if probs_tensor.shape[-1] != patch_size:
             probs_tensor = nn.functional.interpolate(
                 probs_tensor, 
                 size=(patch_size, patch_size), 
                 mode='bilinear', 
                 align_corners=False
             )
        
        return {
            'probs_tensor': probs_tensor,
            'coords': metadata['coords'],
            'H_crop': metadata['H_crop'],
            'W_crop': metadata['W_crop'],
            'r_chunk': metadata['original_r'],
            'c_chunk': metadata['original_c']
        }

    @property
    def num_classes(self) -> int:
        return self.model_config.num_labels

    @property
    def num_bands(self) -> int:
        return len(self.params.get('bands', ['B02', 'B03', 'B04', 'B8A', 'B11', 'B12']))

    @property
    def patch_size(self) -> int:
        return self.params.get('patch_size', 224)

    @property
    def stride(self) -> int:
        return self.params.get('stride', 112)

    @property
    def is_segmentation(self) -> bool:
        return True

class PrithviOutputWrapper(nn.Module):
    """Helper to extract logits from HF model output"""
    def __init__(self, model):
        super().__init__()
        self.model = model
        # We need to access config from the inner model
        if hasattr(model, 'config'):
            self.config = model.config
        
    def forward(self, x):
        output = self.model(x)
        return output.logits
