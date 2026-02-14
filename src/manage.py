#!/usr/bin/env python3
import argparse
import shutil
import os
import sys
from pathlib import Path
import re
import textwrap

# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
ADAPTERS_DIR = SRC_DIR / "eo_core" / "adapters"
REPORTERS_DIR = SRC_DIR / "eo_core" / "reporters"
CONFIGS_DIR = PROJECT_ROOT / "configs" / "model"

# Templates
ADAPTER_TEMPLATE = """from typing import Any, Dict, List, Tuple
import torch.nn as nn
import numpy as np
from .base import BaseAdapter

class {class_name}(BaseAdapter):
    \"\"\"
    Auto-generated adapter for {class_name}.
    \"\"\"
    
    def build_model(self) -> nn.Module:
        # TODO: Initialize your PyTorch model here
        raise NotImplementedError("Model building not implemented")

    def preprocess(self, raw_input: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        # TODO: Implement data reading and preprocessing
        # raw_input contains 'tile_folder', 'r_start', 'c_start', etc.
        raise NotImplementedError("Preprocessing not implemented")

    def postprocess(self, model_output: Any) -> Dict[str, Any]:
        # TODO: Convert model output to standardized format
        raise NotImplementedError("Postprocessing not implemented")

    @property
    def num_classes(self) -> int:
        return self.params.get('num_classes', 2)

    @property
    def num_bands(self) -> int:
        return self.params.get('num_bands', 12)

    @property
    def patch_size(self) -> int:
        return self.params.get('patch_size', 120)

    @property
    def stride(self) -> int:
        return self.params.get('stride', 60)
"""

REPORTER_TEMPLATE = """from typing import Dict, Any
import logging
from .base import BaseReporter

log = logging.getLogger(__name__)

class {class_name}(BaseReporter):
    \"\"\"
    Auto-generated reporter for {class_name}.
    \"\"\"

    def on_start(self, context: Dict[str, Any]):
        # TODO: Initialize output files or connections
        # context has 'output_path', 'tile_name', 'profile', etc.
        log.info(f"Starting reporting for {{context['tile_name']}}")

    def on_chunk(self, data: Dict[str, Any]):
        # TODO: Write chunk data
        # data has 'probs_map', 'window', 'valid_probs'
        pass

    def on_finish(self, context: Dict[str, Any]):
        # TODO: Cleanup
        log.info("Finished reporting")
"""

CONFIG_TEMPLATE = """# @package _global_
model:
  name: "{name}"
  adapter:
    path: "eo_core.adapters.{module_name}.{class_name}"
    params:
      num_classes: 2
      patch_size: 120
      bands: ["B04", "B03", "B02"]
"""

def setup_parser():
    parser = argparse.ArgumentParser(
        description="GSIP Management Tool: Manage adapters, reporters, and configs.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- Add Existing ---
    
    # Command: add-adapter
    p_add_adapter = subparsers.add_parser("add-adapter", help="Link/Copy an existing python file as an Adapter")
    p_add_adapter.add_argument("source", type=str, help="Path to the source python file")
    p_add_adapter.add_argument("--name", type=str, help="Rename destination file", default=None)
    p_add_adapter.add_argument("--copy", action="store_true", help="Copy instead of symlink (default: symlink)")
    p_add_adapter.add_argument("--force", action="store_true", help="Overwrite if exists")

    # Command: add-reporter
    p_add_reporter = subparsers.add_parser("add-reporter", help="Link/Copy an existing python file as a Reporter")
    p_add_reporter.add_argument("source", type=str, help="Path to the source python file")
    p_add_reporter.add_argument("--name", type=str, help="Rename destination file", default=None)
    p_add_reporter.add_argument("--copy", action="store_true", help="Copy instead of symlink (default: symlink)")
    p_add_reporter.add_argument("--force", action="store_true", help="Overwrite if exists")

    # Command: add-config
    p_add_config = subparsers.add_parser("add-config", help="Link/Copy an existing yaml file as a Config")
    p_add_config.add_argument("source", type=str, help="Path to the source yaml file")
    p_add_config.add_argument("--name", type=str, help="Rename destination file", default=None)
    p_add_config.add_argument("--copy", action="store_true", help="Copy instead of symlink (default: symlink)")
    p_add_config.add_argument("--force", action="store_true", help="Overwrite if exists")

    # --- Create New (Scaffolding) ---

    # Command: create-adapter
    p_create_adapter = subparsers.add_parser("create-adapter", help="Generate a new Adapter template")
    p_create_adapter.add_argument("name", type=str, help="Name of the file (e.g. my_adapter)")
    p_create_adapter.add_argument("--class-name", type=str, help="Name of the Python class", default=None)

    # Command: create-reporter
    p_create_reporter = subparsers.add_parser("create-reporter", help="Generate a new Reporter template")
    p_create_reporter.add_argument("name", type=str, help="Name of the file (e.g. my_reporter)")
    p_create_reporter.add_argument("--class-name", type=str, help="Name of the Python class", default=None)

    # Command: create-config
    p_create_config = subparsers.add_parser("create-config", help="Generate a new Config template")
    p_create_config.add_argument("name", type=str, help="Name of the config file (e.g. my_model)")
    p_create_config.add_argument("--adapter", type=str, help="Name of the adapter module to link", required=True)
    p_create_config.add_argument("--class-name", type=str, help="Name of the adapter class", required=True)

    # --- Management ---

    # Command: remove
    p_remove = subparsers.add_parser("remove", help="Remove an adapter, reporter, or config")
    p_remove.add_argument("type", choices=["adapter", "reporter", "config"], help="Type of component")
    p_remove.add_argument("name", type=str, help="Name of the file to remove")

    # Command: list
    subparsers.add_parser("list", help="List available components with details")
    
    return parser

def to_camel_case(snake_str):
    return "".join(x.title() for x in snake_str.split("_"))

def validate_python_file(path: Path, expected_base: str):
    """
    Simple check to see if the file inherits from the expected base class.
    """
    try:
        content = path.read_text(encoding='utf-8')
        pattern = re.compile(rf"class\s+\w+\s*\([^)]*{expected_base}[^)]*\):")
        if not pattern.search(content):
            print(f"⚠️  Warning: Could not find a class inheriting from '{expected_base}' in {path.name}.")
            return False
        return True
    except Exception as e:
        print(f"⚠️  Warning: Could not read file to validate: {e}")
        return False

def handle_add(args, target_dir: Path, type_label: str, expected_base: str = None):
    source_path = Path(args.source).resolve()
    
    if not source_path.exists():
        print(f"❌ Error: Source file '{source_path}' does not exist.")
        return

    dest_name = args.name if args.name else source_path.name
    dest_path = target_dir / dest_name

    if dest_path.exists() and not args.force:
        print(f"❌ Error: Destination '{dest_path}' already exists.")
        print("   Use --force to overwrite.")
        return

    if expected_base and source_path.suffix == '.py':
        validate_python_file(source_path, expected_base)

    try:
        if args.copy:
            shutil.copy2(source_path, dest_path)
            action = "Copied"
        else:
            if dest_path.exists() or dest_path.is_symlink():
                dest_path.unlink()
            os.symlink(source_path, dest_path)
            action = "Linked"
            
        print(f"✅ Success! {action} {type_label}:")
        print(f"   Source: {source_path}")
        print(f"   Dest:   {dest_path}")
        
    except Exception as e:
        print(f"❌ Error: Failed to {action.lower()} file: {e}")

def handle_create(args, target_dir: Path, template: str, type_label: str):
    name = args.name
    if not name.endswith(".py") and type_label != "Config":
        name += ".py"
    if not name.endswith(".yaml") and type_label == "Config":
        name += ".yaml"

    dest_path = target_dir / name
    if dest_path.exists():
        print(f"❌ Error: {type_label} '{name}' already exists.")
        return

    # Prepare context for template
    ctx = {"name": args.name}
    
    if type_label == "Config":
        ctx["module_name"] = args.adapter.replace(".py", "")
        ctx["class_name"] = args.class_name
    else:
        # Auto-detect class name if not provided
        if args.class_name:
            ctx["class_name"] = args.class_name
        else:
            # simple snake_case to CamelCase conversion
            clean_name = name.replace(".py", "")
            ctx["class_name"] = to_camel_case(clean_name)

    content = template.format(**ctx)
    
    try:
        dest_path.write_text(content)
        print(f"✅ Created new {type_label}: {dest_path}")
        print(f"   Class Name: {ctx.get('class_name', 'N/A')}")
    except Exception as e:
        print(f"❌ Error writing file: {e}")

def handle_remove(args):
    target_map = {
        "adapter": ADAPTERS_DIR,
        "reporter": REPORTERS_DIR,
        "config": CONFIGS_DIR
    }
    
    directory = target_map[args.type]
    file_path = directory / args.name
    
    # Try adding extension if missing
    if not file_path.exists():
        if args.type == "config" and not args.name.endswith(".yaml"):
            file_path = directory / (args.name + ".yaml")
        elif args.type != "config" and not args.name.endswith(".py"):
            file_path = directory / (args.name + ".py")
            
    if not file_path.exists():
        print(f"❌ Error: Could not find {args.type} '{args.name}'")
        return

    try:
        if file_path.is_symlink():
            file_path.unlink()
            print(f"🗑️  Unlinked {args.type}: {args.name}")
        else:
            file_path.unlink()
            print(f"🗑️  Deleted {args.type}: {args.name}")
    except Exception as e:
        print(f"❌ Error removing file: {e}")

def print_component_list(title, directory, pattern):
    print(f"\n{title}")
    if not directory.exists():
        print("   (Directory does not exist)")
        return

    files = sorted([f for f in directory.glob(pattern) if not f.name.startswith("__")])
    if not files:
        print("   (None)")
        return

    for f in files:
        status = "📄"
        extra = ""
        if f.is_symlink():
            status = "🔗"
            try:
                target = f.readlink()
                extra = f" -> {target}"
            except OSError:
                extra = " -> (broken link)"
        
        print(f" {status} {f.name}{extra}")

def handle_list(args):
    print_component_list("📦 Adapters (src/eo_core/adapters/):", ADAPTERS_DIR, "*.py")
    print_component_list("📄 Reporters (src/eo_core/reporters/):", REPORTERS_DIR, "*.py")
    print_component_list("⚙️  Configs (configs/model/):", CONFIGS_DIR, "*.yaml")

def main():
    parser = setup_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Ensure directories exist
    ADAPTERS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTERS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "add-adapter":
        handle_add(args, ADAPTERS_DIR, "Adapter", "BaseAdapter")
    elif args.command == "add-reporter":
        handle_add(args, REPORTERS_DIR, "Reporter", "BaseReporter")
    elif args.command == "add-config":
        handle_add(args, CONFIGS_DIR, "Config")
        
    elif args.command == "create-adapter":
        handle_create(args, ADAPTERS_DIR, ADAPTER_TEMPLATE, "Adapter")
    elif args.command == "create-reporter":
        handle_create(args, REPORTERS_DIR, REPORTER_TEMPLATE, "Reporter")
    elif args.command == "create-config":
        handle_create(args, CONFIGS_DIR, CONFIG_TEMPLATE, "Config")
        
    elif args.command == "remove":
        handle_remove(args)
        
    elif args.command == "list":
        handle_list(args)

if __name__ == "__main__":
    main()

