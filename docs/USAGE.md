# Usage Guide

This guide explains how to run the GeoSpatial Inference Pipeline (GSIP) using the unified command system.

## 🛠️ Invocation Methods

You can interact with GSIP in two ways depending on how you installed it:

### 1. As an Installed Command
If you installed via `pipx install .` or `pip install .`, use the **`gsip`** command:
```bash
gsip [subcommand] [arguments]
```

### 2. As a Local Script
If you are running directly from the source code, use **`python src/cli.py`**:
```bash
python src/cli.py [subcommand] [arguments]
```

*Note: In the examples below, we use `gsip` for brevity, but you can always substitute it with `python src/cli.py`.*

## Quick Reference

| Command | Description |
| :--- | :--- |
| `gsip infer` | Run the main inference pipeline on a single tile/image. |
| `gsip suite` | Execute a batch of runs (experiments/benchmarks) defined in a JSON file. |
| `gsip studio` | Launch the desktop GUI for analysis and visualization. |
| `gsip manage` | Manage adapters, reporters, and configurations. |

---

## 1. Running Inference (`gsip infer`)

The core command to process data is `gsip infer`.

```bash
gsip infer model=<model_config> input_path=<path_to_data> output_path=<path_to_output>
```

### Understanding `input_path`
The system automatically handles different data structures:

1.  **Single Image:** Point to a `.SAFE` directory (e.g., `S2B_MSIL2A_...SAFE`).
2.  **Time Series:** Point to a folder *containing multiple* `.SAFE` directories. The system will load them as a sequence if the model supports it.

### Examples

**ResNet-50 (Sentinel-2 Only):**
```bash
gsip infer model=resnet_s2 input_path=/path/to/S2_tile output_path=./results
```

**ResNet-50 (Sentinel-1 & Sentinel-2):**
Requires matching Sentinel-1 data.
```bash
gsip infer model=resnet_all input_path=/path/to/S2_tile output_path=./results
```

**Prithvi-100M Flood Segmentation:**
```bash
gsip infer model=prithvi_segmentation input_path=/path/to/S2_tile output_path=./results
```

---

## 2. Batch Execution Suite (`gsip suite`)

To run multiple experiments back-to-back (e.g., for benchmarking or large-scale processing), use `gsip suite`.

### Configuration Format (`batch_config.json`)

The batch configuration is highly flexible, supporting simple runs, complex matrices (Cartesian products), and hierarchical overrides.

```json
{
  "output_dir": "out/batch_runs",
  "global_overrides": ["+pipeline.output.save_preview=true"],
  "runs": [
    {
      "name": "resnet_s2",
      "input_path": "/path/to/tile1.SAFE"
    },
    {
      "models": [
        "resnet_s2",
        {
          "name": "convnext_s2",
          "label": "Experimental",
          "config_overrides": ["+special_param=1"]
        }
      ],
      "input_path": ["/path/to/tile2.SAFE", "/path/to/tile3.SAFE"],
      "config_overrides": ["+pipeline.tiling.max_memory_gb=16"]
    }
  ]
}
```

#### Key Concepts

1.  **Global Overrides:** Applied to *every* job in the suite.
2.  **Run Groups:** The `runs` list contains groups. Each group generates jobs based on the combination of its models and inputs.
3.  **Cartesian Product:** If you provide a list of 2 models and 3 inputs, the system generates **6 jobs** (Model A on Input 1, Model A on Input 2, ..., Model B on Input 3).
4.  **Overrides Hierarchy:** Configuration is merged in this order (later overrides overwrite earlier ones):
    1.  `global_overrides` (Root)
    2.  `config_overrides` (Run Group Shared)
    3.  `overrides` dictionary (Mapped by Model Name)
    4.  `config_overrides` inside a Model Object (Specific)

#### Fields Reference

*   `models` (or `name`): A single string, a list of strings, or a list of objects.
    *   Object format: `{ "name": "...", "label": "...", "config_overrides": [...] }`
*   `input_path`: A single path string or a list of path strings.
*   `label`: Optional. If a list, it maps 1:1 to the models list.
*   `overrides`: A dictionary mapping model names to specific override lists (e.g., `{ "resnet_s2": ["+foo=bar"] }`).

### Running the Suite
```bash
# Run using default 'batch_config.json'
gsip suite

# Run using a custom config
gsip suite --config my_experiments.json
```

### Exporting Results
You can package your results into a ZIP archive directly from the CLI.

*   **Partial Export (Default):** Excludes large TIFF files to save space (useful for sharing analysis data).
    ```bash
    gsip suite --export-partial results.zip out/batch_runs
    ```
*   **Full Export:** Includes everything (TIFFs, logs, JSONs).
    ```bash
    gsip suite --export-full full_backup.zip out/batch_runs
    ```

---

## 3. GSIP Studio (`gsip studio`)

GSIP Studio is a native desktop application for visualizing results and performance metrics.

```bash
gsip studio
```

### Features
*   **Performance Monitoring:** Interactive charts for Memory (RAM) and GPU usage.
*   **Spatial Analysis:** View classification maps, confidence, and entropy side-by-side.
*   **Config Editor:** Edit YAML configurations with a built-in "Refresh" feature.
*   **Global Comparison:** Compare peak memory and duration across all your runs.

---

## 4. Management Tools (`gsip manage`)

Use this to quickly extend the pipeline with new models or output formats.

```bash
# List all installed components
gsip manage list

# Create a new adapter template
gsip manage create-adapter my_new_model --class-name MyModel

# Link an existing script
gsip manage add-adapter path/to/my_script.py
```

See [EXTENDING.md](EXTENDING.md) for detailed development guides.

---

## Advanced Configuration: Reporters

You can enable/disable output formats (Reporters) on the fly using Hydra syntax with `gsip infer`.

**Disable a Reporter (e.g., Preview):**
```bash
gsip infer model=resnet_s2 ... ~pipeline.reporters.preview
```

**Add a Custom Reporter:**
```bash
gsip infer model=resnet_s2 ... \
  +pipeline.reporters.my_stats._target_=my_custom_package.StatisticsReporter
```
