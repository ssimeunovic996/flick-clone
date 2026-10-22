"""Pokreti kamere i .ops.json scena, bez Blendera (čista matematika)."""

import math
from pathlib import Path

import pytest

from blender import camera_moves as cm
from blender import scene_ops

KUHINJA = Path(__file__).resolve().parent.parent / "blender" / "primeri" / "kuhinja.ops.json"
BASE = {"pos": (0.0, 1.6, 5.0), "target": (0.0, 1.6, 0.0), "lens": 35.0, "roll": 0.0}


def close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def dist(a, b):
    return cm.length(cm.sub(a, b))


def test_dolly_in_moves_forward_and_keeps_direction():
    s = cm.MOVES["dolly_in"](BASE, {"distance": 2}, 1.0)
    assert close(s["pos"], (0, 1.6, 3))
    assert close(cm.norm(cm.sub(s["target"], s["pos"])), (0, 0, -1))


def test_dolly_zoom_keeps_subject_size():
    s = cm.MOVES["dolly_zoom"](BASE, {"distance": 2.5}, 1.0)
    assert math.isclose(dist(s["pos"], s["target"]), 2.5)
    # veličina subjekta je srazmerna lens / udaljenost
    assert math.isclose(s["lens"] / 2.5, BASE["lens"] / 5.0)


def test_orbit_keeps_radius_and_target():
    s = cm.MOVES["orbit"](BASE, {"degrees": 90}, 1.0)
    assert close(s["target"], BASE["target"])
    assert math.isclose(dist(s["pos"], s["target"]), 5.0)
    assert close(s["pos"], (5, 1.6, 0))  # +90° suprotno od kazaljke gledano odozgo


def test_pan_left_turns_view_to_the_left():
    s = cm.MOVES["pan_left"](BASE, {"degrees": 90}, 1.0)
    assert close(s["pos"], BASE["pos"])
    assert close(cm.norm(cm.sub(s["target"], s["pos"])), (-1, 0, 0))


def test_crane_up_keeps_aim():
    s = cm.MOVES["crane_up"](BASE, {"height": 2}, 1.0)
    assert close(s["pos"], (0, 3.6, 5)) and close(s["target"], BASE["target"])


def test_tilt_up():
    s = cm.MOVES["tilt_up"](BASE, {"degrees": 45}, 1.0)
    d = cm.norm(cm.sub(s["target"], s["pos"]))
    assert math.isclose(d[1], math.sin(math.radians(45)), abs_tol=1e-6)


def test_spiral_goes_closer_and_higher():
    s = cm.MOVES["spiral"](BASE, {"degrees": 180, "radius_factor": 0.5, "height": 1}, 1.0)
    assert close(s["pos"], (0, 2.6, -2.5))


def test_path_visits_points_evenly():
    move = {"points": [[0, 1.6, 3], [2, 1.6, 3]], "target": [0, 1, 0]}
    assert close(cm.MOVES["path"](BASE, move, 0.5)["pos"], (0, 1.6, 3))  # 2 m od 4 m puta
    assert close(cm.MOVES["path"](BASE, move, 1.0)["pos"], (2, 1.6, 3))


def test_moves_run_in_sequence():
    moves = [{"move": "dolly_in", "distance": 1, "start": 0, "end": 2, "ease": "linear"},
             {"move": "crane_up", "height": 1, "start": 2, "end": 4, "ease": "linear"}]
    assert close(cm.camera_at(BASE, moves, 1)["pos"], (0, 1.6, 4.5))
    assert close(cm.camera_at(BASE, moves, 3)["pos"], (0, 2.1, 4))
    assert close(cm.camera_at(BASE, moves, 9)["pos"], (0, 2.6, 4))


def test_ease_in_out_is_smooth_at_ends():
    assert cm.ease(0) == 0 and cm.ease(1) == 1 and cm.ease(0.5) == 0.5
    assert cm.ease(0.05) < 0.05


def test_handheld_is_small_and_repeatable():
    a = cm.handheld(BASE, 0.02, 1.234)
    assert a == cm.handheld(BASE, 0.02, 1.234)
    assert 0 < dist(a["pos"], BASE["pos"]) < 0.05


def test_example_scene_loads():
    stage = scene_ops.Stage.load(KUHINJA)
    assert set(stage.shots) == {"s01", "s02", "s03"}
    assert stage.frame_count("s01") == 121
    assert "kadar s03: kamera kamera_rame, 5 s, 121 frejmova, 1280x720, pokreti: dolly_in" in stage.summary()


def test_errors_are_collected():
    stage = scene_ops.Stage.from_ops([
        {"op": "add", "id": "a", "shape": "pyramid"},
        {"op": "add", "id": "b"},
        {"op": "add", "id": "b"},
        {"op": "remove", "id": "x"},
        {"op": "camera_move", "shot": "s9", "move": "fly"},
        {"op": "shot", "id": "s1", "camera": "b", "duration": 5},
        {"op": "teleport"},
    ])
    text = "\n".join(stage.errors)
    for expected in ["shape mora biti", "'b' već postoji", "remove: objekat 'x'", "nepoznat pokret 'fly'",
                     "camera 'b' nije kamera", "nepoznata operacija 'teleport'"]:
        assert expected in text


def test_figure_follows_path_and_faces_where_it_walks():
    stage = scene_ops.Stage.from_ops([
        {"op": "add", "id": "cam", "type": "camera", "pos": [0, 1.6, 5], "look_at": [0, 1, 0]},
        {"op": "add", "id": "marko", "type": "figure", "pos": [0, 0, 0], "facing": 0},
        {"op": "shot", "id": "s1", "camera": "cam", "duration": 4},
        {"op": "path", "shot": "s1", "id": "marko", "points": [[2, 0, 0]], "start": 0, "end": 2},
    ])
    assert not stage.errors
    mid = stage.object_at("s1", "marko", 1.0)
    assert close(mid["pos"], (1, 0, 0))
    assert math.isclose(mid["facing"], 90)  # hoda ka +X
    end = stage.object_at("s1", "marko", 3.0)
    assert close(end["pos"], (2, 0, 0)) and math.isclose(end["facing"], 90)


def test_keyframes_interpolate_and_turn_the_short_way():
    stage = scene_ops.Stage.from_ops([
        {"op": "add", "id": "cam", "type": "camera", "pos": [0, 1.6, 5]},
        {"op": "add", "id": "ana", "type": "figure", "pos": [0, 0, 0], "facing": 170},
        {"op": "shot", "id": "s1", "camera": "cam", "duration": 2},
        {"op": "keyframe", "shot": "s1", "id": "ana", "t": 2, "pos": [1, 0, 0], "facing": -170, "ease": "linear"},
    ])
    st = stage.object_at("s1", "ana", 1.0)
    assert close(st["pos"], (0.5, 0, 0))
    assert math.isclose(st["facing"], 180)  # 170 -> 190, ne 170 -> -170 preko nule


def test_camera_looks_at_figure_eyes():
    stage = scene_ops.Stage.from_ops([
        {"op": "add", "id": "mila", "type": "figure", "pos": [0, 0, 0], "height": 1.6},
        {"op": "add", "id": "cam", "type": "camera", "pos": [0, 1.5, 3], "look_at": "mila"},
        {"op": "shot", "id": "s1", "camera": "cam", "duration": 1},
    ])
    assert close(stage.camera_at("s1", 0)["target"], (0, 1.6 * 0.92, 0))


def test_camera_rot_matches_threejs_convention():
    # three.js kamera sa rot [0, 90, 0] gleda ka -X
    stage = scene_ops.Stage.from_ops([
        {"op": "add", "id": "cam", "type": "camera", "pos": [0, 1, 0], "rot": [0, 90, 0]},
        {"op": "shot", "id": "s1", "camera": "cam", "duration": 1},
    ])
    assert close(stage.camera_at("s1", 0)["target"], (-1, 1, 0))


@pytest.mark.parametrize("value,expected", [("#ffffff", (1.0, 1.0, 1.0)), ("#000000", (0.0, 0.0, 0.0)), ("nema", None)])
def test_hex_color(value, expected):
    rgb = scene_ops.hex_color(value)
    if expected:
        assert close(rgb, expected)
    else:
        assert len(rgb) == 3
    assert close(scene_ops.hex_color("yellow"), scene_ops.hex_color(scene_ops.COLORS["yellow"]))
