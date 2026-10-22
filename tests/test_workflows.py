import json

import pytest

from pipeline import workflows
from tests.conftest import FAKE_WORKFLOWS


def test_load_and_check(workflows_dir):
    wf, spec = workflows.load("ltx-i2v", workflows_dir)
    assert spec["output_node"] == "41"


def test_missing_workflow_message(workflows_dir):
    with pytest.raises(workflows.WorkflowError, match="treba ne-postoji.api.json"):
        workflows.load("ne-postoji", workflows_dir)


def test_rejects_ui_format():
    with pytest.raises(workflows.WorkflowError, match="Export \\(API\\)"):
        workflows.check({"nodes": [], "links": []}, {"slots": {}})


@pytest.mark.parametrize("slots,match", [
    ({"boja": {"node": "6", "input": "text"}}, "nepoznat slot"),
    ({"prompt": {"node": "99", "input": "text"}}, "ne postoji"),
    ({"prompt": {"node": "6", "input": "tekst"}}, "nema ulaz 'tekst'"),
])
def test_check_finds_bad_slots(slots, match):
    with pytest.raises(workflows.WorkflowError, match=match):
        workflows.check(FAKE_WORKFLOWS["ltx-i2v"]["api"], {"slots": slots})


def test_apply_fills_values_and_uploads(tmp_path):
    wf = FAKE_WORKFLOWS["ltx-i2v"]["api"]
    spec = {"slots": {
        "prompt": {"node": "6", "input": "text"},
        "image": {"node": "12", "input": "image"},
        "frames": [{"node": "27", "input": "length"}, {"node": "41", "input": "frame_rate", "scale": 0.5}],
    }, "required": ["prompt"]}
    uploaded = []
    out = workflows.apply(wf, spec, {"prompt": "hello", "image": tmp_path / "a.png", "frames": 121, "seed": 5},
                          uploader=lambda p: uploaded.append(p.name) or f"flick/{p.name}")
    assert out["6"]["inputs"]["text"] == "hello"
    assert out["12"]["inputs"]["image"] == "flick/a.png"
    assert out["27"]["inputs"]["length"] == 121
    assert out["41"]["inputs"]["frame_rate"] == 60  # 121 * 0.5 zaokruženo
    assert wf["6"]["inputs"]["text"] == ""  # original ostaje netaknut
    assert uploaded == ["a.png"]


def test_apply_requires_values():
    with pytest.raises(workflows.WorkflowError, match="slot 'image'"):
        workflows.apply(FAKE_WORKFLOWS["ltx-i2v"]["api"], FAKE_WORKFLOWS["ltx-i2v"]["slots"], {"prompt": "x"})


def test_suggest_traces_prompts_through_links():
    # pozitivan prompt ide kroz LTXVConditioning do CFGGuider-a, kao u pravom LTX workflow-u
    wf = {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat", "clip": ["38", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["38", 0]}},
        "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5.safetensors"}},
        "69": {"class_type": "LTXVConditioning", "inputs": {"positive": ["6", 0], "negative": ["7", 0], "frame_rate": 24}},
        "72": {"class_type": "CFGGuider", "inputs": {"positive": ["69", 0], "negative": ["69", 1], "cfg": 3}},
        "12": {"class_type": "LoadImage", "inputs": {"image": "start.png"}},
        "13": {"class_type": "LoadImage", "inputs": {"image": "ref.png"}},
        "25": {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}},
        "27": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 768, "height": 512, "length": 97}},
        "40": {"class_type": "SaveImage", "inputs": {"filename_prefix": "preview", "images": ["8", 0]}},
        "41": {"class_type": "SaveVideo", "inputs": {"filename_prefix": "video", "video": ["39", 0]}},
    }
    s = workflows.suggest(wf)
    assert s["slots"]["prompt"] == {"node": "6", "input": "text"}
    assert s["slots"]["negative"] == {"node": "7", "input": "text"}
    assert s["slots"]["image"] == {"node": "12", "input": "image"}
    assert s["slots"]["reference"] == {"node": "13", "input": "image"}
    assert s["slots"]["seed"] == {"node": "25", "input": "noise_seed"}
    assert s["slots"]["frames"] == {"node": "27", "input": "length"}
    assert s["slots"]["fps"] == {"node": "69", "input": "frame_rate"}
    assert s["output_node"] == "41"
    assert s["required"] == ["prompt", "image"]
    workflows.check(wf, s)  # predlog mora proći proveru


def test_example_slots_are_well_formed():
    from pathlib import Path
    for path in (Path(__file__).resolve().parent.parent / "comfy-workflows" / "primeri").glob("*.slots.json"):
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert set(spec["slots"]) <= workflows.KNOWN_SLOTS, path.name
        assert set(spec["required"]) <= set(spec["slots"]), path.name


def test_minimax_h3_workflow_fills_real_nodes():
    # pravi workflow za Stefanov MiniMax H3 (LoRA od 4 koraka): 9:16 i 5 s daju 736x1280 i 124 frejma
    from pathlib import Path

    from pipeline import gen_video, shotlist

    wf, spec = workflows.load("minimax-h3")
    w, h = (shotlist.snap(v, spec["size_multiple"]) for v in (720, 1280))
    values = {"prompt": "a sprout on Mars", "image": Path("s01.png"), "seed": 7, "width": w, "height": h,
              "frames": gen_video.frame_count(spec, 5, 24), "fps": 24, "filename_prefix": "flick/dan-412/s01"}
    filled = workflows.apply(wf, spec, values, uploader=lambda p: f"flick/{p.name}")
    i2v, scale, save = filled["9"]["inputs"], filled["8"]["inputs"], filled["17"]["inputs"]
    assert (i2v["width"], i2v["height"], i2v["length"]) == (736, 1280, 124)
    assert (scale["width"], scale["height"]) == (736, 1280)
    assert i2v["prompt"] == "a sprout on Mars" and filled["7"]["inputs"]["image"] == "flick/s01.png"
    assert filled["10"]["inputs"]["noise_seed"] == 7
    assert save["filename_prefix"] == "flick/dan-412/s01" and save["frame_rate"] == 24
    assert "4step" in filled["2"]["inputs"]["lora_name"]
    assert "last_frame" not in i2v  # bez krajnje slike H3 dobija samo početnu

    values["end_image"] = Path("s02_kraj.png")
    filled = workflows.apply(wf, spec, values, uploader=lambda p: f"flick/{p.name}")
    assert filled["9"]["inputs"]["last_frame"] == ["19", 0]
    assert filled["18"]["inputs"]["image"] == "flick/s02_kraj.png"
    assert (filled["19"]["inputs"]["width"], filled["19"]["inputs"]["height"]) == (736, 1280)


def test_suggest_minimax_h3():
    wf, _ = workflows.load("minimax-h3")
    s = workflows.suggest(wf)
    assert s["frames"] == "17k+5"
    assert s["slots"]["prompt"] == {"node": "9", "input": "prompt"}
    assert s["slots"]["image"] == {"node": "7", "input": "image"}
    assert s["output_node"] == "17"


def test_slika_without_reference_unlinks_image():
    # bez reference sheet-a Qwen pravi sliku iz teksta, pa veza ka LoadImage mora da nestane
    wf, spec = workflows.load("slika")
    filled = workflows.apply(wf, spec, {"prompt": "astronaut", "width": 1536, "height": 1024})
    assert "images.image_1" not in filled["7"]["inputs"] and "images.image_2" not in filled["7"]["inputs"]
    assert (filled["8"]["inputs"]["width"], filled["8"]["inputs"]["height"]) == (1536, 1024)
    assert "images.image_1" in wf["7"]["inputs"]  # original ostaje netaknut


def test_slika_with_reference_keeps_link():
    from pathlib import Path

    wf, spec = workflows.load("slika")
    filled = workflows.apply(wf, spec, {"prompt": "astronaut", "reference": Path("sheet.png")},
                             uploader=lambda p: f"flick/{p.name}")
    assert filled["7"]["inputs"]["images.image_1"] == ["6", 0]
    assert filled["6"]["inputs"]["image"] == "flick/sheet.png"
    assert "images.image_2" not in filled["7"]["inputs"]

    # Layout to Render: layout iz Blendera je prva slika (ona se menja), sheet lika druga
    filled = workflows.apply(wf, spec, {"prompt": "astronaut", "reference": Path("s01_start.png"),
                                        "reference2": Path("sheet.png")}, uploader=lambda p: f"flick/{p.name}")
    assert filled["7"]["inputs"]["images.image_2"] == ["12", 0]
    assert filled["12"]["inputs"]["image"] == "flick/sheet.png"


def test_unlink_target_must_exist():
    spec = {"slots": {}, "unlink_if_empty": {"reference": {"node": "99", "input": "x"}}}
    with pytest.raises(workflows.WorkflowError, match="99"):
        workflows.check({"1": {"class_type": "X", "inputs": {}}}, spec)
