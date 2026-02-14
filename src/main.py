import hydra
from omegaconf import DictConfig, OmegaConf
import os
import sys
import logging
from pathlib import Path

# Set PyTorch Memory Config to reduce fragmentation
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Robustly find config path
# 1. Dev Mode: src/main.py -> ../configs
# 2. Installed: site-packages/src/main.py -> ../configs (sibling package)
current_dir = Path(__file__).resolve().parent
CONFIG_PATH = str(current_dir.parent / "configs")

# Ensure eo_core is importable if running from source
if (current_dir / "eo_core").exists():
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))

from eo_core.process import main_hydra


@hydra.main(version_base=None, config_path=CONFIG_PATH, config_name="config")
def main(cfg: DictConfig):
    main_hydra(cfg)


if __name__ == "__main__":
    main()
