"""Render u Blenderu bez prozora. Preskače se ako `bpy` nije instaliran
(pokreni sa Python-om koji ima `pip install bpy`, ili iz Blenderovog Python-a)."""

import subprocess
import sys
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")

from tests.conftest import needs_ffmpeg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "blender" / "stage.py"

OPS = """[
  {"op": "add", "id": "pod", "shape": "plane", "pos": [0, 0, 0], "size": [6, 0, 6], "color": "#777777"},
  {"op": "add", "id": "zid", "shape": "box", "pos": [0, 1.5, -2], "size": [6, 3, 0.1], "color": "#cccccc"},
  {"op": "add", "id": "marko", "type": "figure", "pos": [0, 0, 0], "color": "blue"},
  {"op": "add", "id": "cam", "type": "camera", "pos": [0, 1.6, 4], "look_at": "marko", "lens_mm": 35},
  {"op": "shot", "id": "s01", "camera": "cam", "duration": 1, "fps": 8, "resolution": [128, 72]},
  {"op": "camera_move", "shot": "s01", "move": "dolly_in", "distance": 1}
]"""


def stage(*args: str) -> str:
    proc = subprocess.run([sys.executable, str(STAGE), *args], capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc.stdout


@pytest.fixture
def ops(tmp_path):
    path = tmp_path / "soba.ops.json"
    path.write_text(OPS, encoding="utf-8")
    return path


def test_still(ops, tmp_path):
    out = tmp_path / "still.png"
    stage("still", str(ops), "--samples", "4", "--out", str(out))
    assert out.exists() and out.stat().st_size > 1000


@needs_ffmpeg
def test_render_layout_and_depth(ops, tmp_path):
    from pipeline import media

    stage("render", str(ops), "--shot", "s01", "--samples", "2", "--out", str(tmp_path))
    for kind in ("layout", "depth"):
        video = tmp_path / f"soba_s01_{kind}.mp4"
        info = media.probe(video)
        stream = info["streams"][0]
        assert (stream["width"], stream["height"]) == (128, 72)
        frames = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                 "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(video)],
                                capture_output=True, text=True).stdout.strip()
        assert frames == "9"  # 1 s pri 8 fps -> 8k+1


@needs_ffmpeg
def test_depth_is_bright_near_and_dark_far(ops, tmp_path):
    stage("render", str(ops), "--passes", "depth", "--samples", "2", "--out", str(tmp_path))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(tmp_path / "soba_s01_depth.mp4"), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    w = 128
    figure = raw[40 * w + 64]  # sredina slike: figura
    wall = raw[10 * w + 10]    # gore levo: zid iza
    assert figure > wall + 20


def test_build_saves_blend(ops, tmp_path):
    out = tmp_path / "soba.blend"
    stage("build", str(ops), "--out", str(out))
    assert out.exists()
