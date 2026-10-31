"""Slike iz 3D blokiranja (Blender) za kadrove sa poljem `layout`: kamera na početku i na kraju kadra.

Kadar u shotlist.json:

    "layout": {"ops": "lokacije/kuhinja.ops.json"}

Scena je `.ops.json` iz `blender/` sa kadrom istog id-ja. Pipeline renderuje sliku iz kamere na
početku i na kraju kadra (`kadrovi/layout/<kadar>_start.png` i `_end.png`). Qwen od njih napravi
pravu početnu i krajnju sliku (Layout to Render), a MiniMax H3 napravi pokret između njih
(first_frame + last_frame). Tako 3D vodi kameru i raspored i bez LTX-a.

Za svaku figuru lika pipeline iz scene računa da li je okrenuta ka kameri, leđima ili profilom,
da li sedi ili stoji, gde je u kadru (levo, sredina, desno) i ko je u prvom planu. Qwen bez toga
okrene lika licem ka kameri, a zamagljenu figuru tik uz kameru ne prepozna kao osobu.

Objekti u .ops.json mogu imati `label`: rečenicu na engleskom šta je blok u pravoj slici
("The brown box on the table is an old wooden radio."). Te rečenice idu u prompt za Qwen.

`"end_frame": false` u `layout` znači da se krajnja slika ne pravi iz 3D-a. Tada kadar ima samo
početnu sliku, a ako ima `end_moment`, krajnja slika je izmena početne (ista pozadina i svetlo).
To je bolje za male pokrete (blag dolly in, okret glave): Qwen iz dva layout-a izmisli dve malo
različite sobe, pa H3 između njih pretapa pozadinu. Layout za kraj vredi za velike pokrete (orbit). Blender se traži u BLENDER (u .env), podrazumevano `blender`.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from blender import camera_moves as cm
from blender import scene_ops

from .config import Settings

STAGE = Path(__file__).resolve().parent.parent / "blender" / "stage.py"


def needs_end(shot: dict[str, Any]) -> bool:
    layout = shot.get("layout") or {}
    return bool(layout) and layout.get("end_frame", True) is not False


def legend(project: Path, shot: dict[str, Any]) -> list[str]:
    ops = project / (shot.get("layout") or {}).get("ops", "")
    if not ops.is_file():
        return []
    return [op["label"] for op in json.loads(ops.read_text(encoding="utf-8"))
            if op.get("op") in ("add", "update") and op.get("label")]


def views(project: Path, shot: dict[str, Any], t: float) -> dict[str, dict[str, str]]:
    """Kako kamera vidi svaku figuru lika u trenutku t.

    {"mila": {"view": "front"|"back"|"profile", "pose": "sit"|"stand", "side": "left"|"center"|"right",
              "depth": "foreground"|"background"}}; "depth" samo kad je u kadru više figura.
    """
    ops = project / (shot.get("layout") or {}).get("ops", "")
    if not ops.is_file():
        return {}
    stage = scene_ops.Stage.load(ops)
    if shot["id"] not in stage.shots:  # bez kadra u sceni Blender javlja grešku, ovde samo nema smera
        return {}
    cam = stage.camera_at(shot["id"], t)
    forward = cm.norm(cm.sub(cam["target"], cam["pos"]))
    right = cm.norm(cm.cross(forward, (0.0, 1.0, 0.0)))
    w, h = stage.shot(shot["id"]).get("resolution", [16, 9])
    half = 18 / cam["lens"] * (w / h if h > w else 1)  # Blender: senzor 36 mm po dužoj strani kadra
    out, dist = {}, {}
    for cid in shot.get("characters", []):
        if stage.objects.get(cid, {}).get("type") != "figure":
            continue
        fig = stage.object_at(shot["id"], cid, t)
        delta = abs((fig["facing"] - scene_ops.yaw_towards(fig["pos"], cam["pos"]) + 180) % 360 - 180)
        rel = cm.sub(fig["pos"], cam["pos"])
        dist[cid] = max(cm.dot(rel, forward), 0.01)
        x = cm.dot(rel, right) / dist[cid] / half  # -1 levi rub kadra, 1 desni
        out[cid] = {"view": "front" if delta < 50 else "back" if delta > 130 else "profile",
                    "pose": stage.objects[cid].get("pose", "stand"),
                    "side": "left" if x < -0.3 else "right" if x > 0.3 else "center"}
    if len(dist) > 1:
        near = min(dist.values())
        for cid, d in dist.items():
            out[cid]["depth"] = "foreground" if d == near else "background" if d > near * 1.8 else ""
    return out


def still_command(settings: Settings, ops: Path, shot_id: str, t: float, dest: Path) -> list[str]:
    return [settings.blender, "-b", "--python", str(STAGE), "--", "still", str(ops),
            "--shot", shot_id, "--t", f"{t:g}", "--out", str(dest)]


def run_blender(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def missing(data: dict[str, Any], project: Path, only: set[str] | None = None) -> list[tuple[dict[str, Any], str]]:
    """(kadar, "start" ili "end") za layout slike koje fale."""
    out = []
    for shot in data["shots"]:
        layout = shot.get("layout")
        if not layout or (only and shot["id"] not in only):
            continue
        for key in ("start", "end") if needs_end(shot) else ("start",):
            if not (layout.get(key) and (project / layout[key]).exists()):
                out.append((shot, key))
    return out


def render(data: dict[str, Any], project: Path, settings: Settings, only: set[str] | None = None,
           log=print) -> list[str]:
    """Renderuje layout slike koje fale. Vraća listu problema (npr. Blender nije pronađen)."""
    problems: list[str] = []
    for shot, key in missing(data, project, only):
        layout = shot["layout"]
        ops = project / layout["ops"]
        if not ops.exists():
            problems.append(f"kadar {shot['id']}: nema scene {layout['ops']}")
            continue
        dest = project / "kadrovi" / "layout" / f"{shot['id']}_{key}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        t = 0.0 if key == "start" else float(shot["duration"])
        try:
            r = run_blender(still_command(settings, ops, shot["id"], t, dest))
        except FileNotFoundError:
            problems.append(f"Blender nije pronađen ({settings.blender}); upiši putanju u BLENDER u .env")
            break
        if r.returncode != 0 or not dest.exists():
            problems.append(f"kadar {shot['id']}: Blender nije napravio sliku: {(r.stderr or r.stdout)[-300:]}")
            continue
        layout[key] = f"kadrovi/layout/{dest.name}"
        log(f"kadar {shot['id']}: layout {key} -> {layout[key]}")
    return problems
