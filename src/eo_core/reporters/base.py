from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np
from rasterio.windows import Window

class BaseReporter(ABC):
    """
    Abstract base class for Output Reporters.
    Reporters handle the writing of inference results to various formats (GeoTIFF, PNG, JSON, etc.).
    """

    @staticmethod
    def get_memory_multiplier(config: Dict[str, Any], context: Dict[str, Any]) -> float:
        """
        Calculates the memory usage multiplier for this reporter.
        
        Args:
            config: The configuration dictionary for this specific reporter instance.
            context: Global context containing 'num_classes', 'num_bands', 'is_segmentation', etc.
            
        Returns:
            float: The memory multiplier. The total memory usage for a chunk of size (H, W) 
                   will be estimated as: (H * W * multiplier).
                   The multiplier should effectively represent "Bytes Per Pixel".
        """
        return 0.0

    @abstractmethod
    def on_start(self, context: Dict[str, Any]):
        """
        Called when the writer process starts.
        Use this to initialize file handles, databases, or state.
        
        Args:
            context: A dictionary containing global context:
                - output_path: Path to the output directory.
                - tile_name: Name of the tile being processed.
                - profile: Rasterio profile for the output image.
                - adapter: The model adapter instance.
                - H_full, W_full: Full dimensions of the image.
                - classes: List of class names.
                - config: The full Hydra configuration (optional subsets).
        """
        pass

    @abstractmethod
    def on_chunk(self, data: Dict[str, Any]):
        """
        Called when a chunk of the image has been reconstructed and is ready for writing.
        
        Args:
            data: A dictionary containing chunk data:
                - probs_map: (C, H, W) numpy array of normalized probabilities for this chunk (ZoR).
                - window: rasterio.windows.Window object defining the location of this chunk.
                - valid_probs: (C, H, W) same as probs_map but explicitly cropped/validated if needed.
        """
        pass

    @abstractmethod
    def on_finish(self, context: Dict[str, Any]):
        """
        Called when the inference loop is complete.
        Use this to close files, generate summary reports, or run post-processing scripts (like previews).
        """
        pass
