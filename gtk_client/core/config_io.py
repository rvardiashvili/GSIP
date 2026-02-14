import json
import yaml
from pathlib import Path
import os
import sys

def get_project_root() -> Path:
    """
    Robustly finds the project root directory.
    Assumes this file is at: [root]/gtk_client/core/config_io.py
    """
    # Start from this file's location
    current_file = Path(__file__).resolve()
    
    # Go up 3 levels: core -> gtk_client -> [root]
    candidate_root = current_file.parent.parent.parent
    
    # Verify by checking for specific files
    if (candidate_root / "pyproject.toml").exists() or (candidate_root / "src").exists():
        return candidate_root
    
    # Fallback: Check if we are installed in site-packages? 
    # If so, we might not have a "project root" in the development sense.
    # In that case, we might need to look for user config dirs or system paths.
    # For now, let's assume we are in the source tree or similar structure.
    return candidate_root

PROJECT_ROOT = get_project_root()
CONFIGS_DIR = PROJECT_ROOT / "configs"
MODEL_CONFIGS_DIR = CONFIGS_DIR / "model"

def get_absolute_path(relative_path: str) -> Path:
    """Resolves a path relative to the project root."""
    return PROJECT_ROOT / relative_path

def load_yaml(path):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_yaml(path, data):
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def list_model_configs(base_path=None):
    """Returns a list of model config names (filenames without .yaml)"""
    if base_path is None:
        p = MODEL_CONFIGS_DIR
    else:
        p = Path(base_path)
        
    if not p.exists():
        return []
    return [f.stem for f in p.glob("*.yaml")]

def scan_run_results(results_dir):
    """Recursively finds benchmark_*.json files (renamed to runs)"""
    # If results_dir is relative, make it absolute
    p = Path(results_dir)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
        
    if not p.exists():
        return []
    return list(p.rglob("benchmark_*.json"))

def scan_components():
    """
    Scans the source tree for available Adapters and Reporters.
    Returns:
        dict: {'adapters': [str], 'reporters': [str]}
    """
    components = {'adapters': [], 'reporters': []}
    
    # 1. Scan Adapters
    adapters_dir = PROJECT_ROOT / "src" / "eo_core" / "adapters"
    if adapters_dir.exists():
        for f in adapters_dir.glob("*.py"):
            if f.name == "__init__.py" or f.name == "base.py" or f.name == "wrappers.py":
                continue
            components['adapters'].append(f.stem)
            
    # 2. Scan Reporters
    reporters_dir = PROJECT_ROOT / "src" / "eo_core" / "reporters"
    if reporters_dir.exists():
        for f in reporters_dir.glob("*.py"):
            if f.name == "__init__.py" or f.name == "base.py":
                continue
            components['reporters'].append(f.stem)
            
    components['adapters'].sort()
    components['reporters'].sort()
    return components


