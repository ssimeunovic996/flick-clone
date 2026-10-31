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
    assert "Opening moment: Mila turns the radio dial slowly." in p
    assert "freezes" not in p


def test_reference_sheet_prompt():
    p = prompts.reference_sheet_prompt(DATA, "deda")
    assert "Grandpa Rade" in p and "front view" in p and "no text" in p


def test_dan_412_prompts():
    data = shotlist.load(Path(__file__).resolve().parent.parent / "projects" / "dan-412")
    s01, s02 = data["shots"]
    p1 = prompts.video_prompt(data, s01, "i2v")
    assert 'Voice-over (no one on screen speaks): "Day four hundred twelve.' in p1
    assert "The astronaut: lone astronaut" in p1
    p2 = prompts.video_prompt(data, s02, "i2v")
    assert "rack focus from the foreground to the background" in p2
    assert "Faces, hair and clothing" not in p2  # u kadru nema lika, samo rukavica
    start = prompts.start_frame_prompt(data, s02)
    assert "vague red blob" in start  # obrt: na početnoj slici cvet i kantica su samo mrlje
    assert "watering can" not in start and "watering can" in p2


def test_start_frame_prompt_with_reference():
    p = prompts.start_frame_prompt(DATA, S02, with_reference=True)
    assert p.startswith("Use the character from the reference image")
    assert "not a reference sheet" in p
    assert not prompts.start_frame_prompt(DATA, S02).startswith("Use the character")


def test_end_frame_prompt_keeps_the_shot():
    shot = {"id": "s02", "duration": 5, "action": "x", "end_moment": "the flower is now in sharp focus."}
    p = prompts.end_frame_prompt({"style": "film grain"}, shot)
    assert p.startswith("Keep the exact same scene, camera position, framing and lighting")
    assert "Final moment: the flower is now in sharp focus. film grain." in p


def test_start_frame_prompt_drops_timing():
    shot = {"id": "x", "duration": 5, "action": "0-2 s: she kneels; 2-5 s: she plants"}
    assert "Opening moment: she kneels." in prompts.start_frame_prompt({}, shot)


def test_layout_prompt_says_how_the_character_is_turned():
    # Qwen inače okrene lika licem ka kameri, i kad ga layout pokazuje s leđa
    data = {"characters": {"mila": {"name": "Mila", "color": "yellow", "description": "yellow sweater"}}}
    shot = {"id": "s01", "duration": 5, "action": "she listens", "characters": ["mila"],
            "camera": {"shot": "medium_close", "lens_mm": 50}}
    p = prompts.layout_frame_prompt(data, shot, end=True, views={"mila": {"view": "back", "pose": "sit", "side": "left"}})
    assert "keep exactly the camera angle, framing (medium close-up, 50 mm lens) and" in p
    assert ("The yellow mannequin is Mila, sitting, seen from behind, with the back to the camera, "
            "on the left of the frame: yellow sweater.") in p
    assert "The yellow mannequin is Mila: yellow sweater." in prompts.layout_frame_prompt(data, shot)


def test_claude_written_prompts_are_used_as_is():
    # Test "Radio" (2026-10-31): prirodan pasus o pokretu, svetlu i zvuku daje mnogo bolji H3 od šablona
    shot = dict(S02, video_prompt="  The camera slowly pushes in as she turns the dial.  ",
                image_prompt="A lived-in old kitchen at night, tiled wall, warm lamp light.")
    for mode in ("i2v", "a2v", "ingredients"):
        assert prompts.video_prompt(DATA, shot, mode) == "The camera slowly pushes in as she turns the dial."
    assert prompts.start_frame_prompt(DATA, shot) == "A lived-in old kitchen at night, tiled wall, warm lamp light."
    with_ref = prompts.start_frame_prompt(DATA, shot, with_reference=True)
    assert with_ref.startswith("Use the character from the reference image")
    assert with_ref.endswith("warm lamp light.")


def test_layout_prompt_asks_for_a_dressed_set():
    # Qwen inače verno precrta prazan blockout, pa soba ispadne prazna kutija
    data = {"characters": {"mila": {"name": "Mila", "color": "yellow", "description": "yellow sweater"}},
            "style": "film grain", "continuity": ["Night"]}
    shot = {"id": "s01", "duration": 5, "action": "0-2 s: she listens; 2-5 s: she looks up", "characters": ["mila"],
            "location_description": "kitchen", "end_moment": "she looks at the lamp"}
    p = prompts.layout_frame_prompt(data, shot)
    assert "not an empty room" in p and "Opening moment: she listens." in p
    shot["image_prompt"] = "A cramped old kitchen with green tiles and a gas stove."
    p = prompts.layout_frame_prompt(data, shot)
    assert p.endswith("No mannequins and no plain blocks. A cramped old kitchen with green tiles and a gas stove.")
    assert "film grain" not in p and "Opening moment" not in p
    end = prompts.layout_frame_prompt(data, shot, end=True)
    assert end.endswith("gas stove. Final moment: she looks at the lamp.")
