import time
import subprocess
import sys
import logging
import os
import shutil
import json
import argparse
import zipfile
from pathlib import Path
from datetime import datetime

# Try to import pynvml for GPU temp monitoring
try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [BENCHMARK] - %(message)s"
)
log = logging.getLogger(__name__)


def get_gpu_temperature(gpu_index=0):
    """Gets the current GPU temperature."""
    if not PYNVML_AVAILABLE:
        log.warning("pynvml not installed. Cannot get GPU temperature.")
        return None
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)  # Default to GPU 0
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        return temp
    except Exception as e:
        log.error(f"Error reading GPU stats: {e}.")
        return None
    finally:
        try:
            pynvml.nvmlShutdown()
        except:
            pass


def wait_for_gpu_cooldown(target_temp: int, gpu_index: int = 0, poll_interval: int = 2):
    """
    Blocks execution indefinitely until GPU temperature drops below target_temp.
    """
    if not PYNVML_AVAILABLE:
        log.warning(
            "pynvml not installed. Skipping smart cooldown (sleeping 10s instead)."
        )
        time.sleep(10)
        return

    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)  # Default to GPU 0

        log.info(f"Waiting for GPU {gpu_index} to cool down to {target_temp}°C (No Timeout)...")

        while True:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)

            if temp <= target_temp:
                log.info(f"Cooldown complete. Current Temp: {temp}°C")
                return

            # Print status every 5 seconds roughly
            if int(time.time()) % 5 == 0 and sys.stdout.isatty():
                print(f"   ... cooling ... {temp}°C", end="\r", flush=True)

            time.sleep(poll_interval)

    except Exception as e:
        log.error(f"Error reading GPU stats: {e}. Skipping cooldown.")
    finally:
        try:
            pynvml.nvmlShutdown()
        except:
            pass


def flatten_configs(raw_configs: list, global_overrides: list = None) -> list:
    """
    Expands high-level config entries into individual run tasks.
    Supports:
    - Single model (string) or List of models (strings)
    - Single input (string) or List of inputs (strings)
    - Labels: Single string (prefix) or List of strings (1:1 with models)
    - Overrides: Global list + 'overrides' dict {model: [list]}
    """
    flat_configs = []
    if global_overrides is None:
        global_overrides = []
    
    for entry in raw_configs:
        # 1. Resolve Models List
        # Support "models" (list) or "name" (string/list)
        raw_models = entry.get("models", entry.get("name"))
        
        if isinstance(raw_models, str):
            models = [raw_models]
        elif isinstance(raw_models, list):
            models = raw_models
        else:
            log.warning(f"Skipping invalid run entry (no model name found): {entry}")
            continue

        # 2. Resolve Inputs List
        raw_inputs = entry.get("input_path")
        if not raw_inputs:
            log.warning(f"Skipping run entry (no input_path): {entry}")
            continue
            
        if isinstance(raw_inputs, str):
            inputs = [raw_inputs]
        else:
            inputs = raw_inputs
            
        # 3. Resolve Labels
        raw_label = entry.get("label", "")
        model_labels = {}
        
        # Determine model names for label mapping
        model_names_list = []
        for m in models:
            if isinstance(m, str): model_names_list.append(m)
            elif isinstance(m, dict): model_names_list.append(m.get("name", "unknown"))
        
        if isinstance(raw_label, list):
            # Map 1:1 if lengths match
            if len(raw_label) == len(model_names_list):
                model_labels = dict(zip(model_names_list, raw_label))
            else:
                log.warning(f"Label list length ({len(raw_label)}) does not match models length ({len(models)}). Using as simple labels.")
        
        # 4. Resolve Overrides
        base_overrides = entry.get("config_overrides", [])
        specific_overrides_map = entry.get("overrides", {})
        
        # 5. Cartesian Product
        for model_obj in models:
            # Normalize model object to name and specific params
            if isinstance(model_obj, str):
                model_name = model_obj
                obj_overrides = []
                obj_label = ""
            elif isinstance(model_obj, dict):
                model_name = model_obj.get("name", "unknown")
                obj_overrides = model_obj.get("config_overrides", [])
                obj_label = model_obj.get("label", "")
            else:
                continue

            # Determine Label for this Model
            # Priority: Object Label > Explicit List Mapping > User Prefix > Model Name
            if obj_label:
                lbl = obj_label
            elif model_name in model_labels:
                lbl = model_labels[model_name]
            else:
                lbl = str(raw_label) if isinstance(raw_label, str) else ""
            
            # Determine Overrides
            # Merge: Global + Base + Map[name] + Object Specific
            map_specific = specific_overrides_map.get(model_name, [])
            final_overrides = global_overrides + base_overrides + map_specific + obj_overrides
            
            for inp in inputs:
                # Final Label Generation
                is_multi_input = len(inputs) > 1
                is_multi_model = len(models) > 1
                
                inp_name = Path(inp).stem
                
                if lbl:
                    if is_multi_input:
                        run_label = f"{lbl}_{inp_name}"
                    else:
                        run_label = lbl
                else:
                    # Automatic labeling
                    if is_multi_input:
                        run_label = f"{model_name}_{inp_name}"
                    else:
                        run_label = model_name

                flat_configs.append({
                    "name": model_name,
                    "input_path": inp,
                    "label": run_label,
                    "config_overrides": final_overrides
                })
                
    return flat_configs


def run_execution_suite(
    output_base: str, configs: list, gpu_index: int = 0, python_bin: str = sys.executable, global_overrides: list = None
):
    """
    Orchestrates the back-to-back execution.
    """

    output_base = Path(output_base).resolve()
    
    # 1. Expand/Flatten Configuration
    execution_plan = flatten_configs(configs, global_overrides)

    log.info("=========================================")
    log.info("   GSIP BATCH RUN SUITE STARTED")
    log.info("=========================================")
    log.info(f"Output Base: {output_base}")
    if global_overrides:
        log.info(f"Global Overrides: {global_overrides}")
    log.info(f"Jobs to Run: {len(execution_plan)}")

    initial_gpu_temp = get_gpu_temperature(gpu_index)
    if initial_gpu_temp is not None:
        log.info(f"Initial GPU temperature: {initial_gpu_temp}°C")

    results = []

    for config in execution_plan:
        model_name = config["name"]
        input_path = Path(config["input_path"]).resolve()
        config_overrides = config.get("config_overrides", [])
        run_label = config.get("label", model_name)

        if not input_path.exists():
            log.error(
                f"Input path not found for {run_label}: {input_path}. Skipping run."
            )
            results.append(
                {
                    "model": run_label,
                    "status": "SKIPPED",
                    "reason": "Input path not found",
                }
            )
            continue

        log.info("")
        log.info(f"--- Preparing: {run_label} ({model_name}) ---")
        log.info(f"    Input: {input_path}")
        log.info(f"    Overrides: {config_overrides}")

        # 1. SMART COOLDOWN
        if initial_gpu_temp is not None:
            wait_for_gpu_cooldown(target_temp=initial_gpu_temp, gpu_index=gpu_index)

        # 2. DEFINE OUTPUT
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_output = output_base / run_label / timestamp

        # 3. BUILD COMMAND
        # Always point directly to main.py in the same directory as this script
        main_py = Path(__file__).resolve().parent / "main.py"
        
        cmd = [
            python_bin,
            str(main_py),
            f"input_path={input_path}",
            f"output_path={run_output}",
            f"model={model_name}",
            f"pipeline.distributed.gpu_index={gpu_index}",
            # Force enable benchmarking flags just in case
            "pipeline.output.save_preview=true",
            "pipeline.disable_progress_bar=true", # Disable progress bars to keep logs clean
        ] + config_overrides  # Append config overrides

        log.info(f"Executing: {' '.join(cmd)}")

        start_t = time.time()
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd(),
            )

            # Print output in real-time
            for line in process.stdout:
                print(f"[{model_name}] {line}", end="")

            process.wait()  # Wait for the process to complete

            if process.returncode == 0:
                duration = time.time() - start_t
                log.info(f"SUCCESS: {run_label} finished in {duration:.2f}s")
                results.append(
                    {
                        "model": run_label,
                        "status": "OK",
                        "duration": duration,
                        "path": str(run_output),
                    }
                )

            else:
                log.error(f"FAILURE: {run_label} failed with code {process.returncode}")
                results.append(
                    {"model": run_label, "status": "FAIL", "code": process.returncode}
                )

        except KeyboardInterrupt:
            log.error("Suite interrupted by user.")
            break
        except Exception as e:
            log.error(f"System error executing {model_name}: {e}")

    log.info("")
    log.info("=========================================")
    log.info("   EXECUTION SUMMARY")
    log.info("=========================================")
    for res in results:
        print(
            f"{res['model']:<30} | {res['status']:<5} | {res.get('duration', 0):.2f}s"
        )


def export_results(source_dir: Path, zip_path: Path, export_mode: str = "partial"):
    """
    Exports results to a ZIP file.
    export_mode="partial": Excludes large TIFF files (default).
    export_mode="full": Includes EVERYTHING.
    """
    source_dir = Path(source_dir).resolve()
    zip_path = Path(zip_path).resolve()
    
    mode_str = "FULL" if export_mode == "full" else "PARTIAL (No TIFFs)"
    log.info(f"Exporting results [{mode_str}] from {source_dir} to {zip_path}...")
    
    if not source_dir.exists():
        log.error(f"Source directory {source_dir} does not exist.")
        return
    
    results_found = False
    added_files = set()
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    
                    # PARTIAL MODE: Skip large TIFF files
                    if export_mode == "partial" and file_path.suffix.lower() in ['.tif', '.tiff']:
                        continue
                    
                    rel_path = file_path.relative_to(source_dir)
                    zf.write(file_path, rel_path)
                    added_files.add(str(rel_path))
                    results_found = True
                                
        if results_found:
             log.info(f"Export successful. Archive created at: {zip_path}")
        else:
             log.warning("No files found to export.")
        
    except Exception as e:
        log.error(f"Export failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run GSIP Batch Run Suite")
    parser.add_argument(
        "--config",
        type=str,
        default="batch_config.json",
        help="Path to the suite configuration JSON file (default: batch_config.json)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Override GPU index for all runs.",
    )
    
    # Export Options
    export_group = parser.add_mutually_exclusive_group()
    export_group.add_argument(
        "--export-partial",
        nargs=2,
        metavar=("ZIP_PATH", "SOURCE_DIR"),
        help="Export results EXCLUDING large TIFFs. Usage: --export-partial <zip_path> <source_dir>.",
    )
    export_group.add_argument(
        "--export-full",
        nargs=2,
        metavar=("ZIP_PATH", "SOURCE_DIR"),
        help="Export ALL results INCLUDING large TIFFs. Usage: --export-full <zip_path> <source_dir>.",
    )
    
    args = parser.parse_args()

    # --- MODE 1: EXPORT ONLY ---
    if args.export_partial:
        zip_out = args.export_partial[0]
        src_dir = args.export_partial[1]
        export_results(src_dir, zip_out, export_mode="partial")
        sys.exit(0)
        
    if args.export_full:
        zip_out = args.export_full[0]
        src_dir = args.export_full[1]
        export_results(src_dir, zip_out, export_mode="full")
        sys.exit(0)

    # --- MODE 2: RUN SUITE ---
    config_path = Path(args.config)

    if not config_path.exists():
        log.error(f"Configuration file not found: {config_path}")
        log.info("Please provide a valid JSON configuration file using --config.")
        log.info("Example structure:")
        example_conf = {
            "output_dir": "out/runs_final",
            "runs": [
                {
                    "name": "resnet_s2",
                    "input_path": "/path/to/input.SAFE",
                    "label": "optional_label",
                    "config_overrides": ["+pipeline.tiling.max_memory_gb=8"],
                }
            ],
        }
        print(json.dumps(example_conf, indent=2))
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            suite_config = json.load(f)
    except Exception as e:
        log.error(f"Failed to parse configuration file: {e}")
        sys.exit(1)

    output_dir = suite_config.get("output_dir", "out/runs_final")
    # Support multiple keys for backward compatibility
    configs = suite_config.get("runs", suite_config.get("experiments", suite_config.get("benchmarks", [])))
    
    global_overrides = suite_config.get("global_overrides", [])
    
    # Priority: Command line flag > Config file > Default (0)
    gpu_index = args.device if args.device is not None else suite_config.get("gpu_index", 0)

    if not configs:
        log.warning("No runs defined in configuration file.")
        sys.exit(0)

    run_execution_suite(output_dir, configs, gpu_index=gpu_index, global_overrides=global_overrides)



if __name__ == "__main__":
    main()
