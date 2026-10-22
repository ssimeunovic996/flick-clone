"""Glavna komanda pipeline-a.

    python -m pipeline.run projects/<film> check              provera liste, ComfyUI-ja i cene glasa
    python -m pipeline.run projects/<film> voice              glas za kadrove sa dijalogom (ElevenLabs)
    python -m pipeline.run projects/<film> refs               reference sheet-ovi i početne slike
    python -m pipeline.run projects/<film> video              video za kadrove kojima fali
    python -m pipeline.run projects/<film> review             frejmovi za pregled i pregled.md
    python -m pipeline.run projects/<film> approve s01 [--take 2]
    python -m pipeline.run projects/<film> assemble [--draft] montaža u final/
    python -m pipeline.run projects/<film> all                voice, refs, video i review redom

Opcije: --shots s01,s03 (samo ti kadrovi), --force (novi pokušaj i za gotove kadrove),
--dry-run (pokaže šta bi uradio i prompt, ništa ne šalje).
Gotovi koraci se preskaču, pa se komanda može pokrenuti ponovo posle prekida.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import assemble, gen_refs, gen_video, gen_voice, review, shotlist, workflows
from .comfy_client import ComfyClient, ComfyError
from .config import Settings
from .media import MediaError


def cmd_check(data, project, settings, args) -> int:
    print(f"Film: {data.get('film', project.name)}, {len(data['shots'])} kadrova, "
          f"{sum(s['duration'] for s in data['shots'])} s ukupno")
    ok = True
    for model in sorted({shotlist.shot_model(data, s) for s in data["shots"]}):
        try:
            workflows.load(model, settings.workflows_dir)
            print(f"  workflow {model}: u redu")
        except workflows.WorkflowError as e:
            ok = False
            print(f"  workflow {model}: {e}")
    try:
        workflows.load(gen_refs.image_workflow(data), settings.workflows_dir)
    except workflows.WorkflowError as e:
        print(f"  workflow za slike: {e}")
    voice_shots = gen_voice.pending(data, project, args.only)
    chars = gen_voice.characters_needed(voice_shots)
    print(f"  glas: {len(voice_shots)} kadrova čeka, {chars} karaktera teksta za ElevenLabs")
    if voice_shots and not settings.elevenlabs_api_key:
        print("  ELEVENLABS_API_KEY nije podešen u .env")
    try:
        stats = ComfyClient(settings.comfyui_url).system_stats()
        dev = (stats.get("devices") or [{}])[0]
        free = dev.get("vram_free", 0) / 2**30
        print(f"  ComfyUI radi: {dev.get('name', '?')}, slobodno {free:.1f} GB VRAM")
    except Exception as e:  # noqa: BLE001 - samo izveštaj
        ok = False
        print(f"  ComfyUI: {e}")
    for shot in data["shots"]:
        takes = shot.get("takes", [])
        print(f"  {shot['id']}: {shot.get('status', 'todo')}, {len(takes)} pokušaja")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m pipeline.run", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("project", type=Path, help="folder filma, npr. projects/prvi-film")
    p.add_argument("command", choices=["check", "voice", "refs", "video", "review", "approve", "assemble", "all"])
    p.add_argument("shot", nargs="?", help="kadar za approve")
    p.add_argument("--shots", help="lista kadrova odvojenih zarezom")
    p.add_argument("--take", type=int, help="broj pokušaja za approve (podrazumevano najnoviji)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--draft", action="store_true", help="montaža i sa neodobrenim kadrovima")
    args = p.parse_args(argv)
    args.only = set(args.shots.split(",")) if args.shots else None

    project = args.project.resolve()
    settings = Settings.from_env()
    try:
        data = shotlist.load(project)
    except (FileNotFoundError, shotlist.ShotlistError) as e:
        print(e, file=sys.stderr)
        return 2

    def save() -> None:
        if not args.dry_run:
            shotlist.save(project, data)

    try:
        if args.command == "check":
            return cmd_check(data, project, settings, args)
        if args.command == "approve":
            if not args.shot:
                p.error("approve traži id kadra, npr. approve s01")
            shot = next((s for s in data["shots"] if s["id"] == args.shot), None)
            if shot is None:
                p.error(f"kadar {args.shot} ne postoji")
            take = review.approve(shot, args.take)
            save()
            print(f"kadar {shot['id']}: odobren pokušaj {take['n']} ({take['file']})")
            return 0
        if args.command == "assemble":
            assemble.assemble(data, project, settings, draft=args.draft)
            return 0

        steps = ["voice", "refs", "video", "review"] if args.command == "all" else [args.command]
        client = None if args.dry_run else ComfyClient(settings.comfyui_url)
        problems: list[str] = []
        for step in steps:
            if step == "voice":
                todo = gen_voice.pending(data, project, args.only)
                print(f"glas: {len(todo)} kadrova, {gen_voice.characters_needed(todo)} karaktera")
                if not args.dry_run and todo:
                    for w in gen_voice.generate(data, project, settings, args.only):
                        print("upozorenje:", w)
                    save()
            elif step == "refs":
                if args.dry_run:
                    print("refs: likovi bez sheet-a:", gen_refs.missing_sheets(data, project) or "nema")
                    print("refs: kadrovi bez početne slike:",
                          [s["id"] for s in gen_refs.missing_start_frames(
                              data, project, args.only, settings.workflows_dir)] or "nema")
                else:
                    gen_refs.generate(data, project, client, settings, args.only, settings.workflows_dir)
                    save()
            elif step == "video":
                problems += gen_video.generate(data, project, client, settings, args.only, args.force,
                                               args.dry_run, settings.workflows_dir, save=save)
            elif step == "review" and not args.dry_run:
                print(f"pregled: {review.build(data, project, settings, args.only).relative_to(project)}")
        if problems:
            print("\nNisu urađeni:\n- " + "\n- ".join(problems))
            return 1
        return 0
    except (ComfyError, MediaError, workflows.WorkflowError, gen_voice.VoiceError,
            assemble.AssembleError, ValueError) as e:
        save()
        print(f"greška: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
