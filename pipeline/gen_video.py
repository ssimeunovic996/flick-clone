"""Generisanje video kadrova u ComfyUI-ju, po modelu iz shotlist.json.

Model kadra je ime workflow-a u comfy-workflows/ (npr. "ltx-i2v" -> ltx-i2v.api.json i
ltx-i2v.slots.json). Slots fajl kaže i kako se pravi prompt i broj frejmova, pa novi model
dodaješ bez menjanja koda.
"""

from __future__ import annotations

import math
import random
import re
import time
from pathlib import Path
from typing import Any

from . import gen_refs, jobs, prompts, shotlist, workflows
from .comfy_client import ComfyClient
from .config import WORKFLOWS_DIR, Settings

HINTS = {
    "image": "početna slika fali; pokreni prvo `refs`",
    "audio": "glas fali; pokreni prvo `voice`",
    "control_video": "kontrolni video fali; napravi ga u Blenderu (blender/stage.py render)",
    "reference": "reference sheet lika fali; pokreni prvo `refs`",
}


class ShotNotReady(RuntimeError):
    pass


def frame_count(spec: dict[str, Any], duration: float, fps: int) -> int:
    """Pravilo iz slots fajla: "8k+1" (LTX), "4k+1" (modeli kao Wan) ili "exact"."""
    rule = str(spec.get("frames", "8k+1")).replace(" ", "")
    match = re.fullmatch(r"(\d+)k\+1", rule)
    if match:
        step = int(match.group(1))
        return step * max(1, math.ceil(duration * fps / step)) + 1
    return max(1, round(duration * fps))


def shot_values(data: dict[str, Any], project: Path, shot: dict[str, Any], spec: dict[str, Any],
                settings: Settings, seed: int) -> dict[str, Any]:
    fps = shotlist.fps(data)
    w, h = shotlist.resolution(data)
    multiple = spec.get("size_multiple", 32)
    mode = spec.get("prompt_mode", "i2v")

    def existing(rel: str | None) -> Path | None:
        return project / rel if rel and (project / rel).exists() else None

    values: dict[str, Any] = {
        "prompt": prompts.video_prompt(data, shot, mode),
        "negative": data.get("negative"),
        "image": existing(shot.get("start_frame")),
        "audio": existing((shot.get("audio") or {}).get("file")),
        "control_video": existing((shot.get("control") or {}).get("video")),
        "reference": gen_refs.shot_reference(data, project, shot, settings),
        "seed": seed,
        "width": shotlist.snap(w, multiple),
        "height": shotlist.snap(h, multiple),
        "frames": frame_count(spec, shot["duration"], fps),
        "fps": fps,
        "length_seconds": shot["duration"],
        "filename_prefix": f"flick/{data.get('film', 'film')}/{shot['id']}",
    }
    missing = [s for s in spec.get("required", []) if values.get(s) is None]
    if missing:
        raise ShotNotReady(f"kadar {shot['id']}: " + "; ".join(HINTS.get(s, f"fali '{s}'") for s in missing))
    return values


def pending(data: dict[str, Any], project: Path, only: set[str] | None = None,
            force: bool = False) -> list[dict[str, Any]]:
    out = []
    for shot in data["shots"]:
        if only and shot["id"] not in only:
            continue
        take = shotlist.latest_take(shot)
        done = shot.get("status") in ("video_ok", "approved") and take and (project / take["file"]).exists()
        if force or not done:
            out.append(shot)
    return out


def generate(data: dict[str, Any], project: Path, client: ComfyClient | None, settings: Settings,
             only: set[str] | None = None, force: bool = False, dry_run: bool = False,
             directory: Path = WORKFLOWS_DIR, save=None, log=print) -> list[str]:
    """Generiše kadrove kojima fali video. `save` se poziva posle svakog kadra (čuva napredak)."""
    problems: list[str] = []
    for shot in pending(data, project, only, force):
        model = shotlist.shot_model(data, shot)
        _, spec = workflows.load(model, directory)
        seed = shot.get("seed", random.randint(0, 2**31 - 1))
        try:
            values = shot_values(data, project, shot, spec, settings, seed)
        except ShotNotReady as e:
            problems.append(str(e))
            log(str(e))
            continue
        if shot["duration"] > spec.get("max_seconds", 30):
            log(f"kadar {shot['id']}: {shot['duration']} s je duže od {spec['max_seconds']} s koliko {model} podnosi")
        if dry_run:
            log(f"\n[{shot['id']}] model={model} mod={spec.get('prompt_mode', 'i2v')} "
                f"frejmova={values['frames']} {values['width']}x{values['height']} seed={seed}")
            for key in ("image", "audio", "control_video", "reference"):
                if values.get(key):
                    log(f"  {key}: {Path(values[key]).relative_to(project)}")
            log(f"  prompt: {values['prompt']}")
            continue
        n = len(shot.get("takes", [])) + 1
        dest = project / "kadrovi" / f"{shot['id']}_t{n}.mp4"
        log(f"kadar {shot['id']}: generišem pokušaj {n} ({model})")
        seconds = jobs.run_workflow(client, model, values, dest, jobs.VIDEO_EXTS, directory)
        shot.setdefault("takes", []).append({
            "n": n, "file": f"kadrovi/{dest.name}", "model": model, "seed": seed,
            "seconds": round(seconds, 1), "prompt": values["prompt"],
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        shot["status"] = "video_ok"  # i odobren kadar sa novim pokušajem ide ponovo na pregled
        log(f"kadar {shot['id']}: gotovo za {seconds:.0f} s -> kadrovi/{dest.name}")
        if save:
            save()
    return problems
