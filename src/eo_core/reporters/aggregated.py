import numpy as np
import logging
from typing import Dict, Any
from .base import BaseReporter

log = logging.getLogger(__name__)

class GlobalProbabilityReporter(BaseReporter):
    """
    Aggregates probability maps into a single global probability vector for the entire tile.
    This effectively performs Global Average Pooling over the entire reconstructed map.
    The result is saved as a .npy file (and optionally .json).
    """
    def __init__(self):
        self.sum_probs = None # Will be (C,)
        self.total_pixels = 0
        self.output_path = None

    def on_start(self, context: Dict[str, Any]):
        output_path = context['output_path']
        tile_name = context['tile_name']
        adapter = context.get('adapter')
        
        self.output_path = output_path / f"{tile_name}_global_probs.npy"
        
        num_classes = adapter.num_classes if adapter else 1
        self.sum_probs = np.zeros(num_classes, dtype=np.float64) # High precision for accumulation
        log.info(f"GlobalProbabilityReporter started. Target: {self.output_path}")

    def on_chunk(self, data: Dict[str, Any]):
        valid_probs = data['valid_probs'] # (C, H_zor, W_zor)
        
        # valid_probs contains the reconstructed probabilities for this Zone of Responsibility.
        # Since ZoRs are non-overlapping (mostly, except potential halo confusion which ZoR solves),
        # we can sum them up to get the global integral.
        
        # Sum over spatial dimensions (H, W) -> (C,)
        chunk_sum = np.sum(valid_probs, axis=(1, 2))
        chunk_pixels = valid_probs.shape[1] * valid_probs.shape[2]
        
        self.sum_probs += chunk_sum
        self.total_pixels += chunk_pixels
        # log.debug(f"GlobalProb chunk processed. Pixels: {chunk_pixels}")

    def on_finish(self, context: Dict[str, Any]):
        if self.total_pixels > 0:
            avg_probs = (self.sum_probs / self.total_pixels).astype(np.float32)
            
            try:
                np.save(self.output_path, avg_probs)
                
                # Also save as simple JSON for easy inspection
                import json
                json_path = self.output_path.with_suffix('.json')
                with open(json_path, 'w') as f:
                    # Convert to list for JSON serialization
                    json.dump({"global_probs": avg_probs.tolist()}, f, indent=2)
                    
                log.info(f"Saved Global Probabilities to {self.output_path}")
            except Exception as e:
                log.error(f"Failed to save Global Probabilities: {e}")
        else:
            log.warning("GlobalProbabilityReporter: No pixels processed.")
