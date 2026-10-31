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


def test_postavka_and_snapshot(ops, tmp_path):
    """Stefan postavlja kadar u .blend; snapshot iz njega daje sliku i gde su kamera i lutke."""
    import json

    blend = tmp_path / "s01_postavka.blend"
    stage("postavka", str(ops), "--shot", "s01", "--out", str(blend))
    assert blend.exists()
    out = tmp_path / "s01_start.png"
    stage("snapshot", "--blend", str(blend), "--samples", "4", "--out", str(out))
    assert out.exists() and out.stat().st_size > 1000
    state = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert state["shot"] == "s01" and state["resolution"] == [128, 72]
    cam = state["camera"]
    assert cam["name"] == "cam" and abs(cam["lens"] - 35) < 0.01 and abs(cam["roll"]) < 0.5
    assert all(abs(a - b) < 1e-3 for a, b in zip(cam["pos"], [0, 1.6, 4]))
    assert cam["target"][2] < cam["pos"][2]  # gleda ka lutki, ka -Z
    marko = state["figures"]["marko"]
    assert marko["pos"] == [0.0, 0.0, 0.0] and marko["pose"] == "stand" and abs(marko["facing"]) < 0.01


def test_snapshot_reads_what_stefan_moved(ops, tmp_path):
    import json

    blend = tmp_path / "s01_postavka.blend"
    stage("postavka", str(ops), "--shot", "s01", "--out", str(blend))
    # kao da je Stefan pomerio lutku i okrenuo je za 90° pa sačuvao fajl
    script = tmp_path / "pomeri.py"
    script.write_text(
        "import bpy, math\n"
        "bpy.ops.wm.open_mainfile(filepath=r'%s')\n"
        "ob = bpy.data.objects['marko']\n"
        "ob.location = (1.0, 0.5, 0.0)\n"
        "ob.rotation_euler = (0, 0, math.radians(90))\n"
        "assert all(p.hide_select for p in ob.children)\n"
        "assert bpy.context.scene.camera.name == 'cam' and ob.animation_data is None\n"
        "bpy.ops.wm.save_mainfile()\n" % blend, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = tmp_path / "start.png"
    stage("snapshot", "--blend", str(blend), "--samples", "2", "--out", str(out))
    marko = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["figures"]["marko"]
    assert marko["pos"] == [1.0, 0.0, -0.5]  # Blender (x, y, z) -> three.js (x, z, -y)
    assert abs(marko["facing"] - 90) < 0.01


def test_snapshot_of_a_plain_build_file(ops, tmp_path):
    """I .blend iz `build` (bez podataka postavke) daje gde su lutke, po imenima delova."""
    import json

    blend = tmp_path / "soba.blend"
    stage("build", str(ops), "--shot", "s01", "--out", str(blend))
    out = tmp_path / "start.png"
    stage("snapshot", "--blend", str(blend), "--samples", "2", "--out", str(out))
    state = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert state["figures"]["marko"]["pose"] == "stand" and state["camera"]["name"] == "cam"
