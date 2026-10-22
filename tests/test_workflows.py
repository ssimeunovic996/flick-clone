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
