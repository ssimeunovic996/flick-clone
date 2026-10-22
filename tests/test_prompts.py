from pathlib import Path

from pipeline import prompts, shotlist

DATA = shotlist.load(Path(__file__).resolve().parent.parent / "projects" / "primer")
S01, S02, S03 = DATA["shots"]


def test_order_of_parts():
    p = prompts.video_prompt(DATA, S02, "i2v")
    order = [p.index(x) for x in ("Style:", "Mila:", "Location:", "Camera:", "Action:", "Mila says:", "Continuity:")]
    assert order == sorted(order)
    assert "medium close-up, static camera, 50mm lens" in p
    assert "Faces, hair and clothing stay identical" in p


def test_narrator_is_voice_over():
    p = prompts.video_prompt(DATA, S01, "a2v")
    assert 'Voice-over (no one on screen speaks): "Svake noći' in p
    assert "Lip movements" not in p  # niko u kadru ne govori


def test_a2v_adds_lip_sync_line():
    assert "Lip movements of Mila match the audio exactly." in prompts.video_prompt(DATA, S02, "a2v")
    assert "Lip movements" not in prompts.video_prompt(DATA, S02, "i2v")


def test_control_mode_names_figure_colors():
    p = prompts.video_prompt(DATA, S03, "control")
    assert "Grandpa Rade (the blue figure in the control video)" in p
    assert "Mila (the yellow figure in the control video)" in p
    assert p.index("Follow the camera movement") < p.index("Grandpa Rade")


def test_ingredients_prefix():
    p = prompts.video_prompt(DATA, S02, "ingredients")
    assert p.startswith("Reference sheet: Mila: woman in her early 30s")
    assert "Generated video: Style:" in p


def test_start_frame_uses_first_beat_only():
    p = prompts.start_frame_prompt(DATA, S02)
    assert "Opening moment: 0-2 s: Mila turns the radio dial slowly." in p
    assert "freezes" not in p


def test_reference_sheet_prompt():
    p = prompts.reference_sheet_prompt(DATA, "deda")
    assert "Grandpa Rade" in p and "front view" in p and "no text" in p
