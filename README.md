# GeoSpatial Inference Pipeline (GSIP)

This project provides a scalable, multi-modal deep learning pipeline for robust and efficient inference on gigapixel-scale Earth Observation (EO) data, focusing on tasks like land cover classification and segmentation.

## 📚 Documentation

Detailed documentation is organized in the `docs/` directory:

| Document | Description |
| :--- | :--- |
| [**Usage Guide**](docs/USAGE.md) | Detailed instructions on how to run models, configure inputs, and interpret outputs. |
| [**Technical Reference**](docs/TECHNICAL_REFERENCE.md) | Deep dive into the **ERF-Aware Tiling**, **Memory Auto-Configuration**, and mathematical formulas. |
| [**API Reference**](docs/API_REFERENCE.md) | Function-level documentation for the codebase (Engine, Adapters, Data Loading). |
| [**Development Guide**](docs/DEVELOPMENT.md) | Instructions for contributors: adding new models, creating adapters, and modifying the core. |
| [**Project Structure**](docs/PROJECT_STRUCTURE.md) | An overview of the file tree and the purpose of each directory. |

## 🚀 Quick Start

### 1. Installation

```bash
pip install -r src/requirements.txt
pip install -e .
```

### 2. Run a Model (CLI)

```bash
python src/main.py model=resnet_s2 input_path=/path/to/tile output_path=./out
```

### 3. GSIP Studio (GUI Analysis)

The project includes a native GTK4 dashboard for deep performance analysis and visualization of benchmark results.

```bash
python gtk_client/main.py
```

## Key Features

-   **GSIP Studio:** A native GTK4 desktop client with interactive, synchronized resource usage charts (Memory/GPU), automated legend generation, and spatial uncertainty mapping.
-   **Multi-Model Support:** Easily switch between ResNet, ConvNeXt, and Segmentation models via Config Adapters.
-   **Scalable Tiling:** Processes massive images using an artifact-free Overlap-Tile strategy.
-   **Smart Memory Management:** Automatically calculates safe processing chunk sizes based on available RAM.
-   **High-Performance Architecture:** Features a **List-of-Views** memory optimization for zero-copy patch processing.
-   **Advanced Benchmarking:** Automated suite with GPU cooldown management and interactive global performance comparisons.
-   **Uncertainty Quantification:** Outputs Entropy and Confidence maps.