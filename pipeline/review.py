"""Pregled kadrova: tri frejma po najnovijem pokušaju i pregled.md koji Claude Code čita.

Claude Code otvori slike iz kadrovi/pregled/, uporedi ih sa scenarijem i referencama,
pa odobri kadar (`approve`) ili traži novi pokušaj (`video --shots s03 --force`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import media, shotlist
from .config import Settings


def build(data: dict[str, Any], project: Path, settings: Settings, only: set[str] | None = None) -> Path:
    out_dir = project / "kadrovi" / "pregled"
    lines = [f"# Pregled: {data.get('film', project.name)}", ""]
    for shot in data["shots"]:
        if only and shot["id"] not in only:
            continue
        takes = shot.get("takes", [])
        status = shot.get("status", "todo")
        lines.append(f"## {shot['id']} ({status}, {shot['duration']} s)")
        lines.append(f"Radnja: {shot['action']}")
        for line in shot.get("dialogue", []):
            lines.append(f"Dijalog: {line['who']}: {line['text']}")
        if not takes:
            lines += ["Nema pokušaja.", ""]
            continue
        take = takes[-1]
        video = project / take["file"]
        if not video.exists():
            lines += [f"Fajl {take['file']} ne postoji.", ""]
            continue
        frames = media.extract_frames(video, out_dir, 3, settings.ffmpeg, settings.ffprobe)
        chosen = shotlist.latest_take(shot, approved_only=True)
        lines.append(f"Pokušaj {take['n']} od {len(takes)}: {take['file']} (model {take['model']}, "
                     f"seed {take['seed']}, {take['seconds']:.0f} s)")
        if chosen and chosen is not take:
            lines.append(f"Odobren je pokušaj {chosen['n']}.")
        lines.append("Frejmovi: " + ", ".join(str(f.relative_to(project)) for f in frames))
        lines.append("")
    dest = project / "pregled.md"
    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest


def approve(shot: dict[str, Any], take_n: int | None = None) -> dict[str, Any]:
    takes = shot.get("takes", [])
    if not takes:
        raise ValueError(f"kadar {shot['id']} nema nijedan pokušaj")
    take = next((t for t in takes if t["n"] == take_n), None) if take_n else takes[-1]
    if take is None:
        raise ValueError(f"kadar {shot['id']} nema pokušaj {take_n}")
    for t in takes:
        t.pop("chosen", None)
    take["chosen"] = True
    shotlist.advance(shot, "approved")
    return take
