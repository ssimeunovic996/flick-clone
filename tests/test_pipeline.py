"""Ceo tok na malom filmu: glas, reference, video, pregled, odobravanje i montaža."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import assemble, gen_layout, gen_voice, media, run, shotlist
from tests.conftest import ffmpeg, make_audio, make_video, needs_ffmpeg, tiny_project

pytestmark = needs_ffmpeg


class FakeResponse:
    def __init__(self, content: bytes = b"", status_code: int = 200, payload=None):
        self.content = content
        self.status_code = status_code
        self.payload = payload
        self.headers = {"Content-Type": "application/json" if payload is not None else "audio/mpeg"}
        self.text = json.dumps(payload) if payload is not None else content[:100].decode(errors="replace")

    def json(self):
        return self.payload


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
    assert comfy.frees == 1  # modeli za slike izbačeni jednom, pre prvog videa
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
    assert comfy.frees == 1  # bez novog videa nema ni pražnjenja memorije

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


def test_proba_is_half_size_and_kept_apart(env):
    """Proba: pola rezolucije, posebna lista `probe`; pravi video posle uzme njen seed."""
    project, comfy = env["project"], env["comfy"]
    assert run.main([str(project), "refs"]) == 0
    comfy.prompts.clear()
    assert run.main([str(project), "video", "--shots", "s01", "--proba"]) == 0
    (job,) = comfy.prompts
    assert (job["27"]["inputs"]["width"], job["27"]["inputs"]["height"]) == (160, 96)
    s01 = load(project)["shots"][0]
    assert s01["probe"][0]["file"] == "kadrovi/proba/s01_p1.mp4" and (project / s01["probe"][0]["file"]).exists()
    assert "takes" not in s01 and s01.get("status") != "video_ok"  # approve i montaža je ne vide

    assert run.main([str(project), "video", "--shots", "s01", "--proba"]) == 0
    assert len(comfy.prompts) == 1  # proba postoji, nova tek sa --force
    assert run.main([str(project), "video", "--shots", "s01"]) == 0
    s01 = load(project)["shots"][0]
    assert (comfy.prompts[-1]["27"]["inputs"]["width"], comfy.prompts[-1]["27"]["inputs"]["height"]) == (320, 192)
    assert s01["takes"][0]["seed"] == s01["probe"][0]["seed"] and s01["status"] == "video_ok"


def test_end_frame_made_from_start_frame(env):
    project, comfy = env["project"], env["comfy"]
    data = load(project)
    data["shots"][0].update(model="i2v-kraj", end_moment="the room is full of balloons")
    data["shots"][2]["model"] = "i2v-kraj"  # bez end_moment: nema krajnje slike
    shotlist.save(project, data)
    assert run.main([str(project), "refs"]) == 0
    data = load(project)
    s01, _, s03 = data["shots"]
    assert s01["end_frame"] == "kadrovi/start/s01_kraj.png" and (project / s01["end_frame"]).exists()
    assert "end_frame" not in s03
    end_job = next(w for w in comfy.prompts if "Final moment: the room is full of balloons" in w["6"]["inputs"]["text"])
    assert end_job["10"]["inputs"]["image"] != "none.png"  # početna slika je referenca

    comfy.prompts.clear()
    assert run.main([str(project), "video", "--shots", "s01,s03"]) == 0
    with_end, without_end = comfy.prompts
    assert with_end["13"]["inputs"]["image"] != "none.png" and with_end["14"]["inputs"]["last"] == ["13", 0]
    assert "last" not in without_end["14"]["inputs"]


def fake_blender(calls):
    """Umesto Blendera: zapamti komandu i napravi sliku na --out."""
    def run(cmd):
        calls.append(cmd)
        out = Path(cmd[cmd.index("--out") + 1])
        ffmpeg("-f", "lavfi", "-i", "color=c=gray:s=64x36", "-frames:v", "1", str(out))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return run


def test_layout_to_render_first_and_last_frame(env, monkeypatch):
    """3D blokiranje: Blender slike na početku i kraju kadra -> Qwen -> H3 first + last frame."""
    project, comfy = env["project"], env["comfy"]
    (project / "lokacije").mkdir()
    (project / "lokacije" / "soba.ops.json").write_text(json.dumps([
        {"op": "add", "id": "radio", "shape": "box", "label": "The brown box is an old radio"}]), encoding="utf-8")
    data = load(project)
    s01, s02, s03 = data["shots"]
    s01.update(model="i2v-kraj", layout={"ops": "lokacije/soba.ops.json"})  # bez likova
    s03.update(model="i2v-kraj", layout={"ops": "lokacije/soba.ops.json"})  # dva lika
    s02.update(model="i2v-kraj", layout={"ops": "lokacije/soba.ops.json", "end_frame": False},
               end_moment="she smiles")  # mali pokret: kraj je izmena početne slike, ne drugi layout
    shotlist.save(project, data)
    calls = []
    monkeypatch.setattr(gen_layout, "run_blender", fake_blender(calls))

    assert run.main([str(project), "refs"]) == 0
    data = load(project)
    s01, s02, s03 = data["shots"]
    assert [(c[c.index("--shot") + 1], c[c.index("--t") + 1]) for c in calls] == [
        ("s01", "0"), ("s01", "2"), ("s02", "0"), ("s03", "0"), ("s03", "1")]
    assert calls[0][:4] == ["blender", "-b", "--python", str(gen_layout.STAGE)]
    assert s01["layout"]["end"] == "kadrovi/layout/s01_end.png" and "end" not in s02["layout"]
    assert s01["end_frame"] == "kadrovi/start/s01_kraj.png" and s02["end_frame"] == "kadrovi/start/s02_kraj.png"
    edit = next(w for w in comfy.prompts if w["6"]["inputs"]["text"].startswith("Keep the exact same scene"))
    assert "Final moment: she smiles." in edit["6"]["inputs"]["text"]

    starts = [w for w in comfy.prompts if w["6"]["inputs"]["text"].startswith("Image 1 is a rough 3D blockout of a film")]
    ends = [w for w in comfy.prompts if w["6"]["inputs"]["text"].startswith("Image 1 is a rough 3D blockout of the last")]
    start_empty, _, start_cast = starts  # s01 bez likova: samo layout; s03: layout + sheet oba lika
    assert "image_2" not in start_empty["12"]["inputs"] and start_empty["10"]["inputs"]["image"] != "none.png"
    assert "mannequin" not in start_empty["6"]["inputs"]["text"].replace("No mannequins", "")
    assert start_cast["12"]["inputs"]["image_2"] == ["11", 0]
    assert "The yellow mannequin is Mila: yellow sweater." in start_cast["6"]["inputs"]["text"]
    end_empty, end_cast = ends  # kraj kao početak: layout + sheet-ovi (s01 bez likova nema drugu sliku)
    assert "image_2" not in end_empty["12"]["inputs"] and end_cast["12"]["inputs"]["image_2"] == ["11", 0]
    assert all("The brown box is an old radio." in w["6"]["inputs"]["text"] for w in starts + ends)

    assert run.main([str(project), "refs"]) == 0  # sve postoji: Blender se ne poziva ponovo
    assert len(calls) == 5


@pytest.mark.parametrize("cam,view", [([0, 1.6, 3], "front"), ([0, 1.6, -3], "back"), ([3, 1.6, 0], "profile")])
def test_layout_views_follow_the_camera(tmp_path, cam, view):
    """Kako kamera vidi figuru (licem, leđima, profilom) čita se iz 3D scene i ide u prompt za Qwen."""
    (tmp_path / "scena.ops.json").write_text(json.dumps([
        {"op": "add", "id": "mila", "type": "figure", "pos": [0, 0, 0], "facing": 0, "pose": "sit"},
        {"op": "add", "id": "kam", "type": "camera", "pos": cam, "look_at": "mila"},
        {"op": "shot", "id": "s01", "camera": "kam", "duration": 5}]), encoding="utf-8")
    shot = {"id": "s01", "duration": 5, "characters": ["mila", "deda"], "layout": {"ops": "scena.ops.json"}}
    # deda nema figuru u sceni; jedna figura nema prvi i drugi plan
    assert gen_layout.views(tmp_path, shot, 0.0) == {"mila": {"view": view, "pose": "sit", "side": "center"}}


def test_layout_views_place_figures_in_the_frame(tmp_path):
    # kamera gleda niz -Z: Mila tik uz kameru levo, deda daleko desno
    (tmp_path / "scena.ops.json").write_text(json.dumps([
        {"op": "add", "id": "mila", "type": "figure", "pos": [-0.4, 0, -1], "facing": 0, "pose": "sit"},
        {"op": "add", "id": "deda", "type": "figure", "pos": [1.2, 0, -5], "facing": 0},
        {"op": "add", "id": "kam", "type": "camera", "pos": [0, 1.2, 0], "look_at": [0, 1.2, -5], "lens_mm": 35},
        {"op": "shot", "id": "s03", "camera": "kam", "duration": 5, "resolution": [1280, 720]}]), encoding="utf-8")
    shot = {"id": "s03", "duration": 5, "characters": ["deda", "mila"], "layout": {"ops": "scena.ops.json"}}
    v = gen_layout.views(tmp_path, shot, 0.0)
    assert (v["mila"]["side"], v["mila"]["depth"], v["mila"]["view"]) == ("left", "foreground", "front")
    assert (v["deda"]["side"], v["deda"]["depth"], v["deda"]["pose"]) == ("right", "background", "stand")


def test_layout_without_blender_is_reported(env, monkeypatch, capsys):
    project = env["project"]
    data = load(project)
    data["shots"][0]["layout"] = {"ops": "soba.ops.json"}
    shotlist.save(project, data)
    (project / "soba.ops.json").write_text("[]", encoding="utf-8")

    def missing(cmd):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(gen_layout, "run_blender", missing)
    assert run.main([str(project), "refs"]) == 1
    assert "Blender nije pronađen (blender); upiši putanju u BLENDER u .env" in capsys.readouterr().out
    assert "start_frame" not in load(project)["shots"][0]  # bez layout-a se ne pravi slika samo iz teksta


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


def ai33_settings(**changes):
    from pipeline.config import Settings

    base = dict(comfyui_url="http://x", elevenlabs_api_key="k", elevenlabs_model="m", ffmpeg="ffmpeg",
                ffprobe="ffprobe", elevenlabs_base_url="https://api.primer-ai33.test/v1",
                elevenlabs_task_url="https://api.primer-ai33.test/v1/task/{task_id}")
    base.update(changes)
    return Settings(**base)


def test_voice_service_with_task_polling(tmp_path, monkeypatch):
    """Servis tipa ai33: POST vrati id posla, provera posla posle par pokušaja da link do zvuka."""
    mp3 = make_audio(tmp_path / "glas.mp3", 0.5)
    calls = []

    def post(url, params=None, headers=None, json=None, timeout=None):
        calls.append(("POST", url, headers))
        return FakeResponse(payload={"success": True, "task_id": "t-42"})

    def get(url, headers=None, timeout=None):
        calls.append(("GET", url, headers))
        if url.endswith("/task/t-42"):
            polls = sum(1 for c in calls if c[1].endswith("/task/t-42"))
            if polls < 2:
                return FakeResponse(payload={"status": "processing"})
            return FakeResponse(payload={"status": "done", "metadata": {"audio_url": "https://cdn.test/a.mp3"}})
        assert url == "https://cdn.test/a.mp3"
        return FakeResponse(mp3.read_bytes())

    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=get))
    dest = gen_voice.tts("Zdravo", "voice-1", ai33_settings(), tmp_path / "out.mp3", poll=0)
    assert dest.read_bytes() == mp3.read_bytes()
    assert calls[0][1] == "https://api.primer-ai33.test/v1/text-to-speech/voice-1"
    assert calls[0][2]["xi-api-key"] == "k"
    assert [c[0] for c in calls] == ["POST", "GET", "GET", "GET"]


def test_ai33_v3_text_to_speech(tmp_path, monkeypatch):
    """ai33: form polja na /v3/text-to-speech, glas dobija prefiks, posao se proverava na /v1/task."""
    mp3 = make_audio(tmp_path / "glas.mp3", 0.5)
    calls = []

    def post(url, headers=None, files=None, timeout=None):
        calls.append(("POST", url, headers, files))
        return FakeResponse(payload={"success": True, "task_id": "t-7"})

    def get(url, headers=None, timeout=None):
        calls.append(("GET", url, headers, None))
        if url == "https://api.ai33.pro/v1/task/t-7":
            return FakeResponse(payload={"id": "t-7", "status": "done", "progress": 100,
                                         "metadata": {"audio_url": "https://cdn.ai33.test/t-7.mp3"}})
        assert url == "https://cdn.ai33.test/t-7.mp3"
        return FakeResponse(mp3.read_bytes())

    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=get))
    settings = ai33_settings(elevenlabs_base_url="https://api.ai33.pro", elevenlabs_task_url=None)
    dest = gen_voice.tts("Day four hundred twelve.", "21m00Tcm4TlvDq8ikWAM", settings, tmp_path / "o.mp3", poll=0)
    assert dest.read_bytes() == mp3.read_bytes()
    method, url, headers, files = calls[0]
    assert url == "https://api.ai33.pro/v3/text-to-speech"
    assert headers == {"xi-api-key": "k"}
    assert files["voice_id"] == (None, "elevenlabs_21m00Tcm4TlvDq8ikWAM")
    assert files["text"] == (None, "Day four hundred twelve.")
    assert [c[0] for c in calls] == ["POST", "GET", "GET"]


def test_ai33_keeps_provider_prefix_and_strips_version(tmp_path, monkeypatch):
    sent = {}

    def post(url, headers=None, files=None, timeout=None):
        sent.update(url=url, voice=files["voice_id"][1])
        return FakeResponse(payload={"success": True, "task_id": "t-8"})

    get = lambda url, headers=None, timeout=None: FakeResponse(payload={"status": "error", "error_message": "no credits"})  # noqa: E731
    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=get))
    settings = ai33_settings(elevenlabs_base_url="https://api.ai33.pro/v1", elevenlabs_task_url=None)
    with pytest.raises(gen_voice.VoiceError, match="no credits"):
        gen_voice.tts("Or not.", "minimax_glas", settings, tmp_path / "o.mp3", poll=0)
    assert sent == {"url": "https://api.ai33.pro/v3/text-to-speech", "voice": "minimax_glas"}


def test_ai33_rejected_text_explains(tmp_path, monkeypatch):
    post = lambda url, headers=None, files=None, timeout=None: FakeResponse(payload={"success": False, "message": "bad voice"})  # noqa: E731
    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=None))
    settings = ai33_settings(elevenlabs_base_url="https://api.ai33.pro", elevenlabs_task_url=None)
    with pytest.raises(gen_voice.VoiceError, match="bad voice"):
        gen_voice.tts("Or not.", "x", settings, tmp_path / "o.mp3", poll=0)


def test_ai33_credits_and_voices(monkeypatch):
    seen = []

    def get(url, params=None, headers=None, timeout=None):
        seen.append((url, params))
        if url.endswith("/v1/credits"):
            return FakeResponse(payload={"success": True, "credits": 12345})
        return FakeResponse(payload={"success": True, "data": [{"voice_id": "elevenlabs_a", "name": "Rachel"}]})

    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(get=get))
    settings = ai33_settings(elevenlabs_base_url="https://api.ai33.pro")
    assert gen_voice.is_ai33(settings) and not gen_voice.is_ai33(ai33_settings())
    assert gen_voice.ai33_credits(settings) == 12345
    assert gen_voice.ai33_voices(settings, "calm")[0]["name"] == "Rachel"
    assert seen[1] == ("https://api.ai33.pro/v3/voices", {"provider": "elevenlabs", "page_size": 30, "search": "calm"})


def test_voice_service_task_without_task_url_explains(tmp_path, monkeypatch):
    post = lambda *a, **k: FakeResponse(payload={"task_id": "t-1"})  # noqa: E731
    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=None))
    with pytest.raises(gen_voice.VoiceError, match="ELEVENLABS_TASK_URL"):
        gen_voice.tts("x", "v", ai33_settings(elevenlabs_task_url=None), tmp_path / "o.mp3")


def test_voice_service_failed_task(tmp_path, monkeypatch):
    post = lambda *a, **k: FakeResponse(payload={"task_id": "t-1"})  # noqa: E731
    get = lambda *a, **k: FakeResponse(payload={"status": "failed", "error": "no credits"})  # noqa: E731
    monkeypatch.setattr(gen_voice, "requests", SimpleNamespace(post=post, get=get))
    with pytest.raises(gen_voice.VoiceError, match="nije uspeo"):
        gen_voice.tts("x", "v", ai33_settings(), tmp_path / "o.mp3", poll=0)


@pytest.mark.parametrize("rule,seconds,fps,frames", [
    ("8k+1", 5, 24, 121), ("4k+1", 5, 24, 121), ("4k+1", 6, 25, 153), ("exact", 5, 24, 120), ("exact", 6, 25, 150),
    ("17k+5", 5, 24, 124), ("17k+5", 4, 24, 107), ("17k+5", 0.1, 24, 5),
])
def test_frame_rules(rule, seconds, fps, frames):
    from pipeline import gen_video

    assert gen_video.frame_count({"frames": rule}, seconds, fps) == frames


def test_empty_env_values_use_defaults(monkeypatch):
    # prazna linija u .env (npr. ELEVENLABS_BASE_URL=) ne sme da obriše podrazumevanu adresu
    from pipeline import config

    monkeypatch.setattr(config, "load_env", lambda path=None: None)
    for key in ("COMFYUI_URL", "ELEVENLABS_BASE_URL", "ELEVENLABS_AUTH_HEADER", "ELEVENLABS_MODEL",
                "ELEVENLABS_TASK_URL", "ELEVENLABS_API_KEY"):
        monkeypatch.setenv(key, "")
    s = config.Settings.from_env()
    assert s.comfyui_url == "http://127.0.0.1:8188"
    assert s.elevenlabs_base_url == "https://api.elevenlabs.io/v1"
    assert s.elevenlabs_auth_header == "xi-api-key"
    assert s.elevenlabs_model == "eleven_multilingual_v2"
    assert s.elevenlabs_task_url is None and s.elevenlabs_api_key is None


def _mean_volume(path: Path) -> float:
    import re
    import subprocess

    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", out).group(1))


def test_quiet_clip_audio_is_brought_up(tmp_path):
    """H3 nekad napravi zvuk na -26 dB, a nekad na -16 dB; u montaži svaki kadar dobije istu glasnoću."""
    clip = tmp_path / "tih.mp4"
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x192:rate=24:duration=2",
           "-f", "lavfi", "-i", "anoisesrc=d=2:c=pink:a=0.02", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", "-shortest", str(clip))
    data = {"format": {"resolution": [320, 180], "fps": 24}}
    shot = {"id": "s01", "duration": 2}
    out = assemble.segment(data, tmp_path, shot, {"file": "tih.mp4"}, tmp_path / "seg.mp4", ai33_settings())
    assert _mean_volume(clip) < -30
    assert _mean_volume(out) > _mean_volume(clip) + 8
    stream = next(s for s in media.probe(out)["streams"] if s["codec_type"] == "audio")
    assert stream["sample_rate"] == "48000"
