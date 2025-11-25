import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Any, Dict, Tuple, List
from ..adapters.base import BaseAdapter
from ..data import _read_s2_bands_for_chunk, _read_s1_bands_for_chunk, cut_into_patches
from .wrappers import MetadataPassingWrapper
from hydra.utils import instantiate
from omegaconf import OmegaConf

class BigEarthNetAdapter(BaseAdapter):
    def build_model(self) -> nn.Module:
        # Params must contain model configuration and normalization stats
        model_conf = self.params.get('model_config')
        if not model_conf:
            # Fallback: try to construct if path is given? 
            # For now assume full config dictionary is passed in params['model_config']
            raise ValueError("BigEarthNetAdapter requires 'model_config' in params.")

        # Instantiate the core model
        # We need to convert primitive dicts to OmegaConf if necessary, 
        # but hydra.utils.instantiate handles dicts well usually.
        core_model = instantiate(model_conf)
        
        # Get Device (Engine will move this wrapper to device, but we need to know it for batching)
        device_str = self.params.get('device', 'cuda' if torch.cuda.is_available() else 'cpu')
        device = torch.device(device_str)
        
        # Normalization Params
        means = self.params.get('means')
        stds = self.params.get('stds')
        if means is None or stds is None:
            raise ValueError("BigEarthNetAdapter requires 'means' and 'stds' for normalization.")
            
        norm_m = torch.tensor(means, dtype=torch.float32).view(1, len(means), 1, 1)
        norm_s = torch.tensor(stds, dtype=torch.float32).view(1, len(stds), 1, 1)
        
        batch_size = self.params.get('gpu_batch_size', 32)
        
        # Wrap it with activation on GPU
        return MetadataPassingWrapper(core_model, batch_size, norm_m, norm_s, device, activation='sigmoid')

    def preprocess(self, raw_input: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        raw_input: {
            'tile_folder': Path, 
            'r_start': int, 'c_start': int, 
            'w_read': int, 'h_read': int,
            'bands': List[str]
        }
        """
        tile_folder = Path(raw_input['tile_folder'])
        r = raw_input['r_start']
        c = raw_input['c_start']
        w = raw_input['w_read']
        h = raw_input['h_read']
        bands = raw_input['bands']
        
        # --- Logic adapted from process.py / ERFAwareInference.infer_tile_region ---
        
        use_s1 = any(b in ['VV', 'VH'] for b in bands)
        
        # S2 Data
        s2_bands = [b for b in bands if 'B' in b]
        s2_data, s2_crs, s2_transform, s2_size = _read_s2_bands_for_chunk(
            tile_folder, r, c, w, h, pad_if_needed=True, bands_list=s2_bands
        )
        
        # S1 Data
        if use_s1:
            s1_bands = [b for b in bands if b in ['VV', 'VH']]
            s1_data, _, _ = _read_s1_bands_for_chunk(
                tile_folder, r, c, w, h, 
                pad_if_needed=True, 
                bands_list=s1_bands,
                ref_crs=s2_crs,
                ref_transform=s2_transform,
                ref_size=s2_size
            )
            
            if s1_data.size > 0:
                # Clip S1
                s1_data = np.clip(s1_data, -50.0, 30.0) 
            
            # Concatenate S1 FIRST (if that's the convention in config)
            # Check if s1_data is empty (0 shape)
            if s1_data.size == 0:
                 input_data = s2_data
            else:
                 input_data = np.concatenate([s1_data, s2_data], axis=0)
        else:
            input_data = s2_data

        # Cut into patches
        patch_size = self.params.get('patch_size', 120)
        stride = self.params.get('stride', patch_size // 2)
        
        patches, coords, H_crop, W_crop, _ = cut_into_patches(input_data, patch_size, stride=stride)
        
        # patches is (N, C, P, P) numpy array
        # We return it as numpy so InferenceEngine doesn't auto-move it to GPU
        
        metadata = {
            'coords': coords, 
            'H_crop': H_crop, 
            'W_crop': W_crop,
            'original_r': r,
            'original_c': c
        }
        
        return patches, metadata

    def postprocess(self, model_output: Tuple[torch.Tensor, Dict[str, Any]]) -> Dict[str, Any]:
        probs, metadata = model_output
        
        # Sigmoid is now done on GPU in Wrapper
        
        return {
            'probs_tensor': probs, 
            'coords': metadata['coords'],
            'H_crop': metadata['H_crop'],
            'W_crop': metadata['W_crop'],
            'r_chunk': metadata['original_r'],
            'c_chunk': metadata['original_c']
        }

    @property
    def num_classes(self) -> int:
        return self.params.get('num_classes', 19)

    @property
    def num_bands(self) -> int:
        if 'bands' in self.params:
            return len(self.params['bands'])
        elif 'means' in self.params:
            return len(self.params['means'])
        else:
            return 12 # Default S2

    @property
    def patch_size(self) -> int:
        return self.params.get('patch_size', 120)

    @property
    def stride(self) -> int:
        return self.params.get('stride', 60)
