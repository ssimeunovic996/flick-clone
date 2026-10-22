"""Komanda za 3D scene iz .ops.json. Radi u Blenderu bez prozora:

    blender -b --python blender/stage.py -- read     lokacije/kuhinja.ops.json
    blender -b --python blender/stage.py -- still    lokacije/kuhinja.ops.json --shot s01 --t 2.5
    blender -b --python blender/stage.py -- render   lokacije/kuhinja.ops.json --shot s01
    blender -b --python blender/stage.py -- build    lokacije/kuhinja.ops.json --shot s01

read    pregled scene (objekti po grupama, kadrovi, pokreti); ne treba mu Blender
still   jedna slika iz kamere kadra u trenutku --t, za poređenje sa slikom lokacije
render  layout i dubina za kadar kao mp4, sa istim brojem frejmova kao LTX video
build   sačuva .blend sa animiranim kadrom, da se otvori i doradi ručno

Na Windows-u je blender obično "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scene_ops  # noqa: E402


def parse(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="stage.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["read", "still", "render", "build"])
    p.add_argument("ops", type=Path, help="putanja do .ops.json")
    p.add_argument("--shot", help="id kadra (podrazumevano prvi)")
    p.add_argument("--t", type=float, default=0.0, help="trenutak za still, u sekundama")
    p.add_argument("--passes", default="layout,depth", help="za render: layout, depth ili oba")
    p.add_argument("--out", type=Path, help="izlazni fajl (still, build) ili folder (render)")
    p.add_argument("--engine", default="cycles", choices=["cycles", "eevee", "workbench"])
    p.add_argument("--samples", type=int)
    p.add_argument("--depth-mode", default="inverse", choices=["inverse", "linear"])
    p.add_argument("--scale", type=float, default=1.0, help="npr. 0.5 za brz pregled u pola rezolucije")
    p.add_argument("--ffmpeg", default="ffmpeg")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):  # srpska slova kroz pipe na Windows-u
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse(argv)
    try:
        stage = scene_ops.Stage.load(args.ops)
    except scene_ops.OpsError as e:
        print(e, file=sys.stderr)
        return 2
    if args.command == "read":
        print(stage.summary())
        return 0

    import blender_render  # noqa: E402 - traži bpy
    import blender_scene  # noqa: E402

    import bpy

    shot = stage.shot(args.shot)
    sid = shot["id"]
    made = blender_scene.build(stage)
    blender_scene.animate(stage, made, sid)
    scene = bpy.context.scene
    scene.render.resolution_percentage = int(round(args.scale * 100))
    base = args.ops.name.removesuffix(".ops.json").removesuffix(".json")

    if args.command == "still":
        frame = min(scene.frame_end, int(round(args.t * stage.fps(sid))) + 1)
        dest = args.out or args.ops.parent / f"{base}_{sid}_t{args.t:g}.png"
        blender_render.render_still(dest, frame, args.engine, args.samples or 32)
        print(f"slika: {dest}")
    elif args.command == "render":
        out_dir = args.out or args.ops.parent
        for kind in [k.strip() for k in args.passes.split(",") if k.strip()]:
            if kind not in ("layout", "depth"):
                print(f"nepoznat prolaz '{kind}'", file=sys.stderr)
                return 2
            dest = out_dir / f"{base}_{sid}_{kind}.mp4"
            blender_render.render_video(kind, dest, args.engine, args.samples, args.depth_mode, args.ffmpeg)
            print(f"{kind}: {dest} ({stage.frame_count(sid)} frejmova, {stage.fps(sid)} fps)")
        print('u shotlist.json: "control": {"type": "depth", "video": "<putanja do _depth.mp4 '
              'u odnosu na folder filma>"}')
    elif args.command == "build":
        dest = (args.out or args.ops.parent / f"{base}.blend").resolve()
        bpy.ops.wm.save_as_mainfile(filepath=str(dest))
        print(f"blend: {dest}")
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    sys.exit(main(argv))
