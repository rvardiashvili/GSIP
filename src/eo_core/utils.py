"""
Utility functions and visualization tools.
"""
from typing import Dict, List, Any, Optional
from pathlib import Path
import numpy as np
import torch
from PIL import Image 
from scipy.ndimage import zoom
import matplotlib.pyplot as plt # Added
import matplotlib.cm as cm # Added 
import matplotlib.colors as colors # Added 
import logging

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# --- Constants & Helpers ---
# ----------------------------------------------------------------------

def get_device(device_id: Optional[int] = None):
    """Returns the best available device."""
    if torch.cuda.is_available():
        if device_id is not None:
            return torch.device(f"cuda:{device_id}")
        return torch.device("cuda")
    return torch.device("cpu")

# ----------------------------------------------------------------------
# Visualization Functions
# ----------------------------------------------------------------------

def generate_low_res_preview(
    mask_data: np.ndarray, 
    output_path: Path, 
    save_preview: bool = True,
    downscale_factor: int = 10,
    labels: Optional[List[str]] = None,
    color_map: Optional[Dict[str, Any]] = None
):
    """
    Generates a low-resolution color PNG preview of the classification mask.
    """
    if not save_preview:
        return

    if downscale_factor > 1:
        downscaled_mask = zoom(mask_data, 1.0 / downscale_factor, order=0)
    else:
        downscaled_mask = mask_data
    
    if labels is None or color_map is None:
        log.warning("Labels or Color Map not provided for preview generation. Using grayscale fallback.")
        # Create a simple grayscale image normalized to 0-255 based on unique values
        norm_mask = ((downscaled_mask - downscaled_mask.min()) / (downscaled_mask.max() - downscaled_mask.min() + 1e-6) * 255).astype(np.uint8)
        try:
            img_pil = Image.fromarray(norm_mask, 'L')
            img_pil.save(output_path, 'PNG')
        except Exception as e:
            log.error(f"Error saving grayscale preview image: {e}")
        return

    # Use provided labels/colormap
    target_labels = labels
    target_color_map = color_map
    
    # Ensure color map keys exist in labels (robustness)
    # Construct array based on index in target_labels
    color_map_array_list = []
    for label in target_labels:
        if label in target_color_map:
             c = target_color_map[label]
             # Handle list vs numpy array
             if isinstance(c, list):
                 c = np.array(c, dtype=np.uint8)
             color_map_array_list.append(c)
        else:
             color_map_array_list.append(np.array([128, 128, 128], dtype=np.uint8)) # Gray fallback
             
    color_map_array = np.array(color_map_array_list, dtype=np.uint8)
    
    max_idx = len(target_labels) - 1
    safe_mask = np.clip(downscaled_mask, 0, max_idx)
    
    rgb_image = color_map_array[safe_mask]
    
    try:
        img_pil = Image.fromarray(rgb_image, 'RGB')
        img_pil.save(output_path, 'PNG')
    except Exception as e:
        log.error(f"Error saving preview image: {e}")

def generate_float_preview(
    data: np.ndarray,
    output_path: Path,
    save_preview: bool = True,
    downscale_factor: int = 10,
    cmap_name: str = 'magma_r', # Default colormap for continuous data
    title: Optional[str] = None, # Not used for image but could be useful for debugging
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    colorbar_path: Optional[Path] = None # New parameter for color bar output
):
    """
    Generates a low-resolution color PNG preview of continuous float data, and optionally a color bar.
    """
    if not save_preview:
        return

    if downscale_factor > 1:
        downscaled_data = zoom(data, 1.0 / downscale_factor, order=1) # order=1 for bilinear interpolation
    else:
        downscaled_data = data
    
    # Normalize data
    if vmin is None:
        vmin = np.min(downscaled_data)
    if vmax is None:
        vmax = np.max(downscaled_data)

    if vmax == vmin: # Handle constant data
        normalized_data = np.zeros_like(downscaled_data)
    else:
        normalized_data = (downscaled_data - vmin) / (vmax - vmin)
    
    # Apply colormap
    cmap = cm.get_cmap(cmap_name)
    rgb_image = cmap(normalized_data)[:, :, :3] # Take RGB channels, discard alpha
    
    # Convert to 8-bit image
    rgb_image = (rgb_image * 255).astype(np.uint8)

    try:
        img_pil = Image.fromarray(rgb_image, 'RGB')
        img_pil.save(output_path, 'PNG')
    except Exception as e:
        log.error(f"Error saving float preview image: {e}")

    # Generate color bar if requested
    if colorbar_path:
        try:
            fig, ax = plt.subplots(figsize=(1.0, 4.0)) # Adjust size as needed
            cmap_obj = cm.get_cmap(cmap_name)
            norm = colors.Normalize(vmin=vmin, vmax=vmax)
            cb = plt.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap_obj), cax=ax, orientation='vertical')
            cb.set_label(title if title else "") # Use title for colorbar label
            
            plt.tight_layout()
            plt.savefig(colorbar_path, bbox_inches='tight', dpi=100)
            plt.close(fig) # Close the figure to free memory
        except Exception as e:
            log.error(f"Error saving color bar image: {e}")
