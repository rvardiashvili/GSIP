import json
import yaml
from pathlib import Path

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

def list_model_configs(base_path="configs/model"):
    """Returns a list of model config names (filenames without .yaml)"""
    p = Path(base_path)
    if not p.exists():
        return []
    return [f.stem for f in p.glob("*.yaml")]

def scan_benchmark_results(results_dir):
    """Recursively finds benchmark_*.json files"""
    p = Path(results_dir)
    if not p.exists():
        return []
    return list(p.rglob("benchmark_*.json"))
