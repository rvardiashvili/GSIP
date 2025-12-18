import rasterio
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any
from .base import BaseReporter
from ..utils import generate_low_res_preview, NEW_LABELS, LABEL_COLOR_MAP

log = logging.getLogger(__name__)

class PreviewReporter(BaseReporter):
    """
    Reporter that generates a low-resolution PNG preview of the classification map.
    """
    def on_start(self, context: Dict[str, Any]):
        pass # Nothing to setup

    def on_chunk(self, data: Dict[str, Any]):
        pass # We don't process chunks incrementally yet (simplification)

    def on_finish(self, context: Dict[str, Any]):
        output_path = context['output_path']
        tile_name = context['tile_name']
        config = context.get('config', {})
        adapter = context.get('adapter')

        output_cfg = config.get('pipeline', {}).get('output', {})
        save_preview = output_cfg.get('save_preview', True)
        
        if not save_preview:
            return

        downscale = output_cfg.get("preview_downscale_factor", 10)
        class_path = output_path / f"{tile_name}_class.tif"
        
        # Determine labels/colormap
        if adapter and adapter.labels:
            labels = adapter.labels
            color_map = adapter.color_map
        else:
            labels = NEW_LABELS
            color_map = LABEL_COLOR_MAP

        if class_path.exists():
            try:
                log.info(f"Generating preview for {class_path}...")
                with rasterio.open(class_path) as src:
                    # Note: Reading the entire file might be heavy for massive images.
                    # Future optimization: Implement incremental preview generation in on_chunk.
                    generate_low_res_preview(
                        src.read(1), 
                        output_path / "preview.png", 
                        save_preview=save_preview, 
                        downscale_factor=downscale,
                        labels=labels,
                        color_map=color_map
                    )
                log.info(f"Preview generated at {output_path / 'preview.png'}")
            except Exception as e:
                log.error(f"Failed to generate preview: {e}")
        else:
            log.warning(f"Class map file not found at {class_path}. Skipping preview generation.")
