# Development & Modification Guide

## Extended Documentation
For detailed guides on adding new models (Adapters) or custom output formats (Reporters), please refer to:
👉 **[EXTENDING.md](EXTENDING.md)**

## Project Architecture

### Unified CLI Dispatcher
All tools (`infer`, `suite`, `studio`, `manage`) are managed by a central dispatcher in **`src/cli.py`**.
- During development, you should run commands via: `python src/cli.py [subcommand]`.
- When modifying sub-tools, ensure the `main()` function in their respective scripts (e.g., `src/manage.py`) remains the primary entry point for the dispatcher.

## Modifying the Core Pipeline

If you need to change how tiling works (e.g., switching from squares to hexagons, or changing the writer logic):
*   **Tiling Logic:** Modify `src/eo_core/process.py` inside `main_hydra`.
*   **Writing Logic:** Modify `src/eo_core/process.py` inside `writer_process`.

## modifying Data Loading

*   **Sentinel-2 Reading:** `src/eo_core/data.py` -> `_read_s2_bands_for_chunk`
*   **Sentinel-1 Reading:** `src/eo_core/data.py` -> `_read_s1_bands_for_chunk`

## Git Workflow

The project uses standard Git practices.
1.  Check status: `git status`
2.  Review changes: `git diff`
3.  Commit often.
