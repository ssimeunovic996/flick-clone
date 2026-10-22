"""Pravljenje promptova po Flick obrascu (opis u pipeline/prompt_template.md).

Redosled delova: stil, uloga referenci, boja figure -> lik, kamera, radnja po sekundama,
ko govori, pravila kontinuiteta. Video modeli rade bolje sa kratkim, jasnim rečenicama
na engleskom, pa su i šabloni na engleskom.
"""

from __future__ import annotations

from typing import Any

from . import shotlist

SHOT_SIZES = {
    "extreme_wide": "extreme wide shot", "wide": "wide shot", "full": "full shot",
    "medium": "medium shot", "medium_close": "medium close-up", "close": "close-up",
    "extreme_close": "extreme close-up", "over_shoulder": "over-the-shoulder shot",
    "insert": "insert shot",
}
MOVES = {
    "static": "static camera", "dolly_in": "slow dolly in", "dolly_out": "slow dolly out",
    "dolly_zoom": "dolly zoom", "crane_up": "crane up", "crane_down": "crane down",
    "pan_left": "pan left", "pan_right": "pan right", "orbit": "orbit around the subject",
    "tracking": "tracking shot following the subject", "handheld": "subtle handheld movement",
    "spiral": "spiral move around the subject",
    "rack_focus": "static camera, rack focus from the foreground to the background",
}


def _name(data: dict[str, Any], cid: str) -> str:
    return data.get("characters", {}).get(cid, {}).get("name", cid.capitalize())


def camera_line(shot: dict[str, Any]) -> str:
    cam = shot.get("camera", {})
    parts = [SHOT_SIZES.get(cam.get("shot", ""), cam.get("shot", ""))]
    parts.append(MOVES.get(cam.get("move", "static"), cam.get("move", "")))
    if cam.get("lens_mm"):
        parts.append(f"{cam['lens_mm']}mm lens")
    return "Camera: " + ", ".join(p for p in parts if p) + "."


def character_lines(data: dict[str, Any], shot: dict[str, Any], with_colors: bool) -> list[str]:
    lines = []
    for cid in shot.get("characters", []):
        ch = data["characters"][cid]
        desc = ch.get("description", "")
        color = ch.get("color")
        prefix = f"{_name(data, cid)}"
        if with_colors and color:
            prefix += f" (the {color} figure in the control video)"
        lines.append(f"{prefix}: {desc}".strip().rstrip(":") + ".")
    return lines


def dialogue_lines(data: dict[str, Any], shot: dict[str, Any], audio_driven: bool) -> list[str]:
    lines = []
    for line in shot.get("dialogue", []):
        who = line["who"]
        text = line["text"].strip()
        if who == shotlist.NARRATOR:
            lines.append(f'Voice-over (no one on screen speaks): "{text}"')
        else:
            lines.append(f'{_name(data, who)} says: "{text}"')
    if lines and audio_driven:
        speakers = [_name(data, l["who"]) for l in shot["dialogue"] if l["who"] != shotlist.NARRATOR]
        if speakers:
            lines.append(f"Lip movements of {', '.join(dict.fromkeys(speakers))} match the audio exactly.")
    return lines


def video_prompt(data: dict[str, Any], shot: dict[str, Any], mode: str = "i2v") -> str:
    """mode: i2v (početna slika), a2v (zvuk vodi usne), ingredients (reference sheet), control (3D)."""
    with_colors = mode == "control" or shot.get("control") is not None
    parts: list[str] = []
    if data.get("style"):
        parts.append(f"Style: {data['style']}.")
    if with_colors:
        parts.append("Follow the camera movement, framing and blocking of the control video exactly. "
                     "The colored figures are placeholders for the characters below.")
    parts += character_lines(data, shot, with_colors)
    if shot.get("location_description"):
        parts.append(f"Location: {shot['location_description']}.")
    parts.append(camera_line(shot))
    parts.append(f"Action: {shot['action'].strip().rstrip('.')}.")
    parts += dialogue_lines(data, shot, audio_driven=mode == "a2v")
    rules = list(data.get("continuity", []))
    if shot.get("characters"):
        rules.append("Faces, hair and clothing stay identical to the references")
    if rules:
        parts.append("Continuity: " + "; ".join(r.rstrip(".") for r in rules) + ".")
    body = " ".join(parts)
    if mode == "ingredients":
        sheet = " ".join(character_lines(data, shot, with_colors=False)) or "the subject"
        return f"Reference sheet: {sheet} Generated video: {body}"
    return body


def start_frame_prompt(data: dict[str, Any], shot: dict[str, Any]) -> str:
    """Prompt za početnu sliku kadra (prvi frejm), za modele slike."""
    parts = []
    if data.get("style"):
        parts.append(f"{data['style']}.")
    if shot.get("location_description"):
        parts.append(f"{shot['location_description']}.")
    parts += character_lines(data, shot, with_colors=False)
    first_beat = shot["action"].split(";")[0].strip().rstrip(".")
    parts.append(f"Opening moment: {first_beat}.")
    cam = shot.get("camera", {})
    if cam.get("shot"):
        parts.append(f"{SHOT_SIZES.get(cam['shot'], cam['shot']).capitalize()}.")
    parts.append("Cinematic still frame, natural light, no text.")
    return " ".join(parts)


def reference_sheet_prompt(data: dict[str, Any], cid: str) -> str:
    ch = data["characters"][cid]
    style = data.get("style", "cinematic realism")
    return (f"Character reference sheet, {style}. {_name(data, cid)}: {ch.get('description', '')}. "
            "Full body front view, side view and back view, plus a close-up of the head, "
            "same outfit in every view, neutral grey background, even studio light, no text.")
