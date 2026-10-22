"""Reference sheet-ovi za likove i početne slike kadrova, preko lokalnog modela slike u ComfyUI-ju.

Lik koji već ima `ref` fajl se preskače, isto kao kadar koji već ima `start_frame`,
pa Stefan može da ubaci svoju sliku i pipeline je neće pregaziti.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from . import jobs, media, prompts, shotlist, workflows
from .comfy_client import ComfyClient
from .config import WORKFLOWS_DIR, Settings

DEFAULT_IMAGE_WORKFLOW = "slika"
SHEET_SIZE = (1536, 1024)


def image_workflow(data: dict[str, Any]) -> str:
    return data.get("image_workflow", DEFAULT_IMAGE_WORKFLOW)


def missing_sheets(data: dict[str, Any], project: Path) -> list[str]:
    return [cid for cid, ch in data.get("characters", {}).items()
            if not ch.get("ref") or not (project / ch["ref"]).exists()]


def needs_start_frame(data: dict[str, Any], shot: dict[str, Any],
                      directory: Path = WORKFLOWS_DIR) -> bool:
    _, spec = workflows.load(shotlist.shot_model(data, shot), directory)
    return "image" in spec.get("slots", {}) and "image" in spec.get("required", [])


def missing_start_frames(data: dict[str, Any], project: Path, only: set[str] | None = None,
                         directory: Path = WORKFLOWS_DIR) -> list[dict[str, Any]]:
    out = []
    for shot in data["shots"]:
        if only and shot["id"] not in only:
            continue
        if shot.get("start_frame") and (project / shot["start_frame"]).exists():
            continue
        if needs_start_frame(data, shot, directory):
            out.append(shot)
    return out


def shot_reference(data: dict[str, Any], project: Path, shot: dict[str, Any],
                   settings: Settings) -> Path | None:
    """Reference sheet za kadar: jedan lik direktno, više likova složeno jedno pored drugog."""
    refs = [project / data["characters"][cid]["ref"] for cid in shot.get("characters", [])
            if data["characters"][cid].get("ref") and (project / data["characters"][cid]["ref"]).exists()]
    if not refs:
        return None
    if len(refs) == 1:
        return refs[0]
    dest = project / "likovi" / f"_kadar_{shot['id']}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    return media.hstack_images(refs, dest, ffmpeg=settings.ffmpeg)


def generate(data: dict[str, Any], project: Path, client: ComfyClient, settings: Settings,
             only: set[str] | None = None, directory: Path = WORKFLOWS_DIR,
             log=print) -> None:
    name = image_workflow(data)
    for cid in missing_sheets(data, project):
        dest = project / "likovi" / f"{cid}_sheet.png"
        values = {
            "prompt": prompts.reference_sheet_prompt(data, cid),
            "negative": data.get("negative"),
            "width": SHEET_SIZE[0], "height": SHEET_SIZE[1],
            "seed": random.randint(0, 2**31 - 1),
            "filename_prefix": f"flick/{data.get('film', 'film')}/{cid}_sheet",
        }
        log(f"lik {cid}: pravim reference sheet")
        seconds = jobs.run_workflow(client, name, values, dest, jobs.IMAGE_EXTS, directory)
        data["characters"][cid]["ref"] = f"likovi/{dest.name}"
        log(f"lik {cid}: gotovo za {seconds:.0f} s -> likovi/{dest.name}")

    w, h = shotlist.resolution(data)
    for shot in missing_start_frames(data, project, only, directory):
        dest = project / "kadrovi" / "start" / f"{shot['id']}.png"
        ref = shot_reference(data, project, shot, settings)
        values = {
            "prompt": prompts.start_frame_prompt(data, shot, with_reference=ref is not None),
            "negative": data.get("negative"),
            "reference": ref,
            "width": shotlist.snap(w), "height": shotlist.snap(h),
            "seed": shot.get("seed", random.randint(0, 2**31 - 1)),
            "filename_prefix": f"flick/{data.get('film', 'film')}/{shot['id']}_start",
        }
        log(f"kadar {shot['id']}: pravim početnu sliku")
        seconds = jobs.run_workflow(client, name, values, dest, jobs.IMAGE_EXTS, directory)
        shot["start_frame"] = f"kadrovi/start/{dest.name}"
        log(f"kadar {shot['id']}: gotovo za {seconds:.0f} s -> {shot['start_frame']}")
