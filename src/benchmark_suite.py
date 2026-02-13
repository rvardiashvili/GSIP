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


def run_benchmark_suite(
    output_base: str, benchmark_configs: list, gpu_index: int = 0, python_bin: str = sys.executable
):
    """
    Orchestrates the back-to-back benchmarking.
    """

    output_base = Path(output_base).resolve()

    log.info("=========================================")
    log.info("   GSIP NEW BENCHMARK SUITE STARTED")
    log.info("=========================================")
    log.info(f"Output Base: {output_base}")
    log.info(f"Benchmarks to Run: {len(benchmark_configs)}")

    initial_gpu_temp = get_gpu_temperature(gpu_index)
    if initial_gpu_temp is not None:
        log.info(f"Initial GPU temperature: {initial_gpu_temp}°C")

    results = []

    for config in benchmark_configs:
        model_name = config["name"]
        input_path = Path(config["input_path"]).resolve()
        config_overrides = config.get("config_overrides", [])
        run_label = config.get("label", model_name)

        if not input_path.exists():
            log.error(
                f"Input path not found for {run_label}: {input_path}. Skipping benchmark."
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
        cmd = [
            python_bin,
            "src/main.py",
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
    log.info("   BENCHMARK SUMMARY")
    log.info("=========================================")
    for res in results:
        print(
            f"{res['model']:<30} | {res['status']:<5} | {res.get('duration', 0):.2f}s"
        )


def export_benchmark_results(source_dir: Path, zip_path: Path):
    """
    Exports benchmark results to a ZIP file, mimicking the GTK client's export logic.
    Excludes large TIFF files.
    """
    source_dir = Path(source_dir).resolve()
    zip_path = Path(zip_path).resolve()
    
    log.info(f"Exporting results from {source_dir} to {zip_path}...")
    
    if not source_dir.exists():
        log.error(f"Source directory {source_dir} does not exist.")
        return

    # Find all benchmark JSONs
    benchmark_files = list(source_dir.rglob("benchmark_*.json"))
    
    if not benchmark_files:
        log.warning("No benchmark results found to export.")
        return

    added_files = set()
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in benchmark_files:
                # Add the benchmark file itself
                rel_path = f.relative_to(source_dir)
                if str(rel_path) not in added_files:
                    zf.write(f, rel_path)
                    added_files.add(str(rel_path))
                
                # Add sibling files (images, logs, other JSONs)
                parent_dir = f.parent
                for item in parent_dir.glob("*"):
                    if item.is_file():
                        # Skip large TIFF files
                        if item.suffix.lower() in ['.tif', '.tiff']:
                            continue
                        
                        # We are interested in visual assets and data
                        if item.suffix.lower() in ['.png', '.jpg', '.jpeg', '.json', '.log', '.txt']:
                            rel_item = item.relative_to(source_dir)
                            if str(rel_item) not in added_files:
                                zf.write(item, rel_item)
                                added_files.add(str(rel_item))
                                
        log.info(f"Export successful. Archive created at: {zip_path}")
        
    except Exception as e:
        log.error(f"Export failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run GSIP Benchmark Suite")
    parser.add_argument(
        "--config",
        type=str,
        default="benchmark_config.json",
        help="Path to the benchmark configuration JSON file (default: benchmark_config.json)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Override GPU index for all benchmarks.",
    )
    parser.add_argument(
        "--export",
        nargs=2,
        metavar=("ZIP_PATH", "SOURCE_DIR"),
        help="Export benchmark results to a ZIP archive. Usage: --export <zip_path> <source_dir>. This runs ONLY the export.",
    )
    args = parser.parse_args()

    # --- MODE 1: EXPORT ONLY ---
    if args.export:
        zip_out = args.export[0]
        src_dir = args.export[1]
        export_benchmark_results(src_dir, zip_out)
        sys.exit(0)

    # --- MODE 2: RUN BENCHMARKS ---
    config_path = Path(args.config)

    if not config_path.exists():
        log.error(f"Configuration file not found: {config_path}")
        log.info("Please provide a valid JSON configuration file using --config.")
        log.info("Example structure:")
        example_conf = {
            "output_dir": "out/benchmarks_final",
            "benchmarks": [
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

    output_dir = suite_config.get("output_dir", "out/benchmarks_final")
    benchmark_configs = suite_config.get("benchmarks", [])
    
    # Priority: Command line flag > Config file > Default (0)
    gpu_index = args.device if args.device is not None else suite_config.get("gpu_index", 0)

    if not benchmark_configs:
        log.warning("No benchmarks defined in configuration file.")
        sys.exit(0)

    run_benchmark_suite(output_dir, benchmark_configs, gpu_index=gpu_index)
