import torch
import torch.nn as nn
from typing import Any, Tuple

class MetadataPassingWrapper(nn.Module):
    """
    Wraps a model to pass metadata through the forward pass and handle batching/normalization
    to avoid OOM and handle non-tensor inputs (numpy arrays) from the engine.
    """
    def __init__(self, model: nn.Module, batch_size: int, norm_m: torch.Tensor, norm_s: torch.Tensor, device: torch.device, activation: str = None):
        super().__init__()
        self.model = model
        self.batch_size = batch_size
        self.norm_m = norm_m
        self.norm_s = norm_s
        self.device_target = device
        self.activation = activation

    def forward(self, input_package: Tuple[Any, Any]) -> Tuple[torch.Tensor, Any]:
        patches_list, metadata = input_package
        
        # patches_list is a List of (C, H, W) numpy views
        results = []
        n = len(patches_list)
        
        # Ensure norms are on device
        norm_m = self.norm_m.to(self.device_target)
        norm_s = self.norm_s.to(self.device_target)
        
        # Import numpy here (or ensure it's imported at top)
        import numpy as np

        # Iterate in batches
        for i in range(0, n, self.batch_size):
            # Slice the list (cheap)
            batch_list = patches_list[i:i+self.batch_size]
            
            # Stack into contiguous array just for this batch (Efficiency Fix!)
            batch_np = np.stack(batch_list, axis=0)
            
            batch = torch.from_numpy(batch_np).float().to(self.device_target)
            
            # Normalize
            batch = (batch - norm_m) / (norm_s + 1e-6)
            
            # Inference
            output = self.model(batch)
            
            # Apply activation on GPU if requested
            if self.activation == 'sigmoid':
                output = torch.sigmoid(output)
            elif self.activation == 'softmax':
                output = torch.softmax(output, dim=1)
                
            results.append(output.detach().cpu()) # Move back to CPU to save GPU memory
            
        if results:
            final_output = torch.cat(results, dim=0)
        else:
            # Handle empty case
            num_classes = getattr(self.model.config, 'classes', getattr(self.model.config, 'num_labels', 0))
            final_output = torch.empty((0, num_classes))

        return final_output, metadata
