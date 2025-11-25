# Project Structure

This document outlines the directory layout and purpose of key files in the **BigEarthNet v2.0 Scalable Analysis Pipeline**.

```
/home/rati/bsc_thesis/BigEarthNetv2.0/main/
├── configs/                  # Hydra configuration files
│   ├── config.yaml           # Main entry point for configuration
│   ├── data_source/          # Data source settings (Sentinel-2, etc.)
│   ├── model/                # Model architectures and adapters
│   │   ├── resnet_s2.yaml    # Config for ResNet50 (S2 only)
│   │   ├── resnet_all.yaml   # Config for ResNet50 (S1 + S2)
│   │   ├── convnext_s2.yaml  # Config for ConvNeXt (S2 only)
│   │   ├── prithvi_segmentation.yaml # Config for Prithvi Flood Segmentation
│   │   └── ...
│   └── pipeline/             # Inference pipeline parameters (tiling, batching)
│       └── inference_params.yaml
│
├── src/
│   ├── main.py               # CLI Entry Point
│   ├── requirements.txt      # Python dependencies
│   ├── ben_v2/               # Core Package Code
│   │   ├── adapters/         # Model Adapters (Pattern: Adapter Design)
│   │   │   ├── base.py                # Abstract Base Class for all adapters
│   │   │   ├── bigearthnet_adapter.py # Adapter for BigEarthNet classification models
│   │   │   ├── prithvi_adapter.py     # Adapter for Prithvi segmentation models
│   │   │   └── wrappers.py            # PyTorch Module Wrappers (Batching/Norm)
│   │   │
│   │   ├── inference_engine.py   # Generic Inference Engine (loads adapters)
│   │   ├── process.py            # Main Tiling Pipeline & Writer Process
│   │   ├── data.py               # I/O Logic (Reading Sentinel-1/2 GeoTIFFs)
│   │   ├── model.py              # Model Definitions (ConfigILM wrappers)
│   │   ├── utils.py              # Utilities (Visualization, Placeholders)
│   │   ├── fusion.py             # S1/S2 Registration & Fusion logic
│   │   ├── generate_viewer.py    # HTML Viewer Generator
│   │   ├── benchmark.py          # Benchmarking Logic
│   │   └── download_sentinel.py  # Sentinel-1/2 Downloader Script
│
├── out/                      # Default Output Directory
├── docs/                     # Documentation Directory
│   ├── TECHNICAL_REFERENCE.md # Technical Reference Manual
│   ├── PROJECT_STRUCTURE.md  # This File
│   ├── API_REFERENCE.md      # Detailed Function Documentation
│   ├── USAGE.md              # Usage Guide
│   └── DEVELOPMENT.md        # Developer Guide
└── README.md                 # Project Overview
```

## Key Directories

*   **`configs/`**: Controls every aspect of the pipeline without changing code. Models, batch sizes, and file paths are defined here.
*   **`docs/`**: Contains all detailed documentation for the project.
*   **`src/ben_v2/adapters/`**: The "plug-and-play" layer. If you want to add a new model type (e.g., a YOLO detector or a specific segmentation net), you write a new Adapter here without touching the core pipeline logic.
*   **`src/ben_v2/`**: Contains the heavy lifting logic. `process.py` is the orchestrator, managing the multiprocessing and tiling logic described in `docs/TECHNICAL_REFERENCE.md`.
