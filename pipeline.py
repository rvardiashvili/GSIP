import os
import time
import threading
from pathlib import Path
from typing import List, Dict, Any

import torch
import numpy as np
from colorama import Fore, Style, init as colorama_init
from torch.utils.data import DataLoader

from config import DEVICE, USE_AMP, GPU_BATCH_SIZE, DATA_LOADER_WORKERS
from data_loader import PatchFolderDataset, load_patch_tensor
from utils import NORM_M, NORM_S, NEW_LABELS

colorama_init(autoreset=True)

NUM_WORKERS = DATA_LOADER_WORKERS
PREFETCH_FACTOR = 4

# Toggle monitoring display (clearing console)
ENABLE_MONITOR = True

class DebugDataset(torch.utils.data.Dataset):
    """Wraps a dataset to log DataLoader timings for debugging."""
    def __init__(self, base_dataset):
        self.base = base_dataset
        print(f"[MainProc] DebugDataset init at {time.time():.2f}")

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        if idx == 0:
            print(f"[Worker PID {os.getpid()}] first __getitem__ at {time.time():.2f}")
        return self.base[idx]

class SceneAnalyzer:
    """Manages the parallel CPU (Producer) and GPU (Consumer) pipeline."""

    def __init__(self, folder_path: Path, model: torch.nn.Module, max_patches: int = 0, enable_monitor=True):
        self.folder_path = folder_path
        self.model = model
        self.enable_monitor = enable_monitor

        # Wrap dataset with debug proxy
        base_dataset = PatchFolderDataset(folder_path, max_patches)
        self.dataset = DebugDataset(base_dataset)

        self.data_loader = DataLoader(
            self.dataset,
            batch_size=GPU_BATCH_SIZE,
            shuffle=False,
            num_workers=NUM_WORKERS,
            pin_memory=(DEVICE.type == 'cuda'),
            prefetch_factor=PREFETCH_FACTOR,
            persistent_workers=True,
            collate_fn=lambda x: (
                torch.stack([item[0] for item in x]),
                [item[1] for item in x]
            )
        )

        self.raw_results: List[Dict[str, Any]] = []
        self.labels_arr = np.array(NEW_LABELS)

        self.pipeline_status: Dict[str, Dict[str, Any]] = {}
        self.total_patches_processed = 0
        self.lock = threading.Lock()
        self.stop_gpu = threading.Event()
        self.status_condition = threading.Condition(self.lock)

        self.pipeline_status["GPU-Worker"] = {
            "status": "IDLE (Waiting for Data)",
            "current_batch": 0,
            "total_batches": 0,
            "patch_range": (0, 0),
        }

    def _aggregate_results(self, batch_tensors: torch.Tensor, batch_names: List[str], probs: np.ndarray):
        """
        Aggregate results but **do not store all tensors** in RAM.
        Only keep top 9 patches if needed.
        """
        # Find top 9 patches by max probability in this batch
        max_probs = probs.max(axis=1)
        top_indices = max_probs.argsort()[-9:] if len(max_probs) > 9 else range(len(max_probs))

        for i, name in enumerate(batch_names):
            prob_arr = probs[i]
            top_idx = prob_arr.argsort()[-5:][::-1]
            top_probs = prob_arr[top_idx]
            top_labels = self.labels_arr[top_idx]

            result = {
                "name": name,
                "probs": prob_arr,
                "max_prob": float(top_probs[0]) if len(top_probs) > 0 else 0.0,
                "top_classes": dict(zip(top_labels, top_probs.astype(float))),
                "top_label_name": top_labels[0] if len(top_labels) > 0 else "N/A",
                "top_label_prob": float(top_probs[0]) if len(top_probs) > 0 else 0.0,
            }


            self.raw_results.append(result)

    def monitor_thread(self, total_patches: int, total_batches: int, start_time: float):
        clear = lambda: os.system('cls' if os.name == 'nt' else 'clear')
        while not self.stop_gpu.is_set():
            with self.status_condition:
                self.status_condition.wait(timeout=0.2)
                status_copy = self.pipeline_status.copy()
                processed_count = self.total_patches_processed

            gpu_worker_status = status_copy.get("GPU-Worker", {})
            gpu_status = gpu_worker_status.get("status", "N/A")
            current_batch = gpu_worker_status.get("current_batch", 0)
            patch_range = gpu_worker_status.get("patch_range", (0, 0))

            if self.enable_monitor and ENABLE_MONITOR:
                clear()
                elapsed_time = time.time() - start_time
                print(f"{Fore.CYAN + Style.BRIGHT}--- Pipeline Monitor ---{Style.RESET_ALL}")
                print(f"Time Elapsed: {elapsed_time:.2f}s")
                print(f"Total Patches Processed: {processed_count}/{total_patches}")
                print(f"Total Batches: {total_batches}")
                print(f"Workers: {NUM_WORKERS} | Prefetch Factor: {PREFETCH_FACTOR}")
                print("--------------------------")
                cpu_status = f"RUNNING" if processed_count < total_patches else "DONE"
                print(f"{Fore.YELLOW}CPU Workers ({NUM_WORKERS}): {cpu_status}{Style.RESET_ALL}")

                gpu_color = (
                    Fore.GREEN if gpu_status == "DONE"
                    else (Fore.MAGENTA if "PROCESSING" in gpu_status else Fore.BLUE)
                )
                print(f"{Fore.MAGENTA}GPU Worker:{Style.RESET_ALL}")
                print(f"  - {gpu_color}{gpu_status} (Batch {current_batch}/{total_batches}, Patches {patch_range}){Style.RESET_ALL}")

            if self.stop_gpu.is_set():
                break

    def run(self) -> (List[float], int):
        if not self.dataset:
            return [], 0

        total_patches = len(self.dataset)
        batches_processed = 0
        batch_times = []
        total_batches = len(self.data_loader)

        start_pipeline_time = time.time()

        with self.lock:
            self.pipeline_status["GPU-Worker"]["total_batches"] = total_batches
            self.status_condition.notify_all()

        monitor = threading.Thread(target=self.monitor_thread, args=(total_patches, total_batches, start_pipeline_time))
        monitor.start()

        with torch.no_grad():
            for current_batch_cpu, current_batch_names in self.data_loader:
                batch_ready_time = time.time()  # Log the moment the batch is ready
                print(f"[Batch {batches_processed+1}] ready at {batch_ready_time:.2f} "
                    f"({len(current_batch_names)} patches)")
                start_batch_time = time.time()
                batches_processed += 1
                current_batch_size = len(current_batch_names)
                start_patch_index = (batches_processed - 1) * GPU_BATCH_SIZE
                end_patch_index = start_patch_index + current_batch_size - 1

                with self.lock:
                    self.pipeline_status["GPU-Worker"]["status"] = f"PROCESSING Batch {batches_processed}"
                    self.pipeline_status["GPU-Worker"]["current_batch"] = batches_processed
                    self.pipeline_status["GPU-Worker"]["patch_range"] = (start_patch_index, end_patch_index)
                    self.status_condition.notify_all()

                try:
                    tensor_gpu = current_batch_cpu.to(DEVICE, non_blocking=True)
                    tensor_gpu = (tensor_gpu - NORM_M.to(DEVICE)) / (NORM_S.to(DEVICE) + 1e-6)
                    if USE_AMP and DEVICE.type == 'cuda':
                        with torch.amp.autocast(device_type='cuda', dtype=torch.float16):
                            logits = self.model(tensor_gpu)
                    else:
                        logits = self.model(tensor_gpu)
                    probs = torch.sigmoid(logits.float()).cpu().numpy()
                except Exception as e:
                    print(f"{Fore.RED}GPU inference error on batch {batches_processed}: {e}{Style.RESET_ALL}")
                    probs = np.zeros((len(current_batch_names), len(NEW_LABELS)))

                self._aggregate_results(current_batch_cpu, current_batch_names, probs)
                batch_time = time.time() - start_batch_time
                batch_times.append(batch_time)
                self.total_patches_processed += current_batch_size

                with self.lock:
                    self.pipeline_status["GPU-Worker"]["status"] = f"IDLE (Processed Batch {batches_processed})"
                    self.status_condition.notify_all()

        self.stop_gpu.set()
        with self.lock:
            self.pipeline_status["GPU-Worker"]["status"] = "DONE"
            self.status_condition.notify_all()

        monitor.join()

        if self.enable_monitor and ENABLE_MONITOR:
            print(f"{Fore.CYAN + Style.BRIGHT}--- Pipeline Monitor Complete ---{Style.RESET_ALL}")
            print(f"Time Elapsed: {time.time() - start_pipeline_time:.2f}s")
            print(f"Total Patches: {self.total_patches_processed}/{total_patches}")
            print(f"{Fore.GREEN + Style.BRIGHT}✅ Scene analysis complete.{Style.RESET_ALL}")

        return batch_times, self.total_patches_processed
