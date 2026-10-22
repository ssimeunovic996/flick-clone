import pytest

from pipeline import workflows
from pipeline.comfy_client import ComfyClient, ComfyError
from tests.conftest import FAKE_WORKFLOWS, needs_ffmpeg

pytestmark = needs_ffmpeg


def test_system_stats(fake_comfy):
    assert ComfyClient(fake_comfy.url).system_stats()["devices"][0]["name"] == "Lažni GPU"


def test_friendly_error_when_comfy_is_down():
    with pytest.raises(ComfyError, match="da li je pokrenut"):
        ComfyClient("http://127.0.0.1:9", timeout=2).system_stats()


def test_upload_returns_subfolder_name(fake_comfy, tmp_path):
    img = tmp_path / "lice.png"
    img.write_bytes(b"\x89PNG")
    assert ComfyClient(fake_comfy.url).upload(img) == "flick/lice.png"
    assert fake_comfy.uploads == ["lice.png"]


def test_run_downloads_outputs(fake_comfy, tmp_path):
    wf = workflows.apply(FAKE_WORKFLOWS["ltx-i2v"]["api"], {"slots": FAKE_WORKFLOWS["ltx-i2v"]["slots"]["slots"]},
                         {"prompt": "test", "frames": 25, "width": 160, "height": 96})
    paths, seconds = ComfyClient(fake_comfy.url).run(wf, tmp_path / "out", output_node="41")
    assert sorted(p.suffix for p in paths) == [".mp4", ".png"]
    assert all(p.stat().st_size > 0 for p in paths)
    assert seconds >= 0


def test_failed_job_reports_node_error(fake_comfy, tmp_path):
    wf = workflows.apply(FAKE_WORKFLOWS["ltx-i2v"]["api"], {"slots": FAKE_WORKFLOWS["ltx-i2v"]["slots"]["slots"]},
                         {"prompt": "FAIL", "frames": 25})
    with pytest.raises(ComfyError, match="CLIPTextEncode \\(6\\): lažna greška"):
        ComfyClient(fake_comfy.url).run(wf, tmp_path)
