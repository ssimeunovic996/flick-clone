"""Ceo tok na malom filmu: glas, reference, video, pregled, odobravanje i montaža."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import assemble, gen_voice, media, run, shotlist
from tests.conftest import make_audio, make_video, needs_ffmpeg, tiny_project

pytestmark = needs_ffmpeg


class FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code
        self.text = content[:100].decode(errors="replace")


@pytest.fixture
def env(tmp_path, monkeypatch, fake_comfy, workflows_dir):
    """Film, lažni ComfyUI i lažni ElevenLabs koji vraća ton dužine srazmerne tekstu."""
    calls = []

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        mp3 = tmp_path / f"tts{len(calls)}.mp3"
        make_audio(mp3, 0.2 + 0.05 * len(json["text"]))
        return FakeResponse(mp3.read_bytes())

    # samo ElevenLabs poziv je lažan; ComfyUI klijent i dalje koristi pravi requests
    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=fake_post))
    monkeypatch.setenv("COMFYUI_URL", fake_comfy.url)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("FLICK_WORKFLOWS_DIR", str(workflows_dir))
    project = tiny_project(tmp_path)
    return {"project": project, "comfy": fake_comfy, "tts": calls}


def load(project: Path) -> dict:
    return json.loads((project / "shotlist.json").read_text(encoding="utf-8"))


def test_full_run(env):
    project, comfy = env["project"], env["comfy"]
    assert run.main([str(project), "all"]) == 0

    data = load(project)
    s01, s02, s03 = data["shots"]
    # glas: dva kadra sa dijalogom, pravi voice_id i ključ
    assert [c["url"].rsplit("/", 1)[1] for c in env["tts"]] == ["v-narrator", "v-mila"]
    assert env["tts"][0]["headers"]["xi-api-key"] == "test-key"
    assert (project / s02["audio"]["file"]).exists() and s02["audio"]["seconds"] > 0
    # reference: sheet za oba lika, početna slika za svaki kadar
    assert all((project / ch["ref"]).exists() for ch in data["characters"].values())
    assert all((project / s["start_frame"]).exists() for s in data["shots"])
    assert (project / "likovi" / "_kadar_s03.png").exists()  # dva lika složena u jedan sheet
    # video: jedan pokušaj po kadru, 8k+1 frejmova, veličina zaokružena na 32
    for shot in data["shots"]:
        assert shot["status"] == "video_ok"
        assert [t["n"] for t in shot["takes"]] == [1]
        assert (project / shot["takes"][0]["file"]).exists()
    video_jobs = [w for w in comfy.prompts if "41" in w]
    assert [w["27"]["inputs"]["length"] for w in video_jobs] == [49, 49, 25]
    assert {(w["27"]["inputs"]["width"], w["27"]["inputs"]["height"]) for w in video_jobs} == {(320, 192)}
    a2v = next(w for w in video_jobs if "50" in w)
    assert a2v["50"]["inputs"]["audio"] == "flick/s02.wav"
    assert "Lip movements of Mila" in a2v["6"]["inputs"]["text"]
    # pregled
    review = (project / "pregled.md").read_text(encoding="utf-8")
    assert "## s02 (video_ok, 2 s)" in review
    assert len(list((project / "kadrovi" / "pregled").glob("*.jpg"))) == 9

    # drugo pokretanje ne šalje ništa novo
    jobs_before, tts_before = len(comfy.prompts), len(env["tts"])
    assert run.main([str(project), "all"]) == 0
    assert (len(comfy.prompts), len(env["tts"])) == (jobs_before, tts_before)

    # montaža traži odobrene kadrove
    assert run.main([str(project), "assemble"]) == 1
    for sid in ("s01", "s02", "s03"):
        assert run.main([str(project), "approve", sid]) == 0
    make_audio(project / "audio" / "muzika.mp3", 3, freq=220)
    data = load(project)
    data["music"] = {"file": "audio/muzika.mp3", "volume": 0.3}
    shotlist.save(project, data)
    assert run.main([str(project), "assemble"]) == 0

    film = project / "final" / "film.mp4"
    assert abs(media.duration(film) - 5.0) < 0.15
    info = media.probe(film)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (320, 180)
    assert media.has_audio(film)
    srt = (project / "final" / "film.srt").read_text(encoding="utf-8")
    assert "Jednom davno." in srt and "Deda!" in srt
    assert "00:00:02,000 -->" in srt  # replika iz s02 počinje kad i kadar


def test_force_makes_new_take_and_sends_back_to_review(env):
    project = env["project"]
    assert run.main([str(project), "all"]) == 0
    assert run.main([str(project), "approve", "s03"]) == 0
    assert run.main([str(project), "video", "--shots", "s03", "--force"]) == 0
    s03 = load(project)["shots"][2]
    assert [t["n"] for t in s03["takes"]] == [1, 2]
    assert s03["status"] == "video_ok"
    assert s03["takes"][0]["chosen"] is True
    assert run.main([str(project), "approve", "s03", "--take", "2"]) == 0
    s03 = load(project)["shots"][2]
    assert [t.get("chosen", False) for t in s03["takes"]] == [False, True]


def test_video_waits_for_voice(env, capsys):
    project = env["project"]
    assert run.main([str(project), "refs"]) == 0
    assert run.main([str(project), "video"]) == 1
    out = capsys.readouterr().out
    assert "kadar s02: glas fali; pokreni prvo `voice`" in out
    data = load(project)
    assert data["shots"][1].get("status", "todo") == "todo"
    assert data["shots"][0]["status"] == "video_ok"  # kadrovi bez a2v su urađeni


def test_dry_run_sends_nothing(env, capsys):
    project, comfy = env["project"], env["comfy"]
    (project / "kadrovi" / "start").mkdir(parents=True)
    for sid in ("s01", "s02", "s03"):
        (project / "kadrovi" / "start" / f"{sid}.png").write_bytes(b"png")
    data = load(project)
    for shot in data["shots"]:
        shot["start_frame"] = f"kadrovi/start/{shot['id']}.png"
    shotlist.save(project, data)
    assert run.main([str(project), "video", "--dry-run", "--shots", "s01"]) == 0
    out = capsys.readouterr().out
    assert "[s01] model=ltx-i2v mod=i2v frejmova=49 320x192" in out
    assert "prompt: Style: test style." in out
    assert comfy.prompts == [] and env["tts"] == []


def test_voice_longer_than_shot_is_reported(env, capsys):
    project = env["project"]
    data = load(project)
    data["shots"][1]["dialogue"][0]["text"] = "Deda, " * 20
    shotlist.save(project, data)
    assert run.main([str(project), "voice"]) == 0
    assert "kadar s02: glas traje" in capsys.readouterr().out


def test_check_reports_state(env, capsys):
    assert run.main([str(env["project"]), "check"]) == 0
    out = capsys.readouterr().out
    assert "workflow ltx-a2v: u redu" in out
    assert "ComfyUI radi: Lažni GPU" in out
    assert "2 kadrova čeka, 18 karaktera" in out


def test_subtitles_split_by_text_length():
    data = {"characters": {"a": {"name": "Ana"}}}
    shots = [
        {"id": "s01", "duration": 4, "dialogue": []},
        {"id": "s02", "duration": 4, "audio_start": 1, "audio": {"seconds": 3},
         "dialogue": [{"who": "a", "text": "Kratko."}, {"who": "a", "text": "Malo duža rečenica."}]},
    ]
    srt = assemble.subtitles(data, shots)
    assert srt.startswith("1\n00:00:05,000 --> 00:00:05,808\nKratko.")
    assert "00:00:05,808 --> 00:00:08,000\nMalo duža rečenica." in srt
