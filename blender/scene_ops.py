"""Scena kao lista operacija (.ops.json), po uzoru na Flick-ov Convert to 3D.

Čisti Python, bez Blendera: učitava operacije, proverava ih i računa gde je svaki objekat
i kamera u svakom trenutku kadra. Blender deo (blender_scene.py) samo crta to stanje.

Koordinate su kao u three.js: Y je gore, metri, uglovi u stepenima. Format je opisan u
blender/README.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

try:  # radi i kao paket (testovi) i kao skripta u Blenderu
    from . import camera_moves as cm
except ImportError:  # pragma: no cover
    import camera_moves as cm  # type: ignore[no-redef]

SHAPES = ("box", "cylinder", "sphere", "cone", "plane")
TYPES = ("mesh", "figure", "camera", "light")
OPS = ("add", "update", "remove", "shot", "camera_move", "keyframe", "path")
POSES = ("stand", "sit")
COLORS = {
    "yellow": "#f2c230", "blue": "#3b6fe0", "purple": "#8a4fd6", "red": "#d94141",
    "green": "#3fae5a", "orange": "#ee8a2e", "pink": "#e86fb4", "cyan": "#35b8c9",
    "white": "#f2f2f2", "grey": "#9a9a9a", "gray": "#9a9a9a", "black": "#222222",
}
ASPECTS = {"16:9": (1280, 720), "9:16": (720, 1280), "1:1": (1024, 1024), "4:3": (960, 720),
           "2.39:1": (1280, 536), "21:9": (1280, 544)}


class OpsError(ValueError):
    pass


def hex_color(value: str | None, default: str = "#bbbbbb") -> tuple[float, float, float]:
    """'#rrggbb' ili ime boje -> linearni RGB 0..1 (Blender radi u linearnom prostoru)."""
    text = COLORS.get(str(value).lower(), value) if value else default
    text = str(text).lstrip("#")
    if len(text) != 6:
        text = default.lstrip("#")
    srgb = [int(text[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)  # type: ignore[return-value]


def euler_matrix(rot: list[float] | tuple[float, ...]) -> list[list[float]]:
    """three.js Euler 'XYZ' u stepenima -> 3x3 matrica (Rx * Ry * Rz)."""
    a, b, c = (math.radians(v) for v in rot)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [
        [cb * cc, -cb * sc, sb],
        [ca * sc + sa * sb * cc, ca * cc - sa * sb * sc, -sa * cb],
        [sa * sc - ca * sb * cc, sa * cc + ca * sb * sc, ca * cb],
    ]


def apply_matrix(m: list[list[float]], v: cm.Vec) -> cm.Vec:
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def yaw_towards(pos: cm.Vec, target: cm.Vec) -> float:
    """Ugao (stepeni) oko Y ose tako da figura gleda ka meti; 0 znači da gleda ka +Z."""
    return math.degrees(math.atan2(target[0] - pos[0], target[2] - pos[2]))


class Stage:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.shots: dict[str, dict[str, Any]] = {}
        self.moves: dict[str, list[dict[str, Any]]] = {}
        self.keys: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.paths: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.errors: list[str] = []

    # --- učitavanje ---------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "Stage":
        ops = json.loads(Path(path).read_text(encoding="utf-8"))
        stage = cls.from_ops(ops)
        if stage.errors:
            raise OpsError(f"{path}:\n- " + "\n- ".join(stage.errors))
        return stage

    @classmethod
    def from_ops(cls, ops: list[dict[str, Any]]) -> "Stage":
        stage = cls()
        if not isinstance(ops, list):
            stage.errors.append("fajl mora biti lista operacija")
            return stage
        for i, op in enumerate(ops):
            stage._apply(i, op)
        stage._check_shots()
        return stage

    def _err(self, i: int, msg: str) -> None:
        self.errors.append(f"op[{i}]: {msg}")

    def _apply(self, i: int, op: dict[str, Any]) -> None:
        kind = op.get("op")
        if kind not in OPS:
            return self._err(i, f"nepoznata operacija '{kind}' (poznate: {', '.join(OPS)})")
        oid = op.get("id")
        if kind == "add":
            if not oid:
                return self._err(i, "add traži id")
            if oid in self.objects:
                return self._err(i, f"objekat '{oid}' već postoji (za izmenu koristi update)")
            obj = {k: v for k, v in op.items() if k != "op"}
            obj.setdefault("type", "mesh")
            if obj["type"] not in TYPES:
                return self._err(i, f"'{oid}': type mora biti jedno od {TYPES}")
            if obj["type"] == "mesh" and obj.setdefault("shape", "box") not in SHAPES:
                return self._err(i, f"'{oid}': shape mora biti jedno od {SHAPES}")
            if obj["type"] == "figure" and obj.setdefault("pose", "stand") not in POSES:
                return self._err(i, f"'{oid}': pose mora biti jedno od {POSES}")
            if not _is_vec(obj.get("pos", [0, 0, 0])):
                return self._err(i, f"'{oid}': pos mora biti [x, y, z]")
            self.objects[oid] = obj
        elif kind == "update":
            if oid not in self.objects:
                return self._err(i, f"update: objekat '{oid}' ne postoji")
            self.objects[oid].update({k: v for k, v in op.items() if k not in ("op", "id")})
        elif kind == "remove":
            if self.objects.pop(oid, None) is None:
                return self._err(i, f"remove: objekat '{oid}' ne postoji")
        elif kind == "shot":
            if not oid:
                return self._err(i, "shot traži id (isti kao u shotlist.json, npr. s01)")
            self.shots[oid] = {k: v for k, v in op.items() if k != "op"}
        elif kind == "camera_move":
            shot = op.get("shot")
            if op.get("move") not in cm.MOVES:
                return self._err(i, f"nepoznat pokret '{op.get('move')}' (poznati: {', '.join(cm.MOVES)})")
            if op.get("ease", "in_out") not in cm.EASING:
                return self._err(i, f"ease mora biti jedno od {tuple(cm.EASING)}")
            if op["move"] == "path" and not op.get("points"):
                return self._err(i, "path traži points")
            self.moves.setdefault(shot, []).append(op)
        elif kind == "keyframe":
            if oid not in self.objects:
                return self._err(i, f"keyframe: objekat '{oid}' ne postoji")
            if not isinstance(op.get("t"), (int, float)):
                return self._err(i, "keyframe traži t (sekunde od početka kadra)")
            self.keys.setdefault(op.get("shot"), {}).setdefault(oid, []).append(op)
        elif kind == "path":
            if oid not in self.objects:
                return self._err(i, f"path: objekat '{oid}' ne postoji")
            if not op.get("points"):
                return self._err(i, "path traži points")
            self.paths.setdefault(op.get("shot"), {}).setdefault(oid, []).append(op)
        return None

    def _check_shots(self) -> None:
        for sid, shot in self.shots.items():
            cam = self.objects.get(shot.get("camera", ""))
            if cam is None or cam.get("type") != "camera":
                self.errors.append(f"kadar {sid}: camera '{shot.get('camera')}' nije kamera u sceni")
            if not isinstance(shot.get("duration"), (int, float)) or shot["duration"] <= 0:
                self.errors.append(f"kadar {sid}: duration (sekunde) nedostaje")
        for sid in list(self.moves) + list(self.keys) + list(self.paths):
            if sid is not None and sid not in self.shots:
                self.errors.append(f"operacija pominje kadar '{sid}' koji nije definisan sa op: shot")

    # --- kadar --------------------------------------------------------------

    def shot(self, sid: str | None = None) -> dict[str, Any]:
        if sid is None:
            if not self.shots:
                raise OpsError("scena nema nijedan kadar (op: shot)")
            sid = next(iter(self.shots))
        if sid not in self.shots:
            raise OpsError(f"kadar '{sid}' ne postoji; postoje: {', '.join(self.shots) or 'nijedan'}")
        return {"id": sid, **self.shots[sid]}

    def fps(self, sid: str | None = None) -> int:
        return int(self.shot(sid).get("fps", 24))

    def resolution(self, sid: str | None = None) -> tuple[int, int]:
        shot = self.shot(sid)
        if shot.get("resolution"):
            w, h = shot["resolution"]
            return int(w), int(h)
        cam = self.objects[shot["camera"]]
        return ASPECTS.get(cam.get("aspect", "16:9"), ASPECTS["16:9"])

    def frame_count(self, sid: str | None = None) -> int:
        """Isti broj frejmova kao video koji pravi LTX (8k+1), da kontrolni video legne 1:1."""
        shot = self.shot(sid)
        fps = self.fps(sid)
        if shot.get("frames") == "exact":
            return max(1, round(shot["duration"] * fps))
        k = max(1, math.ceil(shot["duration"] * fps / 8))
        return 8 * k + 1

    def times(self, sid: str | None = None) -> list[float]:
        fps = self.fps(sid)
        return [i / fps for i in range(self.frame_count(sid))]

    # --- stanje u trenutku t ------------------------------------------------

    def _point(self, value: Any) -> cm.Vec:
        """Meta može biti tačka [x, y, z] ili id objekta (za figuru: visina očiju)."""
        if isinstance(value, str):
            obj = self.objects[value]
            x, y, z = obj.get("pos", [0, 0, 0])
            if obj.get("type") == "figure":
                y += obj.get("height", 1.75) * (0.92 if obj.get("pose") != "sit" else 0.62)
            return (float(x), float(y), float(z))
        return tuple(float(v) for v in value)  # type: ignore[return-value]

    def camera_base(self, cam_id: str) -> cm.State:
        cam = self.objects[cam_id]
        pos = tuple(float(v) for v in cam.get("pos", [0, 1.6, 5]))
        if cam.get("look_at") is not None:
            target = self._point(cam["look_at"])
        else:
            forward = apply_matrix(euler_matrix(cam.get("rot", [0, 0, 0])), (0.0, 0.0, -1.0))
            target = cm.add(pos, forward)  # type: ignore[arg-type]
        return {"pos": pos, "target": target, "lens": float(cam.get("lens_mm", 35)),
                "roll": float(cam.get("roll", 0))}

    def camera_at(self, sid: str, t: float) -> cm.State:
        shot = self.shot(sid)
        moves = []
        for m in self.moves.get(sid, []) + self.moves.get(None, []):
            m = dict(m)
            if isinstance(m.get("target"), str):
                m["target"] = self._point(m["target"])
            m.setdefault("end", shot["duration"])
            moves.append(m)
        base = self.camera_base(shot["camera"])
        target_override = next((m["target"] for m in moves if m.get("target") is not None and m["move"] != "path"), None)
        if target_override is not None:
            base["target"] = tuple(target_override)
        return cm.camera_at(base, moves, t)

    def object_at(self, sid: str, oid: str, t: float) -> dict[str, Any]:
        """Položaj i okret objekta u trenutku t: keyframe-ovi i putanje kadra preko osnovnog stanja."""
        obj = self.objects[oid]
        pos = tuple(float(v) for v in obj.get("pos", [0, 0, 0]))
        yaw = float(obj.get("facing", 0.0))
        if obj.get("look_at") is not None and obj.get("type") == "figure":
            yaw = yaw_towards(pos, self._point(obj["look_at"]))
        keys = sorted(self.keys.get(sid, {}).get(oid, []) + self.keys.get(None, {}).get(oid, []),
                      key=lambda k: k["t"])
        prev = {"t": 0.0, "pos": pos, "facing": yaw}
        for key in keys:
            nxt = {"t": float(key["t"]), "pos": tuple(key.get("pos", prev["pos"])),
                   "facing": float(key.get("facing", prev["facing"]))}
            if t <= nxt["t"]:
                span = nxt["t"] - prev["t"]
                p = 1.0 if span <= 0 else cm.ease((t - prev["t"]) / span, key.get("ease", "in_out"))
                pos = cm.lerp(prev["pos"], nxt["pos"], p)
                yaw = prev["facing"] + _angle_delta(prev["facing"], nxt["facing"]) * p
                break
            prev = nxt
        else:
            pos, yaw = prev["pos"], prev["facing"]
        for path in self.paths.get(sid, {}).get(oid, []) + self.paths.get(None, {}).get(oid, []):
            start, end = float(path.get("start", 0)), float(path.get("end", self.shot(sid)["duration"]))
            if t < start:
                continue
            points = [tuple(map(float, p)) for p in path["points"]]
            if path.get("from_current", True):
                points = [pos, *points]
            p = cm.ease((t - start) / (end - start) if end > start else 1.0, path.get("ease", "linear"))
            new_pos = cm.point_on_path(points, p)
            if path.get("face_direction", True):
                # pravac kretanja oko tačke p; na kraju puta figura ostaje okrenuta kako je stigla
                behind = cm.point_on_path(points, max(0.0, min(p, 0.99) - 0.01))
                ahead = cm.point_on_path(points, min(1.0, min(p, 0.99) + 0.01))
                if math.hypot(ahead[0] - behind[0], ahead[2] - behind[2]) > 1e-4:
                    yaw = yaw_towards(behind, ahead)
            pos = new_pos
        return {"pos": pos, "facing": yaw}

    # --- pregled za agenta (scene_read) ---------------------------------------

    def summary(self) -> str:
        lines = [f"{len(self.objects)} objekata, {len(self.shots)} kadrova"]
        groups: dict[str, list[str]] = {}
        for oid, obj in self.objects.items():
            kind = obj["type"] if obj["type"] != "mesh" else obj.get("shape", "box")
            groups.setdefault(obj.get("group", "-"), []).append(f"{oid} ({kind})")
        for group, items in groups.items():
            lines.append(f"  [{group}] " + ", ".join(items))
        for sid, shot in self.shots.items():
            moves = ", ".join(m["move"] for m in self.moves.get(sid, [])) or "static"
            w, h = self.resolution(sid)
            lines.append(f"  kadar {sid}: kamera {shot.get('camera')}, {shot.get('duration')} s, "
                         f"{self.frame_count(sid)} frejmova, {w}x{h}, pokreti: {moves}")
        return "\n".join(lines)


def _is_vec(v: Any) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)


def _angle_delta(a: float, b: float) -> float:
    """Najkraći put od ugla a do ugla b (da se figura ne okreće za 350° umesto -10°)."""
    return (b - a + 180) % 360 - 180
