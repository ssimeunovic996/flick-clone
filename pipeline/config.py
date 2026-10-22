"""Podešavanja iz .env fajla i okruženja."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "comfy-workflows"


def load_env(path: Path | None = None) -> None:
    """Učitava KEY=VALUE linije iz .env u os.environ (postojeće vrednosti ne gazi)."""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    comfyui_url: str
    elevenlabs_api_key: str | None
    elevenlabs_model: str
    ffmpeg: str
    ffprobe: str
    workflows_dir: Path = WORKFLOWS_DIR

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        return cls(
            comfyui_url=os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
            elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY") or None,
            elevenlabs_model=os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            ffmpeg=os.environ.get("FFMPEG", "ffmpeg"),
            ffprobe=os.environ.get("FFPROBE", "ffprobe"),
            workflows_dir=Path(os.environ.get("FLICK_WORKFLOWS_DIR", WORKFLOWS_DIR)),
        )
