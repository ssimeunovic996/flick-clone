"""Pomoćne funkcije za ffmpeg i ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise MediaError(f"komanda nije uspela: {' '.join(cmd[:3])} ...\n{tail}")


def probe(path: Path, ffprobe: str = "ffprobe") -> dict:
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise MediaError(f"ffprobe ne može da pročita {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def duration(path: Path, ffprobe: str = "ffprobe") -> float:
    return float(probe(path, ffprobe)["format"]["duration"])


def has_audio(path: Path, ffprobe: str = "ffprobe") -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path, ffprobe)["streams"])


def to_wav(src: Path, dest: Path, ffmpeg: str = "ffmpeg", rate: int = 44100) -> Path:
    run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(rate), str(dest)])
    return dest


def concat_wavs(parts: list[Path], dest: Path, gap: float = 0.3, ffmpeg: str = "ffmpeg") -> Path:
    """Spaja WAV delove sa kratkom pauzom između."""
    if len(parts) == 1:
        run([ffmpeg, "-y", "-v", "error", "-i", str(parts[0]), str(dest)])
        return dest
    inputs: list[str] = []
    labels = []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        labels.append(f"[{i}:a]")
        if i < len(parts) - 1:
            labels.append(f"[s{i}]")
    silences = ";".join(
        f"anullsrc=r=44100:cl=mono,atrim=duration={gap}[s{i}]" for i in range(len(parts) - 1)
    )
    graph = f"{silences};{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]", str(dest)])
    return dest


def hstack_images(images: list[Path], dest: Path, height: int = 1024, ffmpeg: str = "ffmpeg") -> Path:
    """Slaže slike jednu pored druge (zajednički reference sheet za kadar sa više likova)."""
    if len(images) == 1:
        run([ffmpeg, "-y", "-v", "error", "-i", str(images[0]), str(dest)])
        return dest
    inputs: list[str] = []
    scaled = []
    for i, img in enumerate(images):
        inputs += ["-i", str(img)]
        scaled.append(f"[{i}:v]scale=-2:{height}[v{i}]")
    graph = ";".join(scaled) + ";" + "".join(f"[v{i}]" for i in range(len(images)))
    graph += f"hstack=inputs={len(images)}[out]"
    run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[out]", str(dest)])
    return dest


def extract_frames(video: Path, dest_dir: Path, count: int = 3, ffmpeg: str = "ffmpeg",
                   ffprobe: str = "ffprobe") -> list[Path]:
    """Izvlači `count` frejmova ravnomerno kroz klip (za pregled kadra)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    total = duration(video, ffprobe)
    out = []
    for i in range(count):
        t = total * (i + 0.5) / count
        frame = dest_dir / f"{video.stem}_{i + 1}.jpg"
        run([ffmpeg, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
             "-q:v", "3", str(frame)])
        out.append(frame)
    return out
