import time
import threading
import psutil
import json
import os
import torch
import platform
from pathlib import Path
from datetime import datetime
import logging

log = logging.getLogger(__name__)


class Benchmarker:
    def __init__(self, output_dir: Path, gpu_index: int = 0, interval: float = 1.0):
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.gpu_index = gpu_index
        self.running = False
        self.thread = None
        self.samples = []
        self.events = {}
        self.model_config = {}
        self.full_config = {}
        self.system_info = self._get_system_info()
        self.start_time = None
        self.end_time = None

        # Try to initialize NVML for GPU stats
        self.nvml_available = False
        try:
            import pynvml

            pynvml.nvmlInit()
            self.nvml_available = True
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(self.gpu_index)  # Use specified GPU
            log.info(f"Benchmarker: NVIDIA GPU monitoring enabled (GPU {self.gpu_index}).")
        except ImportError:
            log.warning(
                "Benchmarker: pynvml not found. GPU utilization will not be logged. (pip install pynvml)"
            )
        except Exception as e:
            log.warning(f"Benchmarker: NVML Init failed: {e}")

    def _get_system_info(self):
        info = {
            "os": platform.system(),
            "os_release": platform.release(),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "python_version": platform.python_version(),
            "torch_version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        }
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(self.gpu_index)
            info["gpu_count"] = torch.cuda.device_count()
        return info

    def set_model_config(self, config: dict):
        self.model_config = config

    def set_full_config(self, config: dict):
        self.full_config = config

    def start(self):
        self.running = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        log.info(f"Benchmarker started. Sampling every {self.interval}s.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        self.end_time = datetime.now()
        log.info("Benchmarker stopped.")

    def record_event(self, name: str, value: float):
        """
        Record a point event or duration.
        Example: record_event('wait_read', 0.05)
        """
        if name not in self.events:
            self.events[name] = []
        self.events[name].append(value)

    def _loop(self):
        current_process = psutil.Process()
        while self.running:
            try:
                # Calculate Process-specific Memory (RSS)
                # Sum memory of main process and all children (e.g. Writer Process)
                proc_mem_bytes = current_process.memory_info().rss
                try:
                    children = current_process.children(recursive=True)
                    for child in children:
                        try:
                            proc_mem_bytes += child.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                sample = {
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(interval=None),
                    "ram_percent": psutil.virtual_memory().percent,
                    "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                    "process_ram_used_gb": round(proc_mem_bytes / (1024**3), 2),
                }

                # GPU Stats
                if self.nvml_available:
                    import pynvml

                    try:
                        util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
                        mem = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
                        temp = pynvml.nvmlDeviceGetTemperature(
                            self.handle, pynvml.NVML_TEMPERATURE_GPU
                        )

                        sample["gpu_util_percent"] = util.gpu
                        sample["gpu_mem_percent"] = (mem.used / mem.total) * 100
                        sample["gpu_mem_used_gb"] = round(mem.used / (1024**3), 2)
                        sample["gpu_temp_c"] = temp
                    except Exception:
                        pass

                self.samples.append(sample)
                time.sleep(self.interval)
            except Exception as e:
                log.error(f"Benchmarker sampling error: {e}")
                break

    def save_report(self):
        duration = (
            (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        )

        # Aggregate Events
        event_stats = {}
        for k, v in self.events.items():
            if v:
                event_stats[k] = {
                    "count": len(v),
                    "sum": sum(v),
                    "mean": sum(v) / len(v),
                    "min": min(v),
                    "max": max(v),
                }

        # Aggregate Samples
        metric_stats = {}
        if self.samples:
            keys = self.samples[0].keys()
            for k in keys:
                if k == "timestamp":
                    continue
                values = [s[k] for s in self.samples if k in s]
                if values:
                    metric_stats[k] = {
                        "mean": sum(values) / len(values),
                        "max": max(values),
                        "min": min(values),
                    }

        report = {
            "meta": {
                "start": self.start_time.isoformat(),
                "end": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": duration,
            },
            "system": self.system_info,
            "model_config": self.model_config,
            "full_config": self.full_config,
            "pipeline_stats": event_stats,
            "system_stats": metric_stats,
            "time_series": self.samples,
        }

        filename = (
            self.output_dir
            / f"benchmark_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        log.info(f"Benchmark report saved to: {filename}")
        return filename
