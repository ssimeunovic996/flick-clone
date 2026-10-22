"""Reference sheet-ovi za likove i početne slike kadrova, preko lokalnog modela slike u ComfyUI-ju.

Lik koji već ima `ref` fajl se preskače, isto kao kadar koji već ima `start_frame`,
pa Stefan može da ubaci svoju sliku i pipeline je neće pregaziti.

Kadar sa poljem `end_moment` dobija i krajnju sliku (`end_frame`), napravljenu od početne slike
kao reference, ako workflow kadra prima krajnju sliku (slot `end_image`, npr. `minimax-h3`).

Kadar sa 3D blokiranjem (`layout`, vidi gen_layout.py) dobija početnu i krajnju sliku iz layout
slika iz Blendera: isto kadriranje i raspored, a likovi sa svojih sheet-ova (Layout to Render).
Krajnja slika čeka početnu, da se kadar pravi redom.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from . import gen_layout, jobs, media, prompts, shotlist, workflows
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


def missing_end_frames(data: dict[str, Any], project: Path, only: set[str] | None = None,
                       directory: Path = WORKFLOWS_DIR) -> list[dict[str, Any]]:
    out = []
    for shot in data["shots"]:
        if (only and shot["id"] not in only) or not (shot.get("end_moment") or gen_layout.needs_end(shot)):
            continue
        if shot.get("end_frame") and (project / shot["end_frame"]).exists():
            continue
        _, spec = workflows.load(shotlist.shot_model(data, shot), directory)
        if "end_image" in spec.get("slots", {}):
            out.append(shot)
    return out


def layout_image(project: Path, shot: dict[str, Any], key: str) -> Path | None:
    rel = (shot.get("layout") or {}).get(key)
    return project / rel if rel and (project / rel).exists() else None


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


class NotReady(Exception):
    """Slika kadra još ne može da se pravi (npr. čeka layout iz Blendera ili početnu sliku)."""


def sheet_values(data: dict[str, Any], cid: str) -> dict[str, Any]:
    return {
        "prompt": prompts.reference_sheet_prompt(data, cid),
        "negative": data.get("negative"),
        "width": SHEET_SIZE[0], "height": SHEET_SIZE[1],
        "seed": random.randint(0, 2**31 - 1),
        "filename_prefix": f"flick/{data.get('film', 'film')}/{cid}_sheet",
    }


def start_frame_values(data: dict[str, Any], project: Path, shot: dict[str, Any],
                       settings: Settings) -> dict[str, Any]:
    sheet = shot_reference(data, project, shot, settings)
    layout = layout_image(project, shot, "start")
    if shot.get("layout") and layout is None:
        raise NotReady(f"kadar {shot['id']}: početna slika čeka layout iz Blendera")
    if layout is None:
        prompt = prompts.start_frame_prompt(data, shot, with_reference=sheet is not None)
        return _frame_values(data, shot, prompt, sheet, None, "start")
    prompt = prompts.layout_frame_prompt(data, shot, with_reference=sheet is not None,
                                         legend=gen_layout.legend(project, shot),
                                         views=gen_layout.views(project, shot, 0.0))
    return _frame_values(data, shot, prompt, layout, sheet, "start")


def end_frame_values(data: dict[str, Any], project: Path, shot: dict[str, Any],
                     settings: Settings) -> dict[str, Any]:
    start = project / shot["start_frame"] if shot.get("start_frame") else None
    if start is None or not start.exists():
        raise NotReady(f"kadar {shot['id']}: krajnja slika čeka početnu")
    layout = layout_image(project, shot, "end") if gen_layout.needs_end(shot) else None
    if gen_layout.needs_end(shot) and layout is None:
        raise NotReady(f"kadar {shot['id']}: krajnja slika čeka layout iz Blendera")
    if layout is None:
        return _frame_values(data, shot, prompts.end_frame_prompt(data, shot), start, None, "kraj")
    sheet = shot_reference(data, project, shot, settings)  # kao početna slika: layout + likovi
    prompt = prompts.layout_frame_prompt(data, shot, end=True, with_reference=sheet is not None,
                                         legend=gen_layout.legend(project, shot),
                                         views=gen_layout.views(project, shot, float(shot["duration"])))
    return _frame_values(data, shot, prompt, layout, sheet, "kraj")


def _frame_values(data: dict[str, Any], shot: dict[str, Any], prompt: str, first: Path | None,
                  second: Path | None, suffix: str) -> dict[str, Any]:
    """`first` je slika koju model menja (sheet, početna slika ili layout), `second` dodatna."""
    w, h = shotlist.resolution(data)
    return {
        "prompt": prompt,
        "negative": data.get("negative"),
        "reference": first,
        "reference2": second,
        "width": shotlist.snap(w), "height": shotlist.snap(h),
        "seed": shot.get("seed", random.randint(0, 2**31 - 1)),
        "filename_prefix": f"flick/{data.get('film', 'film')}/{shot['id']}_{suffix}",
    }


def generate(data: dict[str, Any], project: Path, client: ComfyClient, settings: Settings,
             only: set[str] | None = None, directory: Path = WORKFLOWS_DIR,
             log=print) -> None:
    name = image_workflow(data)
    for cid in missing_sheets(data, project):
        dest = project / "likovi" / f"{cid}_sheet.png"
        log(f"lik {cid}: pravim reference sheet")
        seconds = jobs.run_workflow(client, name, sheet_values(data, cid), dest, jobs.IMAGE_EXTS, directory)
        data["characters"][cid]["ref"] = f"likovi/{dest.name}"
        log(f"lik {cid}: gotovo za {seconds:.0f} s -> likovi/{dest.name}")

    for shot in missing_start_frames(data, project, only, directory):
        try:
            values = start_frame_values(data, project, shot, settings)
        except NotReady as e:
            log(str(e))
            continue
        dest = project / "kadrovi" / "start" / f"{shot['id']}.png"
        log(f"kadar {shot['id']}: pravim početnu sliku")
        seconds = jobs.run_workflow(client, name, values, dest, jobs.IMAGE_EXTS, directory)
        shot["start_frame"] = f"kadrovi/start/{dest.name}"
        log(f"kadar {shot['id']}: gotovo za {seconds:.0f} s -> {shot['start_frame']}")

    for shot in missing_end_frames(data, project, only, directory):
        try:
            values = end_frame_values(data, project, shot, settings)
        except NotReady as e:
            log(str(e))
            continue
        dest = project / "kadrovi" / "start" / f"{shot['id']}_kraj.png"
        log(f"kadar {shot['id']}: pravim krajnju sliku")
        seconds = jobs.run_workflow(client, name, values, dest, jobs.IMAGE_EXTS, directory)
        shot["end_frame"] = f"kadrovi/start/{dest.name}"
        log(f"kadar {shot['id']}: gotovo za {seconds:.0f} s -> {shot['end_frame']}")
