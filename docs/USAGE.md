# Usage Guide

This guide explains how to run the GeoSpatial Inference Pipeline (GSIP) using the available model configurations.

## Basic Command Structure

The general command to run the pipeline is:

```bash
python src/main.py model=<model_config_name> input_path=<path_to_data> output_path=<path_to_output_dir>
```

### Understanding `input_path`
The `input_path` parameter is versatile and handles different data structures automatically based on the content and the model's requirements:

1.  **Single Image (S2 Only or S1+S2):** Point to a `.SAFE` directory (e.g., `S2B_MSIL2A_...SAFE`) OR a directory containing exactly one S2 `.SAFE` product (and optionally an S1 product).
    *   *System Logic:* The system counts the number of S2 products (`S2*.SAFE`) in the folder. If count is 1, it treats it as a single time-step. If an S1 product is required (e.g., for `resnet_all`), the adapter looks for it in the same folder or relative to the S2 product.

2.  **Multi-Temporal Series:** Point to a folder *containing multiple* S2 `.SAFE` directories.
    *   *System Logic:* If multiple S2 products are found AND the selected model (e.g., `prithvi`) requires multiple frames (`num_frames > 1`), the system automatically loads them as a time series.

## Available Models

### 1. ResNet-50 (Sentinel-2 Only)
**Config:** `resnet_s2`
**Description:** Standard classification model using 10 Sentinel-2 bands.
**Usage:**
```bash
python src/main.py model=resnet_s2 input_path=/path/to/S2_tile output_path=./results
```

### 2. ResNet-50 (Sentinel-1 & Sentinel-2)
**Config:** `resnet_all`
**Description:** Multi-modal classification using 12 bands (2 S1 + 10 S2). **Requires matching Sentinel-1 data** to be present or configured in the data loader.
**Usage:**
```bash
python src/main.py model=resnet_all input_path=/path/to/S2_tile output_path=./results
```

### 3. ConvNeXt V2 (Sentinel-2)
**Config:** `convnext_s2`
**Description:** Modern ConvNeXt architecture for classification (10 bands).
**Usage:**
```bash
python src/main.py model=convnext_s2 input_path=/path/to/S2_tile output_path=./results
```

### 4. Prithvi-100M Flood Segmentation
**Config:** `prithvi_segmentation`
**Description:** A geospatial foundation model fine-tuned for flood segmentation.
**Note:** This model outputs a segmentation map. The current pipeline will save the raw outputs, but the visualization (Class Map) might need interpretation as "Background" vs "Flood".
**Usage:**
```bash
python src/main.py model=prithvi_segmentation input_path=/path/to/S2_tile output_path=./results
```

## Benchmarking Mode

To run a comprehensive performance benchmark suite across multiple models and configurations, use the `src/benchmark_suite.py` script.

### Using a Configuration File

The benchmark suite is controlled by a JSON configuration file. By default, it looks for `benchmark_config.json` in the root directory.

```bash
python src/benchmark_suite.py
```

To specify a custom configuration file:

```bash
python src/benchmark_suite.py --config my_custom_benchmarks.json
```

### Configuration Format

The JSON file should follow this structure:

```json
{
  "output_dir": "out/benchmarks_final",
  "benchmarks": [
    {
      "name": "resnet_s2",
      "input_path": "/path/to/S2_tile.SAFE",
      "label": "resnet_s2_baseline",
      "config_overrides": [
        "+pipeline.tiling.max_memory_gb=16"
      ]
    },
    {
      "name": "convnext_s2",
      "input_path": "/path/to/S2_tile.SAFE"
    }
  ]
}
```

*   `output_dir`: Where the results for all runs will be stored.
*   `benchmarks`: A list of run configurations.
    *   `name`: The model configuration name (must match a file in `configs/model/`, e.g., `resnet_s2`).
    *   `input_path`: Path to the input tile or folder.
    *   `label` (Optional): A custom name for this run folder.
    *   `config_overrides` (Optional): A list of Hydra override strings (e.g., changing memory limits or patch sizes).

This script orchestrates back-to-back runs, manages GPU cooldowns to ensure fair comparisons, and generates a consolidated report folder containing performance metrics and artifacts from all runs.

## Advanced Configuration: Reporters

GSIP uses a "Reporter" system to generate outputs. You can enable, disable, or add new output formats directly from the command line.

**Disable a Reporter (e.g., Preview):**
Use the `~` prefix to remove a key.
```bash
python src/main.py model=resnet_s2 ... ~pipeline.reporters.preview
```

**Add a Custom Reporter:**
You can inject a new reporter configuration using the `+` prefix.
```bash
python src/main.py model=resnet_s2 ... \
  +pipeline.reporters.my_stats._target_=my_custom_package.StatisticsReporter
```

**Enable Optional Probability Cubes:**
The `ProbabilityReporter` is available but disabled by default in some configs to save space. To enable it:
```bash
python src/main.py model=resnet_s2 ... \
  +pipeline.reporters.probs._target_=eo_core.reporters.probability.ProbabilityReporter
```

## Understanding Outputs

Check the `out/` directory for results:
*   `*_class.tif`: The final class/segmentation map.
*   `*_maxprob.tif`: Confidence map.
*   `*_entropy.tif`: Uncertainty map (Shannon Entropy).
*   `*_global_probs.npy`: Single 1D array of average class probabilities for the *entire* tile.
*   `preview.png`: A quick look RGB image of the classification.
*   `viewer.html`: An interactive web-based viewer for the result.
