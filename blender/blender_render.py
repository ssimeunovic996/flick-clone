"""Render kontrolnih videa za kadar: layout (obojene figure i scena) i dubina, plus jedna slika.

Dubina je bela blizu kamere i crna daleko, kao mape koje prave Depth Anything i slični
modeli, jer takve mape očekuju depth kontrole za video modele.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import bpy

ENGINES = {"cycles": ("CYCLES",), "eevee": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
           "workbench": ("BLENDER_WORKBENCH",)}


def set_engine(name: str = "cycles", samples: int = 32, denoise: bool = True) -> str:
    scene = bpy.context.scene
    engine = None
    for candidate in ENGINES[name]:  # ime EEVEE-a se menjalo između verzija
        try:
            scene.render.engine = candidate
            engine = candidate
            break
        except TypeError:
            continue
    if engine is None:
        raise RuntimeError(f"Blender nema engine '{name}'")
    if engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = denoise
        scene.cycles.device = "GPU" if _enable_gpu() else "CPU"
    elif engine == "BLENDER_WORKBENCH":
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "MATERIAL"
    return engine


def _enable_gpu() -> bool:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return False
    for kind in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except (TypeError, ValueError):
            continue
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == kind
            return True
    return False


def set_view(raw: bool) -> None:
    vs = bpy.context.scene.view_settings
    vs.view_transform = "Raw" if raw else "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0


def depth_range(frames: list[int], low: float = 0.01, high: float = 0.99) -> tuple[float, float]:
    """Raspon dubine koji kamera stvarno vidi u kadru: brz render u maloj rezoluciji gde je
    vrednost piksela dubina u metrima, pa 1. i 99. percentil kroz prvi, srednji i zadnji frejm.
    Isti raspon važi za ceo kadar, da mapa dubine ne treperi."""
    scene = bpy.context.scene
    layer = bpy.context.view_layer
    old = (scene.render.resolution_percentage, scene.render.image_settings.file_format,
           scene.render.image_settings.color_depth)
    probe = bpy.data.materials.get("_dubina_proba") or bpy.data.materials.new("_dubina_proba")
    probe.use_nodes = True
    nodes, links = probe.node_tree.nodes, probe.node_tree.links
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    links.new(nodes.new("ShaderNodeCameraData").outputs["View Z Depth"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], nodes.new("ShaderNodeOutputMaterial").inputs["Surface"])
    set_engine("cycles", 1, denoise=False)
    set_view(raw=True)
    layer.material_override = probe
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
    scene.render.resolution_percentage = max(5, old[0] // 5)
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    values: list[float] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for frame in frames:
                scene.frame_set(frame)
                path = Path(tmp) / f"proba_{frame}.exr"
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(str(path))
                px = img.pixels[:]
                values += [v for v in px[0::4] if v > 0.01]
                bpy.data.images.remove(img)
    finally:
        layer.material_override = None
        scene.render.resolution_percentage, scene.render.image_settings.file_format, \
            scene.render.image_settings.color_depth = old
    if not values:
        return 0.5, 20.0
    values.sort()
    near = values[int(low * (len(values) - 1))]
    far = values[int(high * (len(values) - 1))]
    return max(0.05, near * 0.95), max(far * 1.05, near * 1.5)


def depth_material(near: float, far: float, mode: str = "inverse") -> bpy.types.Material:
    mat = bpy.data.materials.get("_dubina") or bpy.data.materials.new("_dubina")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    cam = nodes.new("ShaderNodeCameraData")
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    rng = nodes.new("ShaderNodeMapRange")
    rng.clamp = True
    if mode == "inverse":
        inv = nodes.new("ShaderNodeMath")
        inv.operation = "DIVIDE"
        inv.inputs[0].default_value = 1.0
        links.new(cam.outputs["View Z Depth"], inv.inputs[1])
        links.new(inv.outputs[0], rng.inputs["Value"])
        rng.inputs["From Min"].default_value = 1.0 / far
        rng.inputs["From Max"].default_value = 1.0 / near
        rng.inputs["To Min"].default_value = 0.0
        rng.inputs["To Max"].default_value = 1.0
    else:
        links.new(cam.outputs["View Z Depth"], rng.inputs["Value"])
        rng.inputs["From Min"].default_value = near
        rng.inputs["From Max"].default_value = far
        rng.inputs["To Min"].default_value = 1.0
        rng.inputs["To Max"].default_value = 0.0
    links.new(rng.outputs["Result"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def _render_frames(dest_dir: Path, frames: list[int]) -> list[Path]:
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    out = []
    for frame in frames:
        scene.frame_set(frame)
        path = dest_dir / f"f_{frame:04d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        out.append(path)
    return out


def _encode(frames_dir: Path, fps: int, dest: Path, ffmpeg: str = "ffmpeg") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-v", "error", "-framerate", str(fps), "-start_number", "1",
           "-i", str(frames_dir / "f_%04d.png"), "-c:v", "libx264", "-crf", "16",
           "-pix_fmt", "yuv420p", str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg nije uspeo: {proc.stderr.strip()[-500:]}")
    return dest


def render_video(kind: str, dest: Path, engine: str = "cycles",
                 samples: int | None = None, depth_mode: str = "inverse",
                 ffmpeg: str = "ffmpeg") -> Path:
    """kind: 'layout' ili 'depth'. Renderuje ceo kadar (frame_start..frame_end) u mp4."""
    scene = bpy.context.scene
    frames = list(range(scene.frame_start, scene.frame_end + 1))
    layer = bpy.context.view_layer
    if kind == "depth":
        near, far = depth_range([frames[0], frames[len(frames) // 2], frames[-1]])
        set_engine("cycles" if engine == "workbench" else engine, samples or 4, denoise=False)
        layer.material_override = depth_material(near, far, depth_mode)
        scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0
        set_view(raw=True)
    else:
        set_engine(engine, samples or 32)
        layer.material_override = None
        set_view(raw=False)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _render_frames(Path(tmp), frames)
            return _encode(Path(tmp), scene.render.fps, dest, ffmpeg)
    finally:
        layer.material_override = None
        scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6


def render_still(dest: Path, frame: int, engine: str = "cycles", samples: int = 32) -> Path:
    """Jedna slika iz kamere kadra; agent je gleda i poredi sa slikom lokacije."""
    set_engine(engine, samples)
    set_view(raw=False)
    bpy.context.view_layer.material_override = None
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        (path,) = _render_frames(Path(tmp), [frame])
        shutil.copy(path, dest)
    return dest
