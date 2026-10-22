"""Glas za dijalog preko ElevenLabs API-ja: jedan WAV po kadru u audio/<kadar>.wav."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import requests

from . import media, shotlist
from .config import Settings

API = "https://api.elevenlabs.io/v1"


class VoiceError(RuntimeError):
    pass


def lines_hash(shot: dict[str, Any], data: dict[str, Any]) -> str:
    payload = [(l["who"], l["text"], voice_for(data, l["who"])) for l in shot.get("dialogue", [])]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:12]


def voice_for(data: dict[str, Any], who: str) -> str | None:
    if who == shotlist.NARRATOR:
        return data.get("narrator_voice_id")
    return data.get("characters", {}).get(who, {}).get("voice_id")


def pending(data: dict[str, Any], project: Path, only: set[str] | None = None) -> list[dict[str, Any]]:
    """Kadrovi sa dijalogom kojima glas fali ili je zastareo."""
    out = []
    for shot in data["shots"]:
        if only and shot["id"] not in only or not shotlist.has_dialogue(shot):
            continue
        audio = shot.get("audio") or {}
        if audio.get("hash") != lines_hash(shot, data) or not (project / audio.get("file", "-")).exists():
            out.append(shot)
    return out


def characters_needed(shots: list[dict[str, Any]]) -> int:
    """Broj karaktera teksta; ElevenLabs naplaćuje po karakteru."""
    return sum(len(l["text"]) for s in shots for l in s.get("dialogue", []))


def tts(text: str, voice_id: str, settings: Settings, dest: Path) -> Path:
    if not settings.elevenlabs_api_key:
        raise VoiceError("ELEVENLABS_API_KEY nije podešen u .env")
    r = requests.post(
        f"{API}/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": settings.elevenlabs_model},
        timeout=120,
    )
    if r.status_code != 200:
        raise VoiceError(f"ElevenLabs greška {r.status_code}: {r.text[:300]}")
    dest.write_bytes(r.content)
    return dest


def generate(data: dict[str, Any], project: Path, settings: Settings,
             only: set[str] | None = None) -> list[str]:
    """Pravi glas za kadrove kojima fali. Vraća listu upozorenja (npr. glas duži od kadra)."""
    warnings: list[str] = []
    audio_dir = project / "audio"
    audio_dir.mkdir(exist_ok=True)
    for shot in pending(data, project, only):
        parts = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, line in enumerate(shot["dialogue"]):
                voice = voice_for(data, line["who"])
                if not voice:
                    raise VoiceError(f"kadar {shot['id']}: '{line['who']}' nema voice_id")
                mp3 = tts(line["text"], voice, settings, Path(tmp) / f"{i}.mp3")
                parts.append(media.to_wav(mp3, Path(tmp) / f"{i}.wav", settings.ffmpeg))
            dest = audio_dir / f"{shot['id']}.wav"
            media.concat_wavs(parts, dest, ffmpeg=settings.ffmpeg)
        seconds = media.duration(dest, settings.ffprobe)
        shot["audio"] = {"file": f"audio/{dest.name}", "hash": lines_hash(shot, data), "seconds": round(seconds, 2)}
        shotlist.advance(shot, "audio_ok")
        if seconds > shot["duration"]:
            warnings.append(f"kadar {shot['id']}: glas traje {seconds:.1f} s, a kadar {shot['duration']} s")
    return warnings
