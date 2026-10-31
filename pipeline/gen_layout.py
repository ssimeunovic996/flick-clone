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

Postavka koju Stefan sam uređuje (uputstvo u docs/POSTAVKA.md):
    "layout": {"blend": "lokacije/s03_postavka.blend"}
Pipeline renderuje sliku iz kamere te postavke (`stage.py snapshot`) i pored nje sačuva .json sa
kamerom i lutkama, pa okret i mesto likova u promptu računa iz toga. Krajnja slika se pravi samo
ako postoji i `<kadar>_kraj.blend` (ili `"blend_end"`). Kad Stefan ponovo sačuva postavku, slika
se pravi iznova, a za njom i početna slika kadra.
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


def blend_file(project: Path, shot: dict[str, Any], key: str = "start") -> Path | None:
    """Postavka iz Blendera za početak ("start") ili kraj ("end") kadra, ako kadar radi tako."""
    layout = shot.get("layout") or {}
    if not layout.get("blend"):
        return None
    if key == "start":
        return project / layout["blend"]
    if layout.get("blend_end"):
        return project / layout["blend_end"]
    start = project / layout["blend"]
    name = start.name.replace("_postavka", "_kraj") if "_postavka" in start.name else f"{start.stem}_kraj.blend"
    return start.with_name(name)


def needs_end(shot: dict[str, Any], project: Path | None = None) -> bool:
    layout = shot.get("layout") or {}
    if not layout or layout.get("end_frame", True) is False:
        return False
    if layout.get("blend"):  # postavka: kraj samo ako je Stefan sačuvao i krajnju postavku
        end = blend_file(project, shot, "end") if project is not None else None
        return bool(end and end.is_file())
    return True


def state(project: Path, shot: dict[str, Any], key: str) -> dict[str, Any] | None:
    """Stanje postavke (.json pored layout slike) koje je napravio `stage.py snapshot`."""
    rel = (shot.get("layout") or {}).get(key)
    path = (project / rel).with_suffix(".json") if rel else None
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def legend(project: Path, shot: dict[str, Any]) -> list[str]:
    if (shot.get("layout") or {}).get("blend"):
        return list((state(project, shot, "start") or {}).get("labels", []))
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
    if (shot.get("layout") or {}).get("blend"):
        snap = state(project, shot, "start" if t <= 0 else "end")
        if snap is None:
            return {}
        return _views(snap["camera"], snap.get("figures", {}), shot.get("characters", []), snap.get("resolution"))
    ops = project / (shot.get("layout") or {}).get("ops", "")
    if not ops.is_file():
        return {}
    stage = scene_ops.Stage.load(ops)
    if shot["id"] not in stage.shots:  # bez kadra u sceni Blender javlja grešku, ovde samo nema smera
        return {}
    figures = {cid: {**stage.object_at(shot["id"], cid, t), "pose": stage.objects[cid].get("pose", "stand")}
               for cid in shot.get("characters", []) if stage.objects.get(cid, {}).get("type") == "figure"}
    return _views(stage.camera_at(shot["id"], t), figures, shot.get("characters", []),
                  stage.shot(shot["id"]).get("resolution"))


def _views(cam: dict[str, Any], figures: dict[str, dict[str, Any]], characters: list[str],
           resolution: list[int] | None) -> dict[str, dict[str, str]]:
    pos, target = tuple(cam["pos"]), tuple(cam["target"])
    forward = cm.norm(cm.sub(target, pos))
    right = cm.norm(cm.cross(forward, (0.0, 1.0, 0.0)))
    w, h = resolution or [16, 9]
    half = 18 / cam["lens"] * (w / h if h > w else 1)  # Blender: senzor 36 mm po dužoj strani kadra
    out, dist = {}, {}
    for cid in characters:
        fig = figures.get(cid)
        if fig is None or fig.get("visible") is False:
            continue
        fpos = tuple(fig["pos"])
        delta = abs((fig["facing"] - scene_ops.yaw_towards(fpos, pos) + 180) % 360 - 180)
        rel = cm.sub(fpos, pos)
        dist[cid] = max(cm.dot(rel, forward), 0.01)
        x = cm.dot(rel, right) / dist[cid] / half  # -1 levi rub kadra, 1 desni
        out[cid] = {"view": "front" if delta < 50 else "back" if delta > 130 else "profile",
                    "pose": fig.get("pose", "stand"),
                    "side": "left" if x < -0.3 else "right" if x > 0.3 else "center"}
    if len(dist) > 1:
        near = min(dist.values())
        for cid, d in dist.items():
            out[cid]["depth"] = "foreground" if d == near else "background" if d > near * 1.8 else ""
    return out


def still_command(settings: Settings, ops: Path, shot_id: str, t: float, dest: Path) -> list[str]:
    return [settings.blender, "-b", "--python", str(STAGE), "--", "still", str(ops),
            "--shot", shot_id, "--t", f"{t:g}", "--out", str(dest)]


def snapshot_command(settings: Settings, blend: Path, dest: Path) -> list[str]:
    return [settings.blender, "-b", "--python", str(STAGE), "--", "snapshot", "--blend", str(blend),
            "--out", str(dest)]


def postavka_command(settings: Settings, ops: Path, shot_id: str, dest: Path) -> list[str]:
    return [settings.blender, "-b", "--python", str(STAGE), "--", "postavka", str(ops),
            "--shot", shot_id, "--out", str(dest)]


def run_blender(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _stale(image: Path, source: Path | None) -> bool:
    """Slika fali ili je starija od postavke iz koje se pravi."""
    if not image.exists():
        return True
    return source is not None and source.exists() and source.stat().st_mtime > image.stat().st_mtime


def missing(data: dict[str, Any], project: Path, only: set[str] | None = None) -> list[tuple[dict[str, Any], str]]:
    """(kadar, "start" ili "end") za layout slike koje fale ili su starije od postavke."""
    out = []
    for shot in data["shots"]:
        layout = shot.get("layout")
        if not layout or (only and shot["id"] not in only):
            continue
        for key in ("start", "end") if needs_end(shot, project) else ("start",):
            source = blend_file(project, shot, key)
            if not layout.get(key) or _stale(project / layout[key], source):
                out.append((shot, key))
    return out


def render(data: dict[str, Any], project: Path, settings: Settings, only: set[str] | None = None,
           log=print) -> list[str]:
    """Renderuje layout slike koje fale. Vraća listu problema (npr. Blender nije pronađen)."""
    problems: list[str] = []
    for shot, key in missing(data, project, only):
        layout = shot["layout"]
        dest = project / "kadrovi" / "layout" / f"{shot['id']}_{key}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        blend = blend_file(project, shot, key)
        if blend is not None:
            if not blend.exists():
                problems.append(f"kadar {shot['id']}: nema postavke {blend.relative_to(project)}; "
                                f"napravi je sa `postavka --shots {shot['id']}`")
                continue
            cmd = snapshot_command(settings, blend, dest)
        else:
            ops = project / layout["ops"]
            if not ops.exists():
                problems.append(f"kadar {shot['id']}: nema scene {layout['ops']}")
                continue
            t = 0.0 if key == "start" else float(shot["duration"])
            cmd = still_command(settings, ops, shot["id"], t, dest)
        try:
            r = run_blender(cmd)
        except FileNotFoundError:
            problems.append(f"Blender nije pronađen ({settings.blender}); upiši putanju u BLENDER u .env")
            break
        if r.returncode != 0 or not dest.exists():
            problems.append(f"kadar {shot['id']}: Blender nije napravio sliku: {(r.stderr or r.stdout)[-300:]}")
            continue
        layout[key] = f"kadrovi/layout/{dest.name}"
        log(f"kadar {shot['id']}: layout {key} -> {layout[key]}")
    return problems


def make_postavka(data: dict[str, Any], project: Path, settings: Settings, only: set[str] | None = None,
                  force: bool = False, log=print) -> list[str]:
    """Pravi `lokacije/<kadar>_postavka.blend` iz scene kadra (`layout.ops`) i upisuje ga u `layout.blend`.
    Postojeća postavka se ne dira bez --force, jer je Stefan možda već uređuje."""
    problems: list[str] = []
    for shot in data["shots"]:
        if only and shot["id"] not in only:
            continue
        layout = shot.get("layout") or {}
        if not layout.get("ops"):
            if only:
                problems.append(f"kadar {shot['id']}: nema scenu (layout.ops) iz koje se pravi postavka")
            continue
        ops = project / layout["ops"]
        dest = project / (layout.get("blend") or f"lokacije/{shot['id']}_postavka.blend")
        if dest.exists() and not force:
            log(f"kadar {shot['id']}: postavka već postoji ({dest.relative_to(project)}), ne diram je")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = run_blender(postavka_command(settings, ops, shot["id"], dest))
            except FileNotFoundError:
                problems.append(f"Blender nije pronađen ({settings.blender}); upiši putanju u BLENDER u .env")
                break
            if r.returncode != 0 or not dest.exists():
                problems.append(f"kadar {shot['id']}: Blender nije napravio postavku: {(r.stderr or r.stdout)[-300:]}")
                continue
            log(f"kadar {shot['id']}: postavka -> {dest.relative_to(project)}")
        layout["blend"] = dest.relative_to(project).as_posix()
        shot["layout"] = layout
    return problems
