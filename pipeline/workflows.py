"""ComfyUI workflow šabloni sa "slotovima".

Svaki workflow se čuva kao par fajlova u comfy-workflows/:

- <ime>.api.json    workflow izvezen iz ComfyUI-ja u API formatu (Workflow > Export (API))
- <ime>.slots.json  koja polja pipeline popunjava (prompt, slika, zvuk, seed, veličina...)

Primer i objašnjenje formata: comfy-workflows/README.md.
Pregled čvorova izvezenog workflow-a i predlog slots fajla:

    python -m pipeline.workflows inspect comfy-workflows/ltx-i2v.api.json
    python -m pipeline.workflows suggest comfy-workflows/ltx-i2v.api.json > comfy-workflows/ltx-i2v.slots.json

Predlog je samo polazna tačka; proveri ga pre upotrebe.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from .config import WORKFLOWS_DIR

KNOWN_SLOTS = {
    "prompt", "negative", "image", "audio", "control_video", "reference",
    "seed", "width", "height", "frames", "fps", "length_seconds", "filename_prefix",
}
UPLOAD_SLOTS = {"image", "audio", "control_video", "reference"}


class WorkflowError(ValueError):
    pass


def load(name: str, directory: Path = WORKFLOWS_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    api_path = directory / f"{name}.api.json"
    slots_path = directory / f"{name}.slots.json"
    if not api_path.exists() or not slots_path.exists():
        raise WorkflowError(
            f"workflow '{name}' ne postoji: treba {api_path.name} i {slots_path.name} u {directory}"
        )
    workflow = json.loads(api_path.read_text(encoding="utf-8"))
    spec = json.loads(slots_path.read_text(encoding="utf-8"))
    check(workflow, spec, name)
    return workflow, spec


def check(workflow: dict[str, Any], spec: dict[str, Any], name: str = "workflow") -> None:
    if "nodes" in workflow and "links" in workflow:
        raise WorkflowError(f"{name}: ovo je UI format; izvezi ga sa Workflow > Export (API)")
    for slot, targets in spec.get("slots", {}).items():
        if slot not in KNOWN_SLOTS:
            raise WorkflowError(f"{name}: nepoznat slot '{slot}' (poznati: {sorted(KNOWN_SLOTS)})")
        for t in _targets(targets):
            node = workflow.get(str(t["node"]))
            if node is None:
                raise WorkflowError(f"{name}: slot '{slot}' pokazuje na čvor {t['node']} koji ne postoji")
            if t["input"] not in node.get("inputs", {}):
                raise WorkflowError(
                    f"{name}: čvor {t['node']} ({node.get('class_type')}) nema ulaz '{t['input']}'"
                )
    for slot, targets in spec.get("unlink_if_empty", {}).items():
        for t in _targets(targets):
            if str(t["node"]) not in workflow:
                raise WorkflowError(f"{name}: unlink_if_empty '{slot}' pokazuje na čvor {t['node']} koji ne postoji")
    out = spec.get("output_node")
    if out is not None and str(out) not in workflow:
        raise WorkflowError(f"{name}: output_node {out} ne postoji")


def apply(workflow: dict[str, Any], spec: dict[str, Any], values: dict[str, Any],
          uploader: Callable[[Path], str] | None = None) -> dict[str, Any]:
    """Vraća kopiju workflow-a sa upisanim vrednostima. Putanje za upload slotove šalje uploader."""
    wf = copy.deepcopy(workflow)
    slots = spec.get("slots", {})
    for slot in spec.get("required", []):
        if values.get(slot) is None:
            raise WorkflowError(f"workflow traži vrednost za slot '{slot}'")
    for slot, targets in spec.get("unlink_if_empty", {}).items():
        if values.get(slot) is None:
            for t in _targets(targets):  # npr. referentna slika koja nije data: čvor ostaje bez te veze
                wf[str(t["node"])]["inputs"].pop(t["input"], None)
    for slot, value in values.items():
        if value is None or slot not in slots:
            continue
        if slot in UPLOAD_SLOTS:
            if uploader is None:
                raise WorkflowError(f"slot '{slot}' traži upload, a uploader nije zadat")
            value = uploader(Path(value))
        for t in _targets(slots[slot]):
            wf[str(t["node"])]["inputs"][t["input"]] = _scaled(value, t)
    return wf


def _targets(targets: Any) -> list[dict[str, Any]]:
    return targets if isinstance(targets, list) else [targets]


def _scaled(value: Any, target: dict[str, Any]) -> Any:
    """Opciono množenje i zaokruživanje (npr. kad čvor traži dužinu u drugoj jedinici)."""
    if isinstance(value, (int, float)) and "scale" in target:
        value = value * target["scale"]
        return int(round(value)) if target.get("int", True) else value
    return value


def inspect(path: Path) -> str:
    wf = json.loads(Path(path).read_text(encoding="utf-8"))
    if "nodes" in wf and "links" in wf:
        return "Ovo je UI format. U ComfyUI-ju izaberi Workflow > Export (API)."
    lines = []
    for nid in sorted(wf, key=lambda k: int(k) if str(k).isdigit() else 0):
        node = wf[nid]
        title = node.get("_meta", {}).get("title", "")
        lines.append(f"[{nid}] {node.get('class_type')}  {title}")
        for key, val in node.get("inputs", {}).items():
            if isinstance(val, list):
                continue  # veza sa drugim čvorom
            shown = val if not isinstance(val, str) or len(val) < 80 else val[:77] + "..."
            lines.append(f"      {key} = {shown!r}")
    return "\n".join(lines)


SIMPLE_INPUTS = {
    "seed": "seed", "noise_seed": "seed", "width": "width", "height": "height",
    "length": "frames", "num_frames": "frames", "frames": "frames", "frame_count": "frames",
    "frame_rate": "fps", "fps": "fps", "filename_prefix": "filename_prefix",
}
LOADERS = {"LoadImage": ("image", "image"), "LoadAudio": ("audio", "audio"),
           "VHS_LoadVideo": ("control_video", "video"), "LoadVideo": ("control_video", "file")}


def _text_source(wf: dict[str, Any], start: Any, side: str, seen: set[str] | None = None) -> str | None:
    """Prati vezu unazad dok ne nađe čvor sa tekstom prompta. Kroz čvorove koji imaju i
    positive i negative ulaz (npr. LTXVConditioning) ide samo istom stranom."""
    seen = seen or set()
    if not isinstance(start, list) or str(start[0]) in seen:
        return None
    nid = str(start[0])
    seen.add(nid)
    inputs = wf.get(nid, {}).get("inputs", {})
    for key in ("text", "prompt"):
        if isinstance(inputs.get(key), str):
            return nid
    other = "negative" if side == "positive" else "positive"
    links = [inputs[side]] if side in inputs else []
    links += [v for k, v in inputs.items() if k not in (side, other)]
    for val in links:
        found = _text_source(wf, val, side, seen)
        if found:
            return found
    return None


def suggest(wf: dict[str, Any]) -> dict[str, Any]:
    """Predlog slots fajla po imenima čvorova i ulaza. Slika za referencu ide u 'image';
    ako workflow ima dve LoadImage, druga postaje 'reference'."""
    slots: dict[str, list[dict[str, Any]]] = {}

    def add(slot: str, nid: str, inp: str) -> None:
        target = {"node": nid, "input": inp}
        if target not in slots.setdefault(slot, []):
            slots[slot].append(target)

    for nid, node in wf.items():
        inputs = node.get("inputs", {})
        for key in ("positive", "negative"):
            src = _text_source(wf, inputs.get(key), key)
            if src:
                text_key = "text" if "text" in wf[src]["inputs"] else "prompt"
                add("prompt" if key == "positive" else "negative", src, text_key)
    images = 0
    out = None
    for nid in sorted(wf, key=lambda k: int(k) if str(k).isdigit() else 0):
        node = wf[nid]
        cls = node.get("class_type", "")
        inputs = node.get("inputs", {})
        if cls in LOADERS:
            slot, inp = LOADERS[cls]
            if slot == "image":
                images += 1
                slot = "image" if images == 1 else "reference"
            if inp in inputs:
                add(slot, nid, inp)
        for key, val in inputs.items():
            if key in SIMPLE_INPUTS and not isinstance(val, list):
                add(SIMPLE_INPUTS[key], nid, key)
        if "filename_prefix" in inputs and ("Video" in cls or out is None):
            out = nid
    if "prompt" not in slots:
        for nid, node in wf.items():
            inputs = node.get("inputs", {})
            key = next((k for k in ("text", "prompt") if isinstance(inputs.get(k), str)), None)
            if key:
                add("prompt", nid, key)
                break
    minimax = any(str(n.get("class_type", "")).startswith("MiniMaxH3") for n in wf.values())
    result: dict[str, Any] = {
        "slots": {k: v[0] if len(v) == 1 else v for k, v in slots.items()},
        "required": [s for s in ("prompt", "image", "audio", "control_video") if s in slots],
        "output_node": out,
        "prompt_mode": "i2v",
        "frames": "17k+5" if minimax else "8k+1",  # MiniMax H3 traži 17k+5 frejmova
        "size_multiple": 32,
        "max_seconds": 10,
    }
    return result


if __name__ == "__main__":
    from .config import utf8_output

    utf8_output()
    if len(sys.argv) == 3 and sys.argv[1] == "inspect":
        print(inspect(Path(sys.argv[2])))
    elif len(sys.argv) == 3 and sys.argv[1] == "suggest":
        wf = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        print(json.dumps(suggest(wf), indent=2, ensure_ascii=False))
    else:
        print("upotreba: python -m pipeline.workflows inspect|suggest <fajl.api.json>")
