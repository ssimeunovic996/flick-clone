"""Pokretanje jednog workflow-a: popuni slotove, pošalji u ComfyUI, preuzmi i preimenuj izlaz."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import workflows
from .comfy_client import ComfyClient, ComfyError
from .config import WORKFLOWS_DIR

VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def pick_output(paths: list[Path], exts: tuple[str, ...]) -> Path:
    for ext in exts:
        for p in paths:
            if p.suffix.lower() == ext:
                return p
    raise ComfyError(f"među izlazima nema fajla tipa {exts}: {[p.name for p in paths]}")


def run_workflow(client: ComfyClient, name: str, values: dict[str, Any], dest: Path,
                 exts: tuple[str, ...], directory: Path = WORKFLOWS_DIR,
                 timeout: float = 3600) -> float:
    """Generiše jedan fajl na putanji `dest`. Vraća trajanje generisanja u sekundama."""
    workflow, spec = workflows.load(name, directory)
    filled = workflows.apply(workflow, spec, values, uploader=client.upload)
    with tempfile.TemporaryDirectory() as tmp:
        paths, seconds = client.run(filled, Path(tmp), spec.get("output_node"), timeout=timeout)
        out = pick_output(paths, tuple(spec.get("output_ext", exts)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(out), dest)
    return seconds
