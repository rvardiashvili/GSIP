# Extending the Pipeline: Adapters and Reporters

This guide provides a deep dive into the two primary extension points of the Geospatial Inference Pipeline: **Adapters** and **Reporters**.

## 🛠️ Quick Start with CLI Tool

For convenience, we provide a management tool integrated into the unified CLI. You can use it as **`gsip manage`** (if installed) or **`python src/cli.py manage`** (from source).

### 1. Generating Templates (Scaffolding)
Start by generating boilerplate code so you don't have to write everything from scratch.

```bash
# Generate a new Adapter template
gsip manage create-adapter my_new_model --class-name MyNewModel

# Generate a new Reporter template
gsip manage create-reporter my_custom_reporter

# Generate a new Config for your adapter
gsip manage create-config my_model_config --adapter my_new_model --class-name MyNewModel
```

### 2. Registering Existing Files
If you already have a script, you can link it into the pipeline. By default, this creates a **symbolic link** to your source file.

```bash
# Link an existing adapter
gsip manage add-adapter path/to/existing_adapter.py

# Link an existing reporter
gsip manage add-reporter path/to/existing_reporter.py
```

### 3. Managing Components
```bash
# List all installed components (shows symlink targets)
gsip manage list

# Remove a component (unlinks or deletes file)
gsip manage remove adapter my_new_model
gsip manage remove config my_model_config
```


---

- **Adapters** allow you to integrate new model architectures (CNNs, Transformers, etc.) and data preprocessing logic without touching the core engine.
- **Reporters** allow you to customize how inference results are saved (GeoTIFF, JSON, Database, etc.) without modifying the main processing loop.

---

## 1. Adapters

An Adapter acts as a bridge between the pipeline's generic data loading mechanism and your specific model's requirements. It handles three key stages:
1.  **Preprocessing:** Converting raw raster data (numpy arrays) into model-ready tensors.
2.  **Model Building:** Instantiating the PyTorch model architecture.
3.  **Postprocessing:** Converting raw model outputs (logits/embeddings) into standardized results (probabilities/masks).

### The Base Class

All adapters must inherit from `src.eo_core.adapters.base.BaseAdapter`.

```python
from abc import ABC, abstractmethod
from typing import Any, Dict
import torch.nn as nn

class BaseAdapter(ABC):
    def __init__(self, params: Dict[str, Any]):
        self.params = params

    @abstractmethod
    def build_model(self) -> nn.Module:
        """Return the PyTorch model."""
        pass

    @abstractmethod
    def preprocess(self, raw_input: Any) -> Any:
        """Prepare input for the model."""
        pass

    @abstractmethod
    def postprocess(self, model_output: Any) -> Any:
        """Process model output into a standard format."""
        pass
    
    # ... required properties (see below)
```

### Step-by-Step Implementation

#### A. Preprocessing
The pipeline reads a chunk of data (e.g., 2048x2048 pixels) and passes metadata to `preprocess`. Your job is to:
1.  Read the actual pixel data (using helper functions in `src.eo_core.data`).
2.  Slice this large chunk into smaller patches (e.g., 120x120) if your model expects fixed-size inputs.
3.  Normalize and convert to Tensor.

```python
def preprocess(self, raw_input: Dict[str, Any]):
    # raw_input contains: 'tile_folder', 'r_start', 'c_start', etc.
    
    # 1. Read Data
    data, _, _, _ = _read_s2_bands_for_chunk(
        raw_input['tile_folder'], 
        raw_input['r_start'], 
        raw_input['c_start'], 
        ...
    )
    
    # 2. Patchify
    patches = cut_into_patches(data, self.patch_size, self.stride)
    
    # 3. Return
    return patches, {'coords': coords} 
```

#### B. Postprocessing
The pipeline runs inference on the patches returned by `preprocess`. The `postprocess` method receives the raw output.

```python
def postprocess(self, model_output):
    logits, metadata = model_output
    probs = torch.sigmoid(logits) # Convert to probability
    return {
        'probs_tensor': probs,
        'coords': metadata['coords']
        # ... other metadata needed for reconstruction
    }
```

#### C. Configuration
To use your adapter, create a config file in `configs/model/my_model.yaml`:

```yaml
# @package _global_
model:
  name: "My Custom Model"
  adapter:
    # Python path to your class
    path: "src.eo_core.adapters.my_adapter.MyAdapter" 
    params:
      # These are passed to __init__
      num_classes: 10
      patch_size: 256
      bands: ["B04", "B03", "B02"]
```

---

## 2. Reporters

Reporters handle the input/output (I/O) of the inference results. The pipeline produces a stream of processed chunks (probability maps), and the Reporter decides where they go.

### The Base Class

All reporters must inherit from `src.eo_core.reporters.base.BaseReporter`.

```python
class BaseReporter(ABC):
    @abstractmethod
    def on_start(self, context: Dict[str, Any]):
        """Initialize files/databases."""
        pass

    @abstractmethod
    def on_chunk(self, data: Dict[str, Any]):
        """Write a processed chunk."""
        pass

    @abstractmethod
    def on_finish(self, context: Dict[str, Any]):
        """Cleanup."""
        pass
```

### Step-by-Step Implementation

#### A. Initialization (`on_start`)
Use this to open file handles (e.g., `rasterio.open`) or connect to databases.
`context` provides global info like `output_path`, `tile_name`, `profile` (CRS/Transform), and the `adapter` instance.

```python
def on_start(self, context):
    self.dst = rasterio.open(
        context['output_path'] / "result.tif", 
        'w', 
        **context['profile']
    )
```

#### B. Writing (`on_chunk`)
Called whenever the pipeline finishes reconstructing a large chunk (e.g., 2048x2048).
`data` contains:
- `probs_map`: The full probability map for the chunk.
- `window`: The `rasterio.window` determining where this chunk fits in the full image.
- `valid_probs`: The probabilities cropped to valid areas (handling overlaps).

```python
def on_chunk(self, data):
    # Write the valid data to the file at the correct window
    self.dst.write(data['valid_probs'], window=data['window'])
```

#### C. Memory Management (`get_memory_multiplier`)
This static method is CRITICAL for stability. It tells the pipeline how much memory your reporter needs per pixel.
If you save a float32 probability map, that's 4 bytes per pixel. If you save 10 classes, that's 40 bytes.

```python
@staticmethod
def get_memory_multiplier(config, context):
    # Example: Saving 10 classes as float32
    num_classes = context.get('num_classes', 10)
    return num_classes * 4.0 
```

### Configuration
To use a custom reporter, you typically reference it in the main pipeline config or instantiate it dynamically if the logic supports it. Currently, the pipeline defaults to `GeoTIFFReporter`, but you can swap this in `src/eo_core/process.py` or extend the configuration system to load reporters dynamically similar to adapters.

---

## 3. Best Practices

1.  **Keep Adapters Stateless:** Ideally, adapters shouldn't hold massive state between `preprocess` and `postprocess` calls other than what is passed in metadata. The pipeline might run these in parallel or distributed settings in the future.
2.  **Reporter Efficiency:** File I/O is the bottleneck. In `on_chunk`, write data immediately. Avoid accumulating the whole image in memory unless absolutely necessary (which defeats the purpose of chunking).
3.  **Memory Multipliers:** Be conservative. If you underestimate memory usage, the pipeline might crash with OOM (Out Of Memory) errors on large satellite tiles.
4.  **Logging:** Use `logging.getLogger(__name__)` to provide helpful debug info, especially in `build_model` and `on_start`.

