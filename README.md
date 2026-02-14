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

GSIP can be used either as an installed command-line tool or by running the scripts directly from the source.

### Option 1: Installed Tool (Recommended)
This installs GSIP as a global or user-level command (`gsip`).

```bash
# Using pipx (isolated environment)
pipx install .

# Or using standard pip
pip install .

# Usage:
gsip infer model=resnet_s2 input_path=...
gsip studio
```

### Option 2: Local / Development
Run directly from the repository without a global installation.

```bash
# 1. Install dependencies
pip install -r src/requirements.txt

# 2. Run using the unified CLI script
python src/cli.py infer model=resnet_s2 input_path=...
python src/cli.py studio
```

---

## 🛠️ Unified Command: `gsip`

Whether installed or run via `cli.py`, the entry point provides several sub-commands:

*   **`gsip infer`**: Run inference on a single tile or folder.
*   **`gsip suite`**: Execute a batch run (experiments/benchmarks) defined in JSON.
*   **`gsip studio`**: Launch the GTK4 Analysis Dashboard.
*   **`gsip manage`**: Scaffolding and linking tools for new Adapters/Reporters.


## Key Features

-   **GSIP Studio:** A native GTK4 desktop client with interactive, synchronized resource usage charts (Memory/GPU), automated legend generation, and spatial uncertainty mapping.
-   **Multi-Model Support:** Easily switch between ResNet, ConvNeXt, and Segmentation models via Config Adapters.
-   **Scalable Tiling:** Processes massive images using an artifact-free Overlap-Tile strategy.
-   **Smart Memory Management:** Automatically calculates safe processing chunk sizes based on available RAM.
-   **High-Performance Architecture:** Features a **List-of-Views** memory optimization for zero-copy patch processing.
-   **Advanced Benchmarking:** Automated suite with GPU cooldown management and interactive global performance comparisons.
-   **Uncertainty Quantification:** Outputs Entropy and Confidence maps.