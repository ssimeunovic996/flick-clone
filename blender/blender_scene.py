"""Gradi Blender scenu iz Stage-a (scene_ops.py) i animira je za jedan kadar.

three.js koordinate (Y gore) se ovde pretvaraju u Blender (Z gore): (x, y, z) -> (x, -z, y).
"""

from __future__ import annotations

import math
from typing import Any

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

try:
    from . import scene_ops
except ImportError:  # pragma: no cover - pokrenuto kao skripta u Blenderu
    import scene_ops  # type: ignore[no-redef]

# three -> blender
C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))


def to_b(v) -> Vector:
    return C @ Vector(v)


def size_to_b(size) -> Vector:
    w, h, d = size
    return Vector((w, d, h))


def rot_to_b(rot) -> Matrix:
    m = Matrix(scene_ops.euler_matrix(rot))
    return C @ m @ C.transposed()


def clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            coll.remove(block)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)


_materials: dict[tuple, bpy.types.Material] = {}


def material(color: Any) -> bpy.types.Material:
    rgb = scene_ops.hex_color(color)
    key = tuple(round(c, 4) for c in rgb)
    mat = _materials.get(key)
    if mat is None or mat.name not in bpy.data.materials:
        mat = bpy.data.materials.new(f"boja_{len(_materials)}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.8
        mat.diffuse_color = (*rgb, 1.0)
        _materials[key] = mat
    return mat


def unit_mesh(shape: str, name: str) -> bpy.types.Mesh:
    """Jedinični oblik koji staje u kocku 1x1x1 sa centrom u nuli (Blender koordinate)."""
    bm = bmesh.new()
    if shape == "box":
        bmesh.ops.create_cube(bm, size=1.0)
    elif shape == "cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.5, depth=1.0)
    elif shape == "cone":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.0, depth=1.0)
    elif shape == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.5)
    elif shape == "plane":
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    else:
        raise ValueError(shape)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if shape in ("cylinder", "cone", "sphere"):
        for poly in mesh.polygons:
            poly.use_smooth = True
    return mesh


def collection(name: str | None) -> bpy.types.Collection:
    scene = bpy.context.scene
    if not name:
        return scene.collection
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        scene.collection.children.link(coll)
    return coll


def add_mesh(oid: str, obj: dict[str, Any]) -> bpy.types.Object:
    shape = obj.get("shape", "box")
    size = obj.get("size", [1, 1, 1])
    if shape == "plane":
        size = [size[0], 1, size[2]]
    ob = bpy.data.objects.new(oid, unit_mesh(shape, oid))
    ob.data.materials.append(material(obj.get("color")))
    # Blender cilindar stoji duž Z, kao three.js cilindar duž Y, pa je dovoljna zamena osa
    ob.scale = size_to_b(size) if shape != "plane" else Vector((size[0], size[2], 1))
    collection(obj.get("group")).objects.link(ob)
    place(ob, obj.get("pos", [0, 0, 0]), rot=obj.get("rot"))
    return ob


# delovi lutke za visinu 1.75 m: (ime, oblik, centar, veličina) u Blender lokalnim koordinatama,
# figura gleda ka -Y (to je +Z u three.js, "ka kameri" u podrazumevanoj sceni)
FIGURE_STAND = [
    ("noga_l", "cylinder", (0.10, 0, 0.43), (0.14, 0.14, 0.86)),
    ("noga_d", "cylinder", (-0.10, 0, 0.43), (0.14, 0.14, 0.86)),
    ("telo", "cylinder", (0, 0, 1.15), (0.36, 0.22, 0.62)),
    ("ruka_l", "cylinder", (0.24, 0, 1.12), (0.09, 0.09, 0.62)),
    ("ruka_d", "cylinder", (-0.24, 0, 1.12), (0.09, 0.09, 0.62)),
    ("glava", "sphere", (0, 0, 1.6), (0.23, 0.25, 0.27)),
    ("nos", "box", (0, -0.13, 1.6), (0.05, 0.06, 0.05)),
]
FIGURE_SIT = [
    ("butina_l", "cylinder", (0.10, -0.22, 0.47), (0.14, 0.44, 0.14)),
    ("butina_d", "cylinder", (-0.10, -0.22, 0.47), (0.14, 0.44, 0.14)),
    ("potkolenica_l", "cylinder", (0.10, -0.44, 0.23), (0.13, 0.13, 0.46)),
    ("potkolenica_d", "cylinder", (-0.10, -0.44, 0.23), (0.13, 0.13, 0.46)),
    ("telo", "cylinder", (0, 0, 0.78), (0.36, 0.22, 0.62)),
    ("ruka_l", "cylinder", (0.24, -0.05, 0.75), (0.09, 0.09, 0.6)),
    ("ruka_d", "cylinder", (-0.24, -0.05, 0.75), (0.09, 0.09, 0.6)),
    ("glava", "sphere", (0, 0, 1.23), (0.23, 0.25, 0.27)),
    ("nos", "box", (0, -0.13, 1.23), (0.05, 0.06, 0.05)),
]


def add_figure(oid: str, obj: dict[str, Any]) -> bpy.types.Object:
    """Obojena lutka od primitiva; koren je prazan objekat na stopalima, pa se pomera samo on."""
    root = bpy.data.objects.new(oid, None)
    root.empty_display_type = "PLAIN_AXES"
    coll = collection(obj.get("group", "Likovi"))
    coll.objects.link(root)
    s = float(obj.get("height", 1.75)) / 1.75
    mat = material(obj.get("color", "blue"))
    parts = FIGURE_SIT if obj.get("pose") == "sit" else FIGURE_STAND
    for name, shape, center, size in parts:
        if name.startswith("butina"):
            mesh = unit_mesh("cylinder", f"{oid}_{name}")
            part = bpy.data.objects.new(f"{oid}_{name}", mesh)
            part.rotation_euler = (math.radians(90), 0, 0)
            part.scale = (size[0] * s, size[2] * s, size[1] * s)
        else:
            part = bpy.data.objects.new(f"{oid}_{name}", unit_mesh(shape, f"{oid}_{name}"))
            part.scale = Vector(size) * s
        part.location = Vector(center) * s
        part.data.materials.append(mat)
        part.parent = root
        coll.objects.link(part)
    place(root, obj.get("pos", [0, 0, 0]), yaw=obj.get("facing", 0))
    return root


def add_camera(oid: str, obj: dict[str, Any]) -> bpy.types.Object:
    cam = bpy.data.cameras.new(oid)
    cam.lens = float(obj.get("lens_mm", 35))
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = float(obj.get("sensor_mm", 36))
    cam.clip_start = 0.05
    cam.clip_end = 500
    ob = bpy.data.objects.new(oid, cam)
    collection("Kamere").objects.link(ob)
    return ob


def add_light(oid: str, obj: dict[str, Any]) -> bpy.types.Object:
    kind = obj.get("kind", "point").upper()
    light = bpy.data.lights.new(oid, kind if kind in ("POINT", "SUN", "AREA", "SPOT") else "POINT")
    light.energy = float(obj.get("energy", 3.0 if kind == "SUN" else 500))
    light.color = scene_ops.hex_color(obj.get("color", "#ffffff"))
    ob = bpy.data.objects.new(oid, light)
    collection("Svetla").objects.link(ob)
    pos = obj.get("pos", [2, 4, 2])
    target = obj.get("look_at", [0, 0, 0])
    aim(ob, pos, target)
    return ob


def place(ob: bpy.types.Object, pos, rot=None, yaw=None) -> None:
    ob.location = to_b(pos)
    if rot is not None:
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = rot_to_b(rot).to_quaternion()
    elif yaw is not None:
        ob.rotation_mode = "XYZ"
        ob.rotation_euler = (0, 0, math.radians(float(yaw)))


def aim(ob: bpy.types.Object, pos, target, roll: float = 0.0) -> None:
    """Postavlja objekat (kameru ili svetlo) da gleda ka meti; gore je Z."""
    p, t = to_b(pos), to_b(target)
    direction = t - p
    if direction.length < 1e-6:
        direction = Vector((0, 1, 0))
    quat = direction.to_track_quat("-Z", "Y")
    if roll:
        quat = quat @ Quaternion((0, 0, 1), math.radians(roll))
    ob.location = p
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = quat


def build(stage: scene_ops.Stage, world_color: str = "#8f96a3") -> dict[str, bpy.types.Object]:
    clear_scene()
    _materials.clear()
    made: dict[str, bpy.types.Object] = {}
    for oid, obj in stage.objects.items():
        kind = obj["type"]
        if kind == "mesh":
            made[oid] = add_mesh(oid, obj)
        elif kind == "figure":
            made[oid] = add_figure(oid, obj)
        elif kind == "camera":
            made[oid] = add_camera(oid, obj)
        elif kind == "light":
            made[oid] = add_light(oid, obj)
    if not any(o["type"] == "light" for o in stage.objects.values()):
        made["_sunce"] = add_light("_sunce", {"kind": "sun", "pos": [3, 6, 4], "look_at": [0, 0, 0], "energy": 3})
    world = bpy.context.scene.world or bpy.data.worlds.new("Svet")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*scene_ops.hex_color(world_color), 1.0)
    bg.inputs["Strength"].default_value = 0.6
    return made


def animate(stage: scene_ops.Stage, made: dict[str, bpy.types.Object], sid: str) -> None:
    """Upisuje keyframe na svaki frejm kadra: kamera, figure i objekti koji se pomeraju."""
    scene = bpy.context.scene
    shot = stage.shot(sid)
    w, h = stage.resolution(sid)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.fps = stage.fps(sid)
    times = stage.times(sid)
    scene.frame_start, scene.frame_end = 1, len(times)
    cam_ob = made[shot["camera"]]
    scene.camera = cam_ob
    moving = [oid for oid in stage.objects
              if oid in stage.keys.get(sid, {}) or oid in stage.paths.get(sid, {})
              or oid in stage.keys.get(None, {}) or oid in stage.paths.get(None, {})]
    for frame, t in enumerate(times, start=1):
        state = stage.camera_at(sid, t)
        aim(cam_ob, state["pos"], state["target"], state.get("roll", 0))
        cam_ob.data.lens = state["lens"]
        cam_ob.keyframe_insert("location", frame=frame)
        cam_ob.keyframe_insert("rotation_quaternion", frame=frame)
        cam_ob.data.keyframe_insert("lens", frame=frame)
        for oid in moving:
            ob = made[oid]
            st = stage.object_at(sid, oid, t)
            ob.location = to_b(st["pos"])
            ob.keyframe_insert("location", frame=frame)
            if stage.objects[oid]["type"] == "figure":
                ob.rotation_mode = "XYZ"
                ob.rotation_euler = (0, 0, math.radians(st["facing"]))
                ob.keyframe_insert("rotation_euler", frame=frame)
    scene.frame_set(1)


# --- postavka: scena koju Stefan sam uređuje u Blenderu -------------------------------

def to_three(v) -> tuple[float, float, float]:
    """Blender (Z gore) -> three.js (Y gore)."""
    x, y, z = C.transposed() @ Vector(v)
    return (round(x, 4), round(y, 4), round(z, 4))


def pose_at(stage: scene_ops.Stage, made: dict[str, bpy.types.Object], sid: str, t: float) -> None:
    """Kamera kadra i sve figure i objekti koji se pomeraju, u trenutku t, bez keyframe-ova."""
    shot = stage.shot(sid)
    cam_ob = made[shot["camera"]]
    state = stage.camera_at(sid, t)
    aim(cam_ob, state["pos"], state["target"], state.get("roll", 0))
    cam_ob.data.lens = state["lens"]
    for oid, obj in stage.objects.items():
        if obj["type"] not in ("figure", "mesh") or oid not in made:
            continue
        st = stage.object_at(sid, oid, t)
        made[oid].location = to_b(st["pos"])
        if obj["type"] == "figure":
            made[oid].rotation_mode = "XYZ"
            made[oid].rotation_euler = (0, 0, math.radians(st["facing"]))


def make_postavka(stage: scene_ops.Stage, made: dict[str, bpy.types.Object], sid: str,
                  t: float = 0.0) -> bpy.types.Object:
    """Scena za ručno postavljanje jednog kadra: sve stoji kako je u trenutku t, bez animacije,
    samo kamera tog kadra. Lutka se bira i pomera cela (delovi tela se ne mogu izabrati), a uz
    svaki objekat ostaju podaci iz .ops.json (id, vrsta, label, poza), da `snapshot` zna šta je šta."""
    scene = bpy.context.scene
    shot = stage.shot(sid)
    w, h = stage.resolution(sid)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.fps = stage.fps(sid)
    scene.frame_start = scene.frame_end = 1
    scene.frame_set(1)
    pose_at(stage, made, sid, t)
    cam_ob = made[shot["camera"]]
    for oid, ob in list(made.items()):
        obj = stage.objects.get(oid, {})
        if obj.get("type") == "camera" and oid != shot["camera"]:
            bpy.data.objects.remove(ob, do_unlink=True)
            del made[oid]
            continue
        ob["flick_id"] = oid
        ob["flick_type"] = obj.get("type", "light")
        for key in ("label", "pose", "color"):
            if obj.get(key) is not None:
                ob[f"flick_{key}"] = str(obj[key])
        if obj.get("type") == "figure":
            ob["flick_height"] = float(obj.get("height", 1.75))
            ob.empty_display_type = "CIRCLE"
            ob.empty_display_size = 0.45
            for part in ob.children:
                part.hide_select = True
    scene.camera = cam_ob
    scene["flick_shot"] = sid
    scene["flick_duration"] = float(shot["duration"])
    tool = scene.tool_settings
    tool.use_keyframe_insert_auto = False  # Stefan postavlja jedan trenutak; kraj je poseban fajl
    for screen in bpy.data.screens:  # u Solid prikazu boje lutki kao u layout slici
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].shading.color_type = "MATERIAL"
    return cam_ob


def snapshot_state() -> dict[str, Any]:
    """Šta je u otvorenoj postavci: kamera i figure u three.js koordinatama i label-e objekata."""
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None:
        raise RuntimeError("scena nema kameru (Scene > Camera)")
    m = cam.matrix_world
    pos = m.translation
    forward = (m.to_3x3() @ Vector((0, 0, -1))).normalized()
    up = (m.to_3x3() @ Vector((0, 1, 0))).normalized()
    level = forward.to_track_quat("-Z", "Y") @ Vector((0, 1, 0))
    roll = math.degrees(level.angle(up)) if level.length and up.length else 0.0
    if level.cross(up).dot(forward) > 0:
        roll = -roll
    figures, labels = {}, []
    for ob in scene.objects:
        kind = ob.get("flick_type")
        if ob.get("flick_label") and ob.visible_get():
            labels.append(str(ob["flick_label"]))
        # .blend iz `build` nema flick_ podatke: lutka je prazan objekat sa delovima "<ime>_glava" itd.
        is_figure = kind == "figure" or (kind is None and ob.type == "EMPTY"
                                         and any(c.name == f"{ob.name}_glava" for c in ob.children))
        if not is_figure:
            continue
        sitting = any(c.name.startswith(f"{ob.name}_butina") for c in ob.children)
        yaw = math.degrees(ob.matrix_world.to_euler("XYZ").z)
        figures[str(ob.get("flick_id", ob.name))] = {
            "pos": list(to_three(ob.matrix_world.translation)),
            "facing": round(yaw % 360, 2),
            "pose": str(ob.get("flick_pose", "sit" if sitting else "stand")),
            "height": float(ob.get("flick_height", 1.75)),
            "visible": ob.visible_get(),
        }
    return {
        "shot": scene.get("flick_shot"),
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
        "camera": {"name": cam.name, "pos": list(to_three(pos)), "target": list(to_three(pos + forward * 3)),
                   "lens": round(cam.data.lens, 2), "roll": round(roll, 2)},
        "figures": figures,
        "labels": labels,
    }
