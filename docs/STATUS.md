# Status projekta

Ažurira se posle svakog koraka: datum, šta je urađeno, gde su fajlovi, izmereno vreme i VRAM.

## Urađeno

- [x] 2026-10-21: Analiza videa i Flick aplikacije, izbor lokalnog puta. Izveštaj: https://claude.ai/artifact/U3nMybyEG5oVuhh7JwdrDY
- [x] 2026-10-21: Reverse engineering Flick-a (`docs/FLICK-REVERSE-ENGINEERING.md`)
- [x] 2026-10-21: Uputstvo, arhitektura i promptovi u ovom folderu

## Faza 0: Priprema i testovi

- [ ] 0.1 Osnovni programi (Git, Python, uv, Node, ffmpeg, Blender)
- [ ] 0.2 Claude Code u `D:\Flick klon`, git init, struktura foldera
- [ ] 0.3 ComfyUI ažuriran; LTX-2.5 NVFP4, Gemma enkoder, IC-LoRA Ingredients, Union, Layout to Render; workflow-i u `comfy-workflows/`
- [ ] 0.4 Blender MCP povezan; ComfyUI API radi; `ELEVENLABS_API_KEY` u `.env`
- [ ] 0.5 Test 1: brzina LTX-2.5 I2V (vreme: ___, VRAM: ___)
- [ ] 0.5 Test 2: konzistentnost lika, LTX-2.5 Ingredients naspram MiniMax H3
- [ ] 0.5 Test 3: ElevenLabs glas + LTX-2.5 A2V
- [ ] 0.5 Test 4: Blender dubina → LTX-2.5 Union
- [ ] Odluka o glavnom modelu upisana u `docs/ODLUKE.md`

## Faza 1: Pipeline

- [ ] 1.1 Struktura filma i `shotlist.json`
- [ ] 1.2 Skripte: comfy_client, gen_refs, gen_voice, gen_video, assemble, run
- [ ] 1.3 Šablon prompta
- [ ] 1.4 Prvi film u `projects/<film>/final/film.mp4`

## Faza 2: 3D blokiranje u Blenderu

- [ ] 2.1 Slika → 3D scena (grubo pa detaljno), `.ops.json`
- [ ] 2.2 Figure likova sa animacijama
- [ ] 2.3 `blender/camera_moves.py`
- [ ] 2.4 Render playblast-a i dubine po kadru
- [ ] 2.5 Video iz 3D-a (Union / Layout to Render / Ingredients)
- [ ] 2.6 MCP alati za scenu

## Faza 3: Web aplikacija

- [ ] Backend (FastAPI + SQLite)
- [ ] Story, Canvas, Stage, Video Editor
- [ ] MCP alati aplikacije za Claude Code
- [ ] Ceo film kroz aplikaciju

## Faza 4: three.js 3D Stage (opciono)

- [ ] Odluka da li je potrebna
