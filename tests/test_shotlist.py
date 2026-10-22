import json
from pathlib import Path

import pytest

from pipeline import shotlist

PRIMER = Path(__file__).resolve().parent.parent / "projects" / "primer"


def test_primer_shotlist_is_valid():
    data = shotlist.load(PRIMER)
    assert [s["id"] for s in data["shots"]] == ["s01", "s02", "s03"]


def test_validate_lists_every_problem():
    data = {
        "format": {"fps": 100},
        "characters": {"mila": {}},
        "shots": [
            {"id": "s01", "duration": 0, "action": "", "characters": ["marko"],
             "dialogue": [{"who": "ana", "text": ""}], "control": {"type": "normal"}, "status": "gotovo"},
            {"id": "s01", "duration": 5, "action": "x"},
        ],
    }
    errors = "\n".join(shotlist.validate(data))
    for expected in ["fps", "duration", "action", "'marko'", "'ana'", "text je prazan", "control.type",
                     "control.video", "status 'gotovo'", "se ponavlja", "nema model"]:
        assert expected in errors


def test_load_raises_with_path(tmp_path):
    (tmp_path / "shotlist.json").write_text(json.dumps({"shots": []}))
    with pytest.raises(shotlist.ShotlistError, match="shots mora biti"):
        shotlist.load(tmp_path)


@pytest.mark.parametrize("seconds,fps,frames", [(5, 24, 121), (4, 24, 97), (2, 24, 49), (1, 24, 25), (5, 25, 129)])
def test_ltx_frames(seconds, fps, frames):
    assert shotlist.ltx_frames(seconds, fps) == frames
    assert (frames - 1) % 8 == 0


@pytest.mark.parametrize("value,expected", [(720, 736), (704, 704), (1280, 1280), (180, 192), (10, 32)])
def test_snap(value, expected):
    assert shotlist.snap(value) == expected


def test_status_only_moves_forward():
    shot = {"status": "video_ok"}
    shotlist.advance(shot, "audio_ok")
    assert shot["status"] == "video_ok"
    shotlist.advance(shot, "approved")
    assert shot["status"] == "approved"


def test_latest_take_prefers_chosen():
    shot = {"takes": [{"n": 1, "chosen": True}, {"n": 2}]}
    assert shotlist.latest_take(shot)["n"] == 1
    assert shotlist.latest_take({"takes": [{"n": 1}, {"n": 2}]})["n"] == 2
    assert shotlist.latest_take({"takes": [{"n": 1}]}, approved_only=True) is None


def test_save_keeps_serbian_letters(tmp_path):
    shotlist.save(tmp_path, {"film": "Čuvar šume"})
    assert "Čuvar šume" in (tmp_path / "shotlist.json").read_text(encoding="utf-8")
