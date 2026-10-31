"""Lažni ComfyUI server i mali test film, da pipeline može da se proveri bez GPU-a."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg nije instaliran")

# podešavanja sa pravog računara (Blender, ai33 adresa, ključ) ne smeju da uđu u testove
LOCAL_ENV_KEYS = ("BLENDER", "COMFYUI_URL", "ELEVENLABS_API_KEY", "ELEVENLABS_BASE_URL", "ELEVENLABS_TASK_URL",
                  "ELEVENLABS_AUTH_HEADER", "ELEVENLABS_MODEL", "FLICK_WORKFLOWS_DIR")


@pytest.fixture(autouse=True)
def no_local_env(monkeypatch):
    """Testovi ne čitaju pravi .env, pa daju isti rezultat i na Stefanovom računaru."""
    from pipeline import config

    monkeypatch.setattr(config, "load_env", lambda path=None: None)
    for key in LOCAL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def make_video(dest: Path, seconds: float, size=(320, 192), fps=24, audio=True) -> Path:
    args = ["-f", "lavfi", "-i", f"testsrc=size={size[0]}x{size[1]}:rate={fps}:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds}"]
    ffmpeg(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-shortest", str(dest))
    return dest


def make_audio(dest: Path, seconds: float, freq: int = 440) -> Path:
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", str(dest))
    return dest


# Lažni workflow-i u API formatu, sa istim imenima ulaza kao pravi čvorovi.
FAKE_WORKFLOWS = {
    "slika": {
        "api": {
            "3": {"class_type": "KSampler", "inputs": {"seed": 1, "positive": ["6", 0], "negative": ["7", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "x", "images": ["8", 0]}},
            "10": {"class_type": "LoadImage", "inputs": {"image": "none.png"}},
            "11": {"class_type": "LoadImage", "inputs": {"image": "none.png"}},
            "12": {"class_type": "FakeImages", "inputs": {"image_1": ["10", 0], "image_2": ["11", 0]}},
        },
        "slots": {
            "unlink_if_empty": {"reference": {"node": "12", "input": "image_1"},
                                "reference2": {"node": "12", "input": "image_2"}},
            "slots": {
                "prompt": {"node": "6", "input": "text"}, "negative": {"node": "7", "input": "text"},
                "reference": {"node": "10", "input": "image"}, "reference2": {"node": "11", "input": "image"},
                "seed": {"node": "3", "input": "seed"},
                "width": {"node": "5", "input": "width"}, "height": {"node": "5", "input": "height"},
                "filename_prefix": {"node": "9", "input": "filename_prefix"},
            },
            "required": ["prompt"], "output_node": "9", "size_multiple": 16,
        },
    },
    "ltx-i2v": {
        "api": {
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}},
            "12": {"class_type": "LoadImage", "inputs": {"image": "none.png"}},
            "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 0}},
            "27": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 768, "height": 512, "length": 97}},
            "41": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "x", "frame_rate": 24}},
        },
        "slots": {
            "slots": {
                "prompt": {"node": "6", "input": "text"}, "negative": {"node": "7", "input": "text"},
                "image": {"node": "12", "input": "image"}, "seed": {"node": "25", "input": "noise_seed"},
                "width": {"node": "27", "input": "width"}, "height": {"node": "27", "input": "height"},
                "frames": {"node": "27", "input": "length"}, "fps": {"node": "41", "input": "frame_rate"},
                "filename_prefix": {"node": "41", "input": "filename_prefix"},
            },
            "required": ["prompt", "image"], "output_node": "41", "prompt_mode": "i2v", "frames": "8k+1",
        },
    },
}
FAKE_WORKFLOWS["ltx-a2v"] = {
    "api": {**FAKE_WORKFLOWS["ltx-i2v"]["api"], "50": {"class_type": "LoadAudio", "inputs": {"audio": "none.wav"}}},
    "slots": {
        **FAKE_WORKFLOWS["ltx-i2v"]["slots"],
        "slots": {**FAKE_WORKFLOWS["ltx-i2v"]["slots"]["slots"], "audio": {"node": "50", "input": "audio"}},
        "required": ["prompt", "image", "audio"], "prompt_mode": "a2v",
    },
}
FAKE_WORKFLOWS["i2v-kraj"] = {  # kao minimax-h3: početna i opciona krajnja slika
    "api": {**FAKE_WORKFLOWS["ltx-i2v"]["api"],
            "13": {"class_type": "LoadImage", "inputs": {"image": "none.png"}},
            "14": {"class_type": "FakeFirstLast", "inputs": {"first": ["12", 0], "last": ["13", 0]}}},
    "slots": {
        **FAKE_WORKFLOWS["ltx-i2v"]["slots"],
        "slots": {**FAKE_WORKFLOWS["ltx-i2v"]["slots"]["slots"], "end_image": {"node": "13", "input": "image"}},
        "unlink_if_empty": {"end_image": {"node": "14", "input": "last"}},
    },
}


@pytest.fixture
def workflows_dir(tmp_path: Path) -> Path:
    d = tmp_path / "workflows"
    d.mkdir()
    for name, wf in FAKE_WORKFLOWS.items():
        (d / f"{name}.api.json").write_text(json.dumps(wf["api"]), encoding="utf-8")
        (d / f"{name}.slots.json").write_text(json.dumps(wf["slots"]), encoding="utf-8")
    return d


class FakeComfy:
    """Minimalni ComfyUI: /system_stats, /upload/image, /prompt, /free, /history, /view."""

    def __init__(self, root: Path):
        self.root = root
        (root / "input").mkdir(parents=True)
        (root / "output").mkdir()
        self.uploads: list[str] = []
        self.frees = 0
        self.prompts: list[dict] = []
        self.history: dict[str, dict] = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def _execute(self, workflow: dict) -> dict:
        texts = [n["inputs"].get("text", "") for n in workflow.values()]
        if any("FAIL" in str(t) for t in texts):
            return {"status": {"status_str": "error", "completed": False, "messages": [
                ["execution_error", {"node_id": "6", "node_type": "CLIPTextEncode",
                                     "exception_message": "lažna greška"}]]}, "outputs": {}}
        outputs = {}
        for nid, node in workflow.items():
            inputs = node["inputs"]
            if "filename_prefix" not in inputs:
                continue
            name = f"{uuid.uuid4().hex[:8]}"
            if node["class_type"] == "SaveImage":
                size = next(n["inputs"] for n in workflow.values() if "width" in n["inputs"])
                dest = self.root / "output" / f"{name}.png"
                ffmpeg("-f", "lavfi", "-i", f"color=c=orange:s={size['width']}x{size['height']}",
                       "-frames:v", "1", str(dest))
                outputs[nid] = {"images": [{"filename": dest.name, "subfolder": "", "type": "output"}]}
            else:
                latent = next(n["inputs"] for n in workflow.values() if "length" in n["inputs"])
                fps = inputs.get("frame_rate", 24)
                dest = self.root / "output" / f"{name}.mp4"
                make_video(dest, latent["length"] / fps, (latent["width"], latent["height"]), fps)
                preview = self.root / "output" / f"{name}.png"
                ffmpeg("-i", str(dest), "-frames:v", "1", str(preview))
                outputs[nid] = {"images": [{"filename": preview.name, "subfolder": "", "type": "output"},
                                           {"filename": dest.name, "subfolder": "", "type": "output"}]}
        return {"status": {"status_str": "success", "completed": True, "messages": []}, "outputs": outputs}

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, body, code=200):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urlparse(self.path)
                if url.path == "/system_stats":
                    return self._json({"devices": [{"name": "Lažni GPU", "vram_free": 8 * 2**30}]})
                if url.path.startswith("/history/"):
                    pid = url.path.rsplit("/", 1)[1]
                    return self._json({pid: fake.history[pid]} if pid in fake.history else {})
                if url.path == "/view":
                    q = parse_qs(url.query)
                    path = fake.root / q["type"][0] / q.get("subfolder", [""])[0] / q["filename"][0]
                    data = path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return None
                self._json({"error": "not found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                if self.path == "/prompt":
                    workflow = json.loads(body)["prompt"]
                    fake.prompts.append(workflow)
                    pid = uuid.uuid4().hex
                    fake.history[pid] = fake._execute(workflow)
                    return self._json({"prompt_id": pid, "number": len(fake.prompts), "node_errors": {}})
                if self.path == "/free":
                    fake.frees += 1
                    return self._json({})
                if self.path == "/upload/image":
                    # dovoljno je izvući ime fajla iz multipart tela
                    marker = b'filename="'
                    start = body.index(marker) + len(marker)
                    name = body[start:body.index(b'"', start)].decode()
                    fake.uploads.append(name)
                    return self._json({"name": name, "subfolder": "flick", "type": "input"})
                self._json({"error": "not found"}, 404)

        return Handler


@pytest.fixture
def fake_comfy(tmp_path: Path):
    fake = FakeComfy(tmp_path / "comfy")
    fake.thread.start()
    yield fake
    fake.server.shutdown()


def tiny_project(tmp_path: Path) -> Path:
    """Film od tri kadra: narator, jedan lik sa dijalogom (a2v), dva lika bez dijaloga."""
    project = tmp_path / "film"
    project.mkdir()
    data = {
        "film": "test",
        "format": {"fps": 24, "resolution": [320, 180]},
        "style": "test style",
        "default_model": "ltx-i2v",
        "narrator_voice_id": "v-narrator",
        "characters": {
            "mila": {"name": "Mila", "description": "yellow sweater", "color": "yellow", "voice_id": "v-mila"},
            "deda": {"name": "Rade", "description": "grey cap", "color": "blue", "voice_id": "v-deda"},
        },
        "shots": [
            {"id": "s01", "duration": 2, "action": "empty room", "camera": {"shot": "wide", "move": "dolly_in"},
             "dialogue": [{"who": "narrator", "text": "Jednom davno."}]},
            {"id": "s02", "duration": 2, "action": "Mila looks up", "characters": ["mila"], "model": "ltx-a2v",
             "dialogue": [{"who": "mila", "text": "Deda!"}]},
            {"id": "s03", "duration": 1, "action": "they meet", "characters": ["deda", "mila"]},
        ],
    }
    (project / "shotlist.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return project
