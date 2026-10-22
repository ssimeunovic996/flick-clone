"""Pokreti kamere kao čista matematika, bez Blendera.

Sve je u three.js koordinatama (Y gore, metri, stepeni), kao u .ops.json, pa isti kod
kasnije može da posluži i za three.js scenu u Fazi 4. Stanje kamere je rečnik:

    {"pos": (x, y, z), "target": (x, y, z), "lens": 35.0, "roll": 0.0}

Pokret dobija napredak `p` od 0 do 1 (posle easing-a) i vraća novo stanje.
"""

from __future__ import annotations

import math
from typing import Any, Callable

Vec = tuple[float, float, float]
State = dict[str, Any]


# --- vektori ---------------------------------------------------------------

def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def length(a: Vec) -> float:
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def norm(a: Vec) -> Vec:
    n = length(a)
    return (0.0, 0.0, -1.0) if n < 1e-9 else mul(a, 1 / n)


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def lerp(a: Vec, b: Vec, p: float) -> Vec:
    return add(a, mul(sub(b, a), p))


def rotate_y(v: Vec, degrees: float) -> Vec:
    """Rotacija oko vertikalne ose; pozitivno je u smeru suprotnom od kazaljke gledano odozgo."""
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


def rotate_axis(v: Vec, axis: Vec, degrees: float) -> Vec:
    """Rodrigova formula: rotacija vektora oko proizvoljne ose."""
    k = norm(axis)
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    kv = cross(k, v)
    kd = k[0] * v[0] + k[1] * v[1] + k[2] * v[2]
    return add(add(mul(v, c), mul(kv, s)), mul(k, kd * (1 - c)))


def right_vector(state: State) -> Vec:
    return norm(cross(norm(sub(state["target"], state["pos"])), (0.0, 1.0, 0.0)))


# --- easing ----------------------------------------------------------------

EASING: dict[str, Callable[[float], float]] = {
    "linear": lambda p: p,
    "in": lambda p: p * p,
    "out": lambda p: 1 - (1 - p) ** 2,
    "in_out": lambda p: p * p * (3 - 2 * p),
}


def ease(p: float, kind: str = "in_out") -> float:
    return EASING[kind](min(1.0, max(0.0, p)))


# --- pokreti ---------------------------------------------------------------

def _with(state: State, **changes: Any) -> State:
    out = dict(state)
    out.update(changes)
    return out


def static(state: State, move: dict, p: float) -> State:
    return state


def dolly(state: State, move: dict, p: float, sign: float = 1.0) -> State:
    """Kamera ide napred (dolly_in) ili nazad (dolly_out) duž pravca gledanja, zajedno sa metom."""
    step = mul(norm(sub(state["target"], state["pos"])), sign * move.get("distance", 1.0) * p)
    return _with(state, pos=add(state["pos"], step), target=add(state["target"], step))


def truck(state: State, move: dict, p: float, sign: float = 1.0) -> State:
    """Bočno klizanje kamere (truck_right je +, truck_left je -)."""
    step = mul(right_vector(state), sign * move.get("distance", 1.0) * p)
    return _with(state, pos=add(state["pos"], step), target=add(state["target"], step))


def dolly_zoom(state: State, move: dict, p: float) -> State:
    """Vertigo: kamera prilazi meti, a žižna daljina se menja tako da subjekat ostane iste veličine."""
    d0 = length(sub(state["target"], state["pos"]))
    distance = move.get("distance", d0 * 0.5)
    d = max(0.05, d0 - distance * p)
    pos = add(state["target"], mul(norm(sub(state["pos"], state["target"])), d))
    return _with(state, pos=pos, lens=state["lens"] * d / d0)


def crane(state: State, move: dict, p: float, sign: float = 1.0) -> State:
    """Kamera se diže ili spušta, a ostaje uperena u metu."""
    h = sign * move.get("height", 1.0) * p
    return _with(state, pos=add(state["pos"], (0.0, h, 0.0)))


def pan(state: State, move: dict, p: float, sign: float = 1.0) -> State:
    """Kamera stoji, okreće se levo (+) ili desno (-) oko vertikalne ose."""
    offset = rotate_y(sub(state["target"], state["pos"]), sign * move.get("degrees", 30.0) * p)
    return _with(state, target=add(state["pos"], offset))


def tilt(state: State, move: dict, p: float, sign: float = 1.0) -> State:
    """Kamera stoji, naginje se gore (+) ili dole (-)."""
    offset = rotate_axis(sub(state["target"], state["pos"]), right_vector(state),
                         sign * move.get("degrees", 15.0) * p)
    return _with(state, target=add(state["pos"], offset))


def orbit(state: State, move: dict, p: float) -> State:
    """Kružna putanja oko mete; pozitivni stepeni idu suprotno od kazaljke gledano odozgo."""
    offset = rotate_y(sub(state["pos"], state["target"]), move.get("degrees", 90.0) * p)
    return _with(state, pos=add(state["target"], offset))


def spiral(state: State, move: dict, p: float) -> State:
    """Orbit uz promenu udaljenosti (radius_factor) i visine (height)."""
    offset = rotate_y(sub(state["pos"], state["target"]), move.get("degrees", 180.0) * p)
    factor = 1 + (move.get("radius_factor", 0.6) - 1) * p
    offset = (offset[0] * factor, offset[1], offset[2] * factor)
    pos = add(add(state["target"], offset), (0.0, move.get("height", 0.5) * p, 0.0))
    return _with(state, pos=pos)


def zoom(state: State, move: dict, p: float) -> State:
    end = move.get("lens_end", state["lens"] * 2)
    return _with(state, lens=state["lens"] + (end - state["lens"]) * p)


def path(state: State, move: dict, p: float) -> State:
    """Kamera ide kroz tačke `points` ravnomerno po dužini puta. Gleda u `target` ako je zadat,
    inače napred duž puta."""
    points = [tuple(map(float, pt)) for pt in move["points"]]
    if move.get("from_current", True):
        points = [state["pos"], *points]
    pos = point_on_path(points, p)
    if move.get("target") is not None:
        return _with(state, pos=pos, target=tuple(map(float, move["target"])))
    # gleda napred duž puta, sa istim nagibom kao na početku
    look = sub(state["target"], state["pos"])
    flat = math.hypot(look[0], look[2]) or 1.0
    slope = look[1] / flat
    ahead = point_on_path(points, min(1.0, p + 0.02))
    direction = sub(ahead, pos) if p < 0.98 else sub(pos, point_on_path(points, 0.98))
    if math.hypot(direction[0], direction[2]) < 1e-6:
        direction = look
    forward = norm((direction[0], 0.0, direction[2]))
    target = add(pos, (forward[0] * 2.0, slope * 2.0, forward[2] * 2.0))
    return _with(state, pos=pos, target=target)


def point_on_path(points: list[Vec], p: float) -> Vec:
    if len(points) == 1:
        return points[0]
    segments = [length(sub(b, a)) for a, b in zip(points, points[1:])]
    total = sum(segments) or 1.0
    want = total * min(1.0, max(0.0, p))
    for (a, b), seg in zip(zip(points, points[1:]), segments):
        if want <= seg:
            return lerp(a, b, 0.0 if seg == 0 else want / seg)
        want -= seg
    return points[-1]


MOVES: dict[str, Callable[[State, dict, float], State]] = {
    "static": static,
    "dolly_in": lambda s, m, p: dolly(s, m, p, 1.0),
    "dolly_out": lambda s, m, p: dolly(s, m, p, -1.0),
    "truck_left": lambda s, m, p: truck(s, m, p, -1.0),
    "truck_right": lambda s, m, p: truck(s, m, p, 1.0),
    "dolly_zoom": dolly_zoom,
    "crane_up": lambda s, m, p: crane(s, m, p, 1.0),
    "crane_down": lambda s, m, p: crane(s, m, p, -1.0),
    "pan_left": lambda s, m, p: pan(s, m, p, 1.0),
    "pan_right": lambda s, m, p: pan(s, m, p, -1.0),
    "tilt_up": lambda s, m, p: tilt(s, m, p, 1.0),
    "tilt_down": lambda s, m, p: tilt(s, m, p, -1.0),
    "orbit": orbit,
    "spiral": spiral,
    "zoom": zoom,
    "path": path,
}


def handheld(state: State, amount: float, t: float, seed: int = 0) -> State:
    """Blago drhtanje iz ruke: zbir sporih sinusa, isti za isti seed (ponovljiv render)."""
    freqs = (1.3, 1.7, 2.3, 1.1, 1.9)

    def wobble(i: int) -> float:
        phase = seed * 1.618 + i * 2.399
        f = freqs[(i - 1) % len(freqs)]
        return (math.sin(t * f + phase) + 0.5 * math.sin(t * f * 2.7 + 2 * phase)) / 1.5

    shake = (wobble(1) * amount, wobble(2) * amount, wobble(3) * amount * 0.5)
    aim = (wobble(4) * amount * 2, wobble(5) * amount * 2, 0.0)
    return _with(state, pos=add(state["pos"], shake), target=add(add(state["target"], shake), aim))


def camera_at(base: State, moves: list[dict], t: float) -> State:
    """Stanje kamere u trenutku t (sekunde od početka kadra). Pokreti idu redom po `start`;
    svaki kreće od stanja u kom je prethodni završio."""
    state = dict(base)
    shake = 0.0
    for move in sorted(moves, key=lambda m: m.get("start", 0.0)):
        start, end = move.get("start", 0.0), move.get("end", move.get("start", 0.0) + 1.0)
        shake = max(shake, float(move.get("handheld", 0.0)))
        if t <= start:
            break
        raw = 1.0 if end <= start else (t - start) / (end - start)
        state = MOVES[move["move"]](state, move, ease(raw, move.get("ease", "in_out")))
        if t < end:
            break
    if shake:
        state = handheld(state, shake, t)
    return state
