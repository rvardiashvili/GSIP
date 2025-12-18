import time
import subprocess
import sys
import logging
import os
from pathlib import Path
from datetime import datetime

# Try to import pynvml for GPU temp monitoring
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False

# Configure simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [BENCHMARK] - %(message)s')
log = logging.getLogger(__name__)

def wait_for_gpu_cooldown(target_temp: int = 65, poll_interval: int = 2):
    """
    Blocks execution indefinitely until GPU temperature drops below target_temp.
    """
    if not PYNVML_AVAILABLE:
        log.warning("pynvml not installed. Skipping smart cooldown (sleeping 10s instead).")
        time.sleep(10)
        return

    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0) # Default to GPU 0
        
        log.info(f"Waiting for GPU to cool down to {target_temp}°C (No Timeout)...")
        
        while True:
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            if temp <= target_temp:
                log.info(f"Cooldown complete. Current Temp: {temp}°C")
                return
            
            # Print status every 5 seconds roughly
            if int(time.time()) % 5 == 0:
                print(f"   ... cooling ... {temp}°C", end="\r", flush=True)
                
            time.sleep(poll_interval)
            
    except Exception as e:
        log.error(f"Error reading GPU stats: {e}. Skipping cooldown.")
    finally:
        try:
            pynvml.nvmlShutdown()
        except:
            pass

def run_benchmark_suite(input_path: str, output_base: str, models: list, python_bin: str = sys.executable):
    """
    Orchestrates the back-to-back benchmarking.
    """
    
    input_path = Path(input_path).resolve()
    output_base = Path(output_base).resolve()
    
    if not input_path.exists():
        log.error(f"Input path not found: {input_path}")
        return

    log.info("=========================================")
    log.info("   GSIP BENCHMARK SUITE STARTED")
    log.info("=========================================")
    log.info(f"Input: {input_path}")
    log.info(f"Models: {models}")
    
    results = []

    for model_name in models:
        log.info("")
        log.info(f"--- Preparing: {model_name} ---")
        
        # 1. SMART COOLDOWN
        wait_for_gpu_cooldown(target_temp=65) # Target temp 65C
        
        # 2. DEFINE OUTPUT
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_output = output_base / model_name / timestamp
        
        # 3. BUILD COMMAND
        # We use subprocess to ensure a clean process state (RAM/VRAM cleared)
        cmd = [
            python_bin,
            "src/main.py",
            f"input_path={input_path}",
            f"output_path={run_output}",
            f"model={model_name}",
            # Force enable benchmarking flags just in case
            "pipeline.output.save_preview=true"
        ]
        
        log.info(f"Executing: {' '.join(cmd)}")
        
        start_t = time.time()
        try:
            # Run and stream output
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.getcwd() # Run from project root
            )
            
            # Print output in real-time
            for line in process.stdout:
                print(f"[{model_name}] {line}", end="")
            
            process.wait() # Wait for the process to complete
            
            if process.returncode == 0:
                duration = time.time() - start_t
                log.info(f"SUCCESS: {model_name} finished in {duration:.2f}s")
                results.append({"model": model_name, "status": "OK", "duration": duration, "path": str(run_output)})
            else:
                log.error(f"FAILURE: {model_name} failed with code {process.returncode}")
                results.append({"model": model_name, "status": "FAIL", "code": process.returncode})
                
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
        print(f"{res['model']:<30} | {res['status']:<5} | {res.get('duration', 0):.2f}s")

if __name__ == "__main__":
    # CONFIGURATION
    
    # 1. Define your input tile (S2 SAFE path)
    # Using the one you provided in the prompt
    INPUT_TILE = "/home/rati/bsc_thesis/sentinel-2/T18TWL_20251001T155111/S2C_MSIL1C_20251001T155111_N0511_R054_T18TWL_20251001T192808.SAFE"
    
    # 2. Define Output Location
    OUTPUT_DIR = "out/benchmarks_final"
    
    # 3. Define Models to Test
    # Ensure these have corresponding .yaml files in configs/model/
    MODELS_TO_TEST = [
        "prithvi_crop"
    ]
    
    run_benchmark_suite(INPUT_TILE, OUTPUT_DIR, MODELS_TO_TEST)
