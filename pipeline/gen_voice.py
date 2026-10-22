"""Glas za dijalog preko ElevenLabs API-ja: jedan WAV po kadru u audio/<kadar>.wav.

Radi i sa servisima koji prodaju ElevenLabs preko svog API-ja (npr. ai33): adresa ide u
ELEVENLABS_BASE_URL. Ako servis umesto zvuka vrati JSON, uzima se link do zvuka iz odgovora,
a ako vrati samo id posla, čeka se na ELEVENLABS_TASK_URL (npr. https://.../task/{task_id}).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from . import media, shotlist
from .config import Settings

AUDIO_KEYS = ("audio_url", "url", "file_url", "output_url", "download_url")
TASK_KEYS = ("task_id", "taskId", "id", "job_id")
FAILED = ("failed", "error", "canceled", "cancelled")


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


def tts(text: str, voice_id: str, settings: Settings, dest: Path, poll: float = 2.0,
        timeout: float = 180.0) -> Path:
    if not settings.elevenlabs_api_key:
        raise VoiceError("ELEVENLABS_API_KEY nije podešen u .env")
    headers = {settings.elevenlabs_auth_header: settings.elevenlabs_api_key}
    r = requests.post(
        f"{settings.elevenlabs_base_url}/text-to-speech/{voice_id}",
        params={"output_format": "mp3_44100_128"},
        headers={**headers, "Content-Type": "application/json"},
        json={"text": text, "model_id": settings.elevenlabs_model},
        timeout=120,
    )
    if r.status_code != 200:
        raise VoiceError(f"servis za glas je vratio {r.status_code}: {r.text[:300]}")
    if not _is_json(r):
        dest.write_bytes(r.content)
        return dest
    body = r.json()
    url = _find(body, AUDIO_KEYS)
    task = _find(body, TASK_KEYS)
    if url is None and task is not None:
        if not settings.elevenlabs_task_url:
            raise VoiceError(f"servis je vratio posao {task}, a ELEVENLABS_TASK_URL nije podešen u .env "
                             "(adresa za proveru posla, sa {task_id})")
        url = _wait_for_task(settings.elevenlabs_task_url.format(task_id=task), headers, poll, timeout)
    if url is None:
        raise VoiceError(f"u odgovoru servisa nema zvuka ni id-ja posla: {json.dumps(body)[:300]}")
    audio = requests.get(url, timeout=120)
    if audio.status_code != 200:
        raise VoiceError(f"preuzimanje zvuka nije uspelo: {audio.status_code}")
    dest.write_bytes(audio.content)
    return dest


def _is_json(r) -> bool:
    return "json" in (r.headers.get("Content-Type") or "").lower()


def _find(obj, keys: tuple[str, ...]):
    """Prva vrednost pod nekim od ključeva, i u ugnježdenim objektima (data, result, metadata)."""
    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if isinstance(value, (str, int)) and value != "":
                if keys is AUDIO_KEYS and not str(value).startswith("http"):
                    continue
                return value
        for value in obj.values():
            found = _find(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find(value, keys)
            if found is not None:
                return found
    return None


def _wait_for_task(url: str, headers: dict[str, str], poll: float, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code != 200:
            raise VoiceError(f"provera posla je vratila {r.status_code}: {r.text[:300]}")
        body = r.json()
        status = str(_find(body, ("status", "state")) or "").lower()
        if status in FAILED:
            raise VoiceError(f"servis za glas: posao nije uspeo ({json.dumps(body)[:300]})")
        audio = _find(body, AUDIO_KEYS)
        if audio:
            return str(audio)
        time.sleep(poll)
    raise VoiceError(f"servis za glas nije završio posao za {timeout:.0f} s")


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
