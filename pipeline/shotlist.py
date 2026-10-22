"""Učitavanje, provera i čuvanje shotlist.json fajla (format u docs/ARHITEKTURA.md)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

STATUSES = ("todo", "audio_ok", "video_ok", "approved")
CONTROL_TYPES = ("depth", "layout", "pose")
NARRATOR = "narrator"


class ShotlistError(ValueError):
    """Shotlist nije ispravan; poruka nabraja sve greške."""


def load(project_dir: Path) -> dict[str, Any]:
    path = Path(project_dir) / "shotlist.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        raise ShotlistError(f"{path}:\n- " + "\n- ".join(errors))
    return data


def save(project_dir: Path, data: dict[str, Any]) -> None:
    path = Path(project_dir) / "shotlist.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate(data: dict[str, Any]) -> list[str]:
    """Vraća listu grešaka; prazna lista znači da je shotlist ispravan."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["koren mora biti JSON objekat"]

    fmt = data.get("format", {})
    fps = fmt.get("fps", 24)
    if not isinstance(fps, int) or not 8 <= fps <= 60:
        errors.append("format.fps mora biti ceo broj od 8 do 60")
    res = fmt.get("resolution", [1280, 720])
    if not (isinstance(res, list) and len(res) == 2 and all(isinstance(v, int) and v > 0 for v in res)):
        errors.append("format.resolution mora biti [širina, visina]")

    characters = data.get("characters", {})
    if not isinstance(characters, dict):
        errors.append("characters mora biti objekat {id: {...}}")
        characters = {}

    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots mora biti neprazna lista")
        return errors

    seen: set[str] = set()
    for i, shot in enumerate(shots):
        where = f"shots[{i}]"
        if not isinstance(shot, dict):
            errors.append(f"{where} mora biti objekat")
            continue
        sid = shot.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append(f"{where}.id nedostaje")
        elif sid in seen:
            errors.append(f"{where}.id '{sid}' se ponavlja")
        else:
            seen.add(sid)
            where = f"kadar {sid}"
        dur = shot.get("duration")
        if not isinstance(dur, (int, float)) or not 1 <= dur <= 30:
            errors.append(f"{where}: duration mora biti broj sekundi od 1 do 30")
        if not isinstance(shot.get("action"), str) or not shot["action"].strip():
            errors.append(f"{where}: action (šta se dešava) nedostaje")
        for who in shot.get("characters", []):
            if who not in characters:
                errors.append(f"{where}: lik '{who}' nije definisan u characters")
        for j, line in enumerate(shot.get("dialogue", [])):
            who = line.get("who") if isinstance(line, dict) else None
            if who != NARRATOR and who not in characters:
                errors.append(f"{where}: dialogue[{j}].who '{who}' nije lik ni '{NARRATOR}'")
            if not isinstance(line, dict) or not str(line.get("text", "")).strip():
                errors.append(f"{where}: dialogue[{j}].text je prazan")
        control = shot.get("control")
        if control is not None:
            if control.get("type") not in CONTROL_TYPES:
                errors.append(f"{where}: control.type mora biti jedno od {CONTROL_TYPES}")
            if not control.get("video"):
                errors.append(f"{where}: control.video (putanja do videa) nedostaje")
        status = shot.get("status", "todo")
        if status not in STATUSES:
            errors.append(f"{where}: status '{status}' nije jedno od {STATUSES}")
        if not (shot.get("model") or data.get("default_model")):
            errors.append(f"{where}: nema model, a nema ni default_model")
    return errors


def fps(data: dict[str, Any]) -> int:
    return data.get("format", {}).get("fps", 24)


def resolution(data: dict[str, Any]) -> tuple[int, int]:
    w, h = data.get("format", {}).get("resolution", [1280, 720])
    return int(w), int(h)


def ltx_frames(duration: float, fps_value: int) -> int:
    """Broj frejmova u obliku 8k+1, koji LTX modeli očekuju (npr. 5 s pri 24 fps -> 121)."""
    k = max(1, math.ceil(duration * fps_value / 8))
    return 8 * k + 1


def snap(value: int, multiple: int = 32) -> int:
    """Zaokružuje dimenziju na najbliži umnožak (LTX traži umnoške od 32)."""
    return max(multiple, int(value / multiple + 0.5) * multiple)


def shot_model(data: dict[str, Any], shot: dict[str, Any]) -> str:
    return shot.get("model") or data["default_model"]


def has_dialogue(shot: dict[str, Any]) -> bool:
    return bool(shot.get("dialogue"))


def advance(shot: dict[str, Any], status: str) -> None:
    """Pomera status napred, nikad nazad."""
    current = shot.get("status", "todo")
    if STATUSES.index(status) > STATUSES.index(current):
        shot["status"] = status


def latest_take(shot: dict[str, Any], approved_only: bool = False) -> dict[str, Any] | None:
    takes = shot.get("takes", [])
    chosen = [t for t in takes if t.get("chosen")]
    if chosen:
        return chosen[-1]
    if approved_only:
        return None
    return takes[-1] if takes else None
