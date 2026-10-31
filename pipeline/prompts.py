"""Pravljenje promptova po Flick obrascu (opis u pipeline/prompt_template.md).

Najbolje rezultate daje prompt koji Claude napiše za svaki kadar posebno: `image_prompt`
(početna slika) i `video_prompt` (video) u `shotlist.json`. Kad postoje, koriste se
doslovno. Šablon ispod je rezervna varijanta za kadrove bez njih.

Redosled delova šablona: stil, uloga referenci, boja figure -> lik, kamera, radnja po
sekundama, ko govori, pravila kontinuiteta. Video modeli rade bolje sa jasnim rečenicama na
engleskom, pa su i šabloni na engleskom.
"""

from __future__ import annotations

import re
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


def character_lines(data: dict[str, Any], shot: dict[str, Any], with_colors: bool,
                    color_source: str = "the control video") -> list[str]:
    lines = []
    for cid in shot.get("characters", []):
        ch = data["characters"][cid]
        desc = ch.get("description", "")
        color = ch.get("color")
        prefix = f"{_name(data, cid)}"
        if with_colors and color:
            prefix += f" (the {color} figure in {color_source})"
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


def custom(shot: dict[str, Any], key: str) -> str:
    """Prompt koji je Claude napisao za kadar (`image_prompt` ili `video_prompt`), ili ""."""
    text = shot.get(key)
    return text.strip() if isinstance(text, str) else ""


REFERENCE_PREFIX = ("Use the character from the reference image, with the exact same face, hair "
                    "and outfit, and place them in a new single scene (one image, not a reference sheet).")
REFERENCE_PREFIX_MANY = ("Use the people from the reference image (their reference sheets side by side), with "
                         "the exact same faces, hair and outfits, and place them together in a new single scene "
                         "(one image, not a reference sheet).")


def video_prompt(data: dict[str, Any], shot: dict[str, Any], mode: str = "i2v") -> str:
    """mode: i2v (početna slika), a2v (zvuk vodi usne), ingredients (reference sheet), control (3D).
    `video_prompt` kadra ide doslovno, u svakom modu."""
    if custom(shot, "video_prompt"):
        return custom(shot, "video_prompt")
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


def start_frame_prompt(data: dict[str, Any], shot: dict[str, Any], with_reference: bool = False) -> str:
    """Prompt za početnu sliku kadra (prvi frejm), za modele slike. Sa referencom (reference sheet)
    model mora da uzme lik sa sheet-a, ali da napravi jednu scenu, a ne novi sheet.
    `image_prompt` kadra zamenjuje šablon; rečenica o referenci se dodaje sama."""
    many = len(shot.get("characters", [])) > 1
    parts = [REFERENCE_PREFIX_MANY if many else REFERENCE_PREFIX] if with_reference else []
    if custom(shot, "image_prompt"):
        return " ".join(parts + [custom(shot, "image_prompt")])
    if data.get("style"):
        parts.append(f"{data['style']}.")
    if shot.get("location_description"):
        parts.append(f"{shot['location_description']}.")
    parts += character_lines(data, shot, with_colors=False)
    parts.append(f"Opening moment: {_beat(shot, 0)}.")
    cam = shot.get("camera", {})
    if cam.get("shot"):
        parts.append(f"{SHOT_SIZES.get(cam['shot'], cam['shot']).capitalize()}.")
    parts.append("Cinematic still frame, natural light, no text.")
    return " ".join(parts)


def _beat(shot: dict[str, Any], index: int) -> str:
    """Prvi (0) ili poslednji (-1) deo radnje, bez oznake vremena ("0-2 s:" je za video)."""
    beat = shot["action"].split(";")[index].strip().rstrip(".")
    return re.sub(r"^\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*s:\s*", "", beat)


VIEWS = {"front": "facing the camera", "back": "seen from behind, with the back to the camera",
         "profile": "seen in profile"}
POSES = {"sit": "sitting", "stand": "standing"}
SIDES = {"left": "on the left of the frame", "center": "in the center of the frame", "right": "on the right of the frame"}
DEPTHS = {"foreground": "in the foreground very close to the camera, partly out of focus",
          "background": "further back in the background"}


def _placement(info: dict[str, str] | None) -> str:
    """", sitting, facing the camera, on the left of the frame" iz gen_layout.views."""
    info = info or {}
    words = [POSES.get(info.get("pose", "")), VIEWS.get(info.get("view", "")), SIDES.get(info.get("side", "")),
             DEPTHS.get(info.get("depth", ""))]
    return "".join(f", {w}" for w in words if w)


def layout_frame_prompt(data: dict[str, Any], shot: dict[str, Any], end: bool = False,
                        with_reference: bool = False, legend: list[str] | None = None,
                        views: dict[str, dict[str, str]] | None = None) -> str:
    """Layout to Render: slika 1 je gruba slika iz Blendera i model je pretvara u pravu fotografiju
    istog kadriranja, a slika 2 je sheet likova. Isto za početnu i krajnju sliku kadra.

    Proba na Qwen Image 2.1 (2026-10-22): layout mora biti prva slika, a figure se moraju nazvati
    zamenama ("placeholder ... remove it"), inače model ostavi lutku i doda lika pored nje. Za krajnju
    sliku početna slika kao druga slika ne valja: model je prepiše i ne pomeri kameru.
    `legend` su rečenice iz .ops.json (polje `label`) koje kažu šta je koji blok, a `views` kako
    kamera vidi koju figuru (gen_layout.views: okret, poza, mesto u kadru), jer model inače okrene
    lika licem ka kameri i postavi ga po svom.
    Proba "Radio" (2026-10-31): Qwen verno precrta prazan blockout, pa soba ispadne prazna kutija.
    Zato prompt traži da model sam doda nameštaj i detalje iz opisa (`image_prompt` kadra, ako postoji).
    """
    moment_of = "the last moment of a film shot" if end else "a film shot"
    cam = shot.get("camera") or {}
    framing = "framing"  # bez veličine kadra Qwen često raširi kadar u srednji plan
    if cam.get("shot") in SHOT_SIZES:
        lens = f", {cam['lens_mm']} mm lens" if cam.get("lens_mm") else ""
        framing = f"framing ({SHOT_SIZES[cam['shot']]}{lens})"
    parts = [f"Image 1 is a rough 3D blockout of {moment_of}. Turn it into a real photograph of the same shot: "
             f"keep exactly the camera angle, {framing} and the position of every person and object.",
             "The blockout shows only the main pieces: dress the rest of the set with the realistic details, "
             "textures and light described below, so it looks like a real lived-in place, not an empty room."]
    people = [cid for cid in shot.get("characters", []) if data["characters"][cid].get("color")]
    if people:
        source = "image 2" if with_reference else "the description"
        parts.append(f"The colored mannequins are only placeholders for people: remove them completely and put "
                     f"each person from {source} in the exact place and pose of their mannequin.")
        for cid in people:
            ch = data["characters"][cid]
            who = _name(data, cid) + _placement((views or {}).get(cid))
            parts.append(f"The {ch['color']} mannequin is {who}: {ch.get('description', '')}.".replace("..", "."))
    parts += [line.strip().rstrip(".") + "." for line in legend or []]
    parts.append("No mannequins and no plain blocks.")
    if custom(shot, "image_prompt"):  # Claude-ov opis scene umesto šablona
        parts.append(custom(shot, "image_prompt"))
        if end:
            parts.append(f"Final moment: {(shot.get('end_moment') or _beat(shot, -1)).strip().rstrip('.')}.")
        return " ".join(parts)
    if shot.get("location_description"):
        parts.append(f"{shot['location_description'][0].upper()}{shot['location_description'][1:]}.")
    if data.get("style"):
        parts.append(f"{data['style']}.")
    rules = [r.rstrip(".") for r in data.get("continuity", [])]
    if rules:
        parts.append("; ".join(rules) + ".")
    moment = (shot.get("end_moment") or _beat(shot, -1)) if end else _beat(shot, 0)
    parts.append(f"{'Final' if end else 'Opening'} moment: {moment.strip().rstrip('.')}.")
    parts.append("Cinematic still frame, no text.")
    return " ".join(parts)


def end_frame_prompt(data: dict[str, Any], shot: dict[str, Any]) -> str:
    """Prompt za krajnju sliku kadra. Referenca je početna slika, pa scena, svetlo i kadriranje
    ostaju isti, a menja se samo ono što `end_moment` kaže (npr. fokus prešao na pozadinu)."""
    parts = ["Keep the exact same scene, camera position, framing and lighting as the reference image; "
             "this is the same shot a few seconds later.",
             f"Final moment: {shot['end_moment'].strip().rstrip('.')}."]
    if data.get("style"):
        parts.append(f"{data['style']}.")
    parts.append("Cinematic still frame, natural light, no text.")
    return " ".join(parts)


def reference_sheet_prompt(data: dict[str, Any], cid: str) -> str:
    ch = data["characters"][cid]
    style = data.get("style", "cinematic realism")
    return (f"Character reference sheet, {style}. {_name(data, cid)}: {ch.get('description', '')}. "
            "Full body front view, side view and back view, plus a close-up of the head, "
            "same outfit in every view, neutral grey background, even studio light, no text.")
