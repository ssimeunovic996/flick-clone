"""Montaža: odobreni kadrovi redom, glas preko kadra, muzika ispod, titlovi u .srt.

Svaki kadar se prvo svede na isti format (rezolucija, fps, trajanje iz shotlist-a, stereo
zvuk 48 kHz), pa se spajaju bez ponovnog kodiranja. Klip koji model vrati u malo drugačijoj
veličini (npr. 1280x704 umesto 1280x720) se uveća i iseče, bez crnih traka. Muzika se spušta dok neko govori.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import media, shotlist
from .config import Settings

# Zvuk koji H3 sam napravi ujednačava se na istu glasnoću (EBU R128, -16 LUFS, vrh -1,5 dB).
CLIP_LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"
# loudnorm sam ne drži vrh: u "Radio 2" s02 je posle montaže dostigao 0 dB. Limiter na -2 dB to sprečava.
CLIP_LIMITER = "alimiter=limit=0.79:level=false"


class AssembleError(RuntimeError):
    pass


def chosen_takes(data: dict[str, Any], project: Path, draft: bool) -> list[tuple[dict, dict]]:
    pairs, problems = [], []
    for shot in data["shots"]:
        take = shotlist.latest_take(shot, approved_only=not draft)
        if take is None:
            problems.append(f"kadar {shot['id']}: nema {'nijedan pokušaj' if draft else 'odobren pokušaj'}")
        elif not (project / take["file"]).exists():
            problems.append(f"kadar {shot['id']}: fajl {take['file']} ne postoji")
        else:
            pairs.append((shot, take))
    if problems:
        hint = "" if draft else "\n(za radnu verziju sa neodobrenim kadrovima dodaj --draft)"
        raise AssembleError("\n".join(problems) + hint)
    return pairs


def segment(data: dict[str, Any], project: Path, shot: dict[str, Any], take: dict[str, Any],
            dest: Path, settings: Settings) -> Path:
    w, h = shotlist.resolution(data)
    fps = shotlist.fps(data)
    dur = float(shot["duration"])
    clip = project / take["file"]
    cmd = [settings.ffmpeg, "-y", "-v", "error", "-i", str(clip)]

    voice = (shot.get("audio") or {}).get("file")
    keep_clip_audio = data.get("format", {}).get("keep_clip_audio", True)
    if voice and (project / voice).exists():
        cmd += ["-i", str(project / voice)]
        a_in = "1:a"
    elif keep_clip_audio and media.has_audio(clip, settings.ffprobe):
        a_in = "0:a"
    else:
        cmd += ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo"]
        a_in = "1:a"

    delay_ms = int(float(shot.get("audio_start", 0)) * 1000)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
          f"setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={dur}")
    af = "aresample=48000,aformat=channel_layouts=stereo"
    if a_in == "0:a":  # zvuk iz H3 klipa: glasnoća mu skače od kadra do kadra (-26 do -16 dB)
        af = f"{CLIP_LOUDNORM},{af},{CLIP_LIMITER}"  # loudnorm radi na 192 kHz, pa aresample ide posle njega
    if delay_ms and a_in != "0:a":
        af += f",adelay={delay_ms}|{delay_ms}"
    af += ",apad"
    cmd += ["-filter_complex", f"[0:v]{vf}[v];[{a_in}]{af}[a]", "-map", "[v]", "-map", "[a]",
            "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            str(dest)]
    media.run(cmd)
    return dest


def add_music(video: Path, music: dict[str, Any], project: Path, dest: Path,
              settings: Settings) -> Path:
    total = media.duration(video, settings.ffprobe)
    vol = float(music.get("volume", 0.25))
    fade = float(music.get("fade_out", 3))
    m = f"[1:a]volume={vol},atrim=0:{total:.3f},afade=t=out:st={max(0, total - fade):.3f}:d={fade}"
    if music.get("duck", True):
        graph = (f"{m}[m];[0:a]asplit[d][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=8:"
                 f"attack=20:release=400[md];[d][md]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        graph = f"{m}[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]"
    media.run([settings.ffmpeg, "-y", "-v", "error", "-i", str(video),
               "-stream_loop", "-1", "-i", str(project / music["file"]),
               "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dest)])
    return dest


def _ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def subtitles(data: dict[str, Any], shots: list[dict[str, Any]]) -> str:
    """SRT od dijaloga. Vreme replike se deli po dužini teksta unutar trajanja glasa kadra."""
    names = {cid: ch.get("name", cid.capitalize()) for cid, ch in data.get("characters", {}).items()}
    entries = []
    t0 = 0.0
    for shot in shots:
        lines = shot.get("dialogue", [])
        start = t0 + float(shot.get("audio_start", 0))
        window = (shot.get("audio") or {}).get("seconds") or (shot["duration"] - float(shot.get("audio_start", 0)))
        window = min(window, t0 + shot["duration"] - start)
        total_chars = sum(len(l["text"]) for l in lines) or 1
        for line in lines:
            span = window * len(line["text"]) / total_chars
            text = line["text"].strip()
            if line["who"] != shotlist.NARRATOR and data.get("subtitle_names", False):
                text = f"{names.get(line['who'], line['who'])}: {text}"
            entries.append((start, start + span, text))
            start += span
        t0 += shot["duration"]
    return "\n".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n" for i, (a, b, text) in enumerate(entries, 1))


def assemble(data: dict[str, Any], project: Path, settings: Settings, draft: bool = False,
             log=print) -> Path:
    pairs = chosen_takes(data, project, draft)
    final = project / "final"
    final.mkdir(exist_ok=True)
    name = "film_radna" if draft else "film"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        for i, (shot, take) in enumerate(pairs):
            log(f"kadar {shot['id']}: pokušaj {take['n']}")
            parts.append(segment(data, project, shot, take, tmp / f"{i:03}.mp4", settings))
        listing = tmp / "lista.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        joined = tmp / "spojeno.mp4"
        media.run([settings.ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", str(listing), "-c", "copy", str(joined)])
        dest = final / f"{name}.mp4"
        music = data.get("music")
        if music and (project / music["file"]).exists():
            add_music(joined, music, project, dest, settings)
        else:
            if music:
                log(f"muzika {music['file']} ne postoji, film ide bez muzike")
            shutil.move(str(joined), dest)  # temp može biti na drugom disku (C: vs D:)
    srt = subtitles(data, [s for s, _ in pairs])
    if srt:
        (final / f"{name}.srt").write_text(srt, encoding="utf-8")
    log(f"gotovo: {dest.relative_to(project)} ({media.duration(dest, settings.ffprobe):.1f} s)")
    return dest
