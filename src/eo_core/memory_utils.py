import psutil
import math
import torch
import gc
import logging
from typing import Tuple, Union, Any, Dict, List
from importlib import import_module

log = logging.getLogger(__name__)


def _load_reporter_class(target: str):
    try:
        module_name, class_name = target.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, class_name)
    except Exception as e:
        log.warning(
            f"Failed to load reporter class {target} for memory estimation: {e}"
        )
        return None


def calculate_optimal_zor(
    pipeline_cfg: Any,
    num_bands: int = 12,
    num_classes: int = 19,
    patch_size: int = 120,
    stride_ratio: float = 0.5,
    is_segmentation: bool = False,
    max_ram_gb: int = None,
) -> int:
    """
    Calculates the optimal Zone of Responsibility (ZoR) size using a precise memory model.
    """
    # Extract settings from pipeline_cfg
    tiling_cfg = pipeline_cfg.get("tiling", {})
    output_cfg = pipeline_cfg.get("output", {})
    dist_cfg = pipeline_cfg.get("distributed", {})
    reporter_configs = pipeline_cfg.get("reporters")

    halo = tiling_cfg.get("halo_size_pixels", 128)
    mem_safety_buffer_gb = tiling_cfg.get("memory_safety_buffer_gb", 1.0)

    # Prefetch Queue
    use_prefetcher = dist_cfg.get("use_prefetcher", True)
    prefetch_queue_size = (
        dist_cfg.get("prefetch_queue_size", 2) if use_prefetcher else 0
    )

    # Writer Queue
    writer_queue_size = dist_cfg.get("writer_queue_size", 4)

    # 1. Get Available Memory in Bytes
    buffer_bytes = mem_safety_buffer_gb * 1024**3
    if max_ram_gb:
        total_available_bytes = max_ram_gb * 1024**3
        available_bytes = max(0, total_available_bytes - buffer_bytes)
        log.info(
            f"ZoR Calculation: Manual Limit={max_ram_gb:.2f}GB, Buffer={mem_safety_buffer_gb:.2f}GB -> Effective={available_bytes / 1024**3:.2f}GB"
        )
    else:
        mem = psutil.virtual_memory()
        total_available_bytes = mem.available
        available_bytes = max(0, total_available_bytes - buffer_bytes)
        log.info(
            f"ZoR Calculation: System Available={total_available_bytes / 1024**3:.2f}GB, Buffer={mem_safety_buffer_gb:.2f}GB -> Effective={available_bytes / 1024**3:.2f}GB"
        )

    BYTES_FLOAT = 4
    BYTES_UINT8 = 1

    # --- BPP (Bytes Per Pixel of the CHUNK) Calculation ---

    # 1. Patches BPP (Float32)
    # Patches are views, so no overlap expansion.
    bpp_patches = num_bands * BYTES_FLOAT

    # 2. Logits BPP (Float32)
    patch_overlap_factor = (1.0 / stride_ratio) ** 2
    if is_segmentation:
        bpp_logits = num_classes * BYTES_FLOAT * patch_overlap_factor
    else:
        stride_pixels = patch_size * stride_ratio
        bpp_logits = (num_classes * BYTES_FLOAT) / (stride_pixels**2)

    # 3. Reconstruction BPP (Float32)
    bpp_recon = (num_classes + 1) * BYTES_FLOAT

    # 4. Reporter / Metrics BPP
    bpp_reporters = 0.0

    # Context for reporters
    reporter_context = {
        "num_classes": num_classes,
        "num_bands": num_bands,
        "is_segmentation": is_segmentation,
        "pipeline": pipeline_cfg,  # FULL pipeline config
    }

    if reporter_configs:
        # Normalize to list
        if isinstance(reporter_configs, dict):
            configs = list(reporter_configs.values())
        elif isinstance(reporter_configs, list):
            configs = reporter_configs
        else:
            configs = []

        for r_conf in configs:
            if r_conf is None:
                continue

            target = r_conf.get("_target_")
            if target:
                cls = _load_reporter_class(target)
                if cls and hasattr(cls, "get_memory_multiplier"):
                    try:
                        bpp_reporters += cls.get_memory_multiplier(
                            r_conf, reporter_context
                        )
                    except Exception as e:
                        log.warning(f"Error calculating memory for {target}: {e}")

    else:
        # Legacy / Default behavior: Assume standard GeoTIFFReporter logic
        save_conf = output_cfg.get("save_confidence", True)
        save_entr = output_cfg.get("save_entropy", True)
        save_gap = output_cfg.get("save_gap", True)

        bpp_reporters += BYTES_UINT8  # dom
        if save_conf:
            bpp_reporters += BYTES_FLOAT
        if save_entr:
            bpp_reporters += BYTES_FLOAT
        if save_gap:
            bpp_reporters += BYTES_FLOAT * 3

    # 5. Write Buffer Overhead
    bpp_io = num_bands * BYTES_FLOAT

    # --- Total System Footprint per Pixel ---

    # Patches:
    # 1. In Prefetch Queue (prefetch_queue_size)
    # 2. Currently being inferred (1)
    # 3. Currently being pre-processed/generated in the worker thread (1)
    # Total multiplier = prefetch_queue_size + 2
    total_bpp_patches = bpp_patches * (prefetch_queue_size + 2)

    total_bpp_logits = bpp_logits * (writer_queue_size + 3)

    # Recon & Metrics: Exist only in Writer
    total_bpp_recon = bpp_recon + bpp_reporters

    # Moderate generic overhead
    overhead_bpp = 300

    total_bpp = (
        total_bpp_patches + total_bpp_logits + total_bpp_recon + bpp_io + overhead_bpp
    )

    # --- Solve for ZoR ---
    max_pixels = available_bytes / total_bpp
    max_chunk_side = int(math.sqrt(max_pixels))

    # We need halo for the side calculation
    max_zor = max_chunk_side - (2 * halo)

    if max_zor <= 0:
        return patch_size

    optimal_zor = (max_zor // patch_size) * patch_size

    if optimal_zor < patch_size:
        optimal_zor = patch_size

    return optimal_zor


def resolve_zor(zor_config: Union[int, str], pipeline_cfg: Any, **kwargs) -> int:
    """
    Resolves the ZoR size from config, handling "auto" or string inputs.
    kwargs should contain num_bands, num_classes, patch_size, stride_ratio, is_segmentation, max_ram_gb.
    """
    if isinstance(zor_config, str) and zor_config.lower() == "auto":
        log.info("Auto-calculating Chunk Size based on available RAM...")
        return calculate_optimal_zor(pipeline_cfg=pipeline_cfg, **kwargs)
    elif isinstance(zor_config, int):
        return zor_config
    else:
        try:
            return int(zor_config)
        except:
            patch_size = kwargs.get("patch_size", 120)
            log.warning(f"Invalid ZoR config, defaulting to {patch_size * 10}")
            return patch_size * 10


def estimate_optimal_batch_size(
    model: torch.nn.Module,
    input_shape: Tuple[int, ...],
    device: torch.device,
    safety_factor: float = 0.40,
) -> int:
    """
    Estimates the optimal batch size for the given model and input shape by binary search
    or heuristic to fill GPU memory.

    Args:
        model: The PyTorch model (should be on 'device').
        input_shape: Shape of a SINGLE sample (C, H, W) or (C, T, H, W).
        device: The target device.
        safety_factor: Fraction of available memory to use (default 0.40).

    Returns:
        Recommended batch size (int).
    """
    if device.type == "cpu":
        return 16  # Conservative default for CPU

    log.info(
        f"🧠 Starting Binary Search for Optimal Batch Size (Safety={safety_factor:.2f})..."
    )

    # Binary Search Parameters
    low = 1
    high = 256  # Reduced hard cap from 512 to 256 for stability
    optimal_bs = 1

    # Get Total Memory
    total_mem = torch.cuda.get_device_properties(device).total_memory

    # Move model to device
    model.to(device)
    model.eval()  # Ensure eval mode

    # Get initial state
    log.info(f"DEBUG: estimate_optimal_batch_size syncing on device: {device}")
    torch.cuda.synchronize(device)
    torch.cuda.empty_cache()

    try:
        while low <= high:
            mid = (low + high) // 2

            try:
                # Create dummy input
                dummy_input = torch.zeros(
                    (mid, *input_shape), device=device, dtype=torch.float32
                )

                # Clean previous run
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats(
                    device
                )  # Reset stats to capture this run's peak

                # Dry Run
                with torch.no_grad():
                    _ = model(dummy_input)

                # Check PEAK Memory Usage
                peak_alloc = torch.cuda.max_memory_allocated(device)

                if peak_alloc > (total_mem * safety_factor):
                    high = mid - 1
                else:
                    # It works and is safe
                    optimal_bs = mid
                    low = mid + 1
                    # log.debug(f"Batch {mid}: OK")

            except RuntimeError as e:
                if "out of memory" in str(e):
                    # log.debug(f"Batch {mid}: OOM")
                    high = mid - 1
                else:
                    # Some other error? Re-raise
                    raise e

        # Final result is already safe due to the check inside the loop
        final_bs = max(1, optimal_bs)

        log.info(f"🧠 Binary Search Result: SafeBS={final_bs}")

        return final_bs

    except Exception as e:
        log.warning(f"⚠️ Binary search failed ({e}). Defaulting to 1.")
        return 1
