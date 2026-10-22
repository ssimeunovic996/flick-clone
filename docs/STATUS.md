# Status projekta

Ažurira se posle svakog koraka: datum, šta je urađeno, gde su fajlovi, izmereno vreme i VRAM.

## Urađeno

- [x] 2026-10-21: Analiza videa i Flick aplikacije, izbor lokalnog puta. Izveštaj: https://claude.ai/artifact/U3nMybyEG5oVuhh7JwdrDY
- [x] 2026-10-21: Reverse engineering Flick-a (`docs/FLICK-REVERSE-ENGINEERING.md`)
- [x] 2026-10-21: Uputstvo, arhitektura i promptovi u ovom folderu
- [x] 2026-10-22: GitHub repo `ssimeunovic996/flick-clone` (privatni)
- [x] 2026-10-22: Kod za Fazu 1 i osnovu Faze 2 napisan i testiran bez GPU-a, grana `claude/faza-1-pipeline` (pull request). Testovi: `python -m pytest` (69 testova; 4 Blender render testa se pokreću samo Python-om koji ima `bpy`, ostali svuda)

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

- [x] 1.1 Format `shotlist.json` sa proverom (`pipeline/shotlist.py`), primer u `projects/primer/`
- [x] 1.2 Skripte napisane i testirane bez GPU-a: `pipeline/` (comfy_client, gen_refs, gen_voice, gen_video, review, assemble, run)
- [x] 1.3 Šablon prompta (`pipeline/prompts.py`, opis u `pipeline/prompt_template.md`)
- [x] 1.2b-1 2026-10-22: `comfy-workflows/minimax-h3.api.json` + `.slots.json` (MiniMax H3, LoRA od 4 koraka), napravljen po Stefanovom "H3 MAIN" i proveren na njegovom ComfyUI-ju (`comfy validate`: bez grešaka)
- [x] 1.2b-2 2026-10-22: Workflow `slika` (Qwen Image 2.1 int8 + Lightning LoRA od 4 koraka, 736x1280): reference sheet lika ~11 s, prva početna slika ~13 s sa učitavanjem modela, svaka sledeća 2 do 3 s. Kasnije `ltx-i2v` i `ltx-a2v`
- [x] 1.2c 2026-10-22: Prvi pravi test na GPU-u, kadar s01 filma "Day 412": MiniMax H3, 736x1280, 124 frejma (5,17 s) sa H3 zvukom, 8 koraka. Vreme: oko 3 do 3,5 min po kadru, sa učitavanjem modela. VRAM: tokom generisanja ~1 GB slobodno od 16 (pun), RAM ~3,7 GB slobodno od 32. Fajl: `projects/dan-412/kadrovi/s01_t1.mp4`
- [x] 1.2d 2026-10-22: ai33 glas u pipeline-u (v3 API, provera posla, krediti u `check`, spisak glasova `python -m pipeline.gen_voice glasovi`). Fali izbor glasa
- [x] 1.4a 2026-10-22: Scenario i `shotlist.json` za prvi film "Day 412" (`projects/dan-412/`): 10 s, 9:16 za Shorts, 2 kadra `minimax-h3` (LoRA od 4 koraka), glas preko radija (55 karaktera, ElevenLabs preko ai33). Fali ID glasa i ai33 adresa u `.env`
- [x] 1.2e 2026-10-22: Krajnja slika kadra: `minimax-h3` prima i `last_frame` (slot `end_image`), kadar u `shotlist.json` dobija `end_moment` i `end_frame`. "Day 412" s02, pokušaj 3 (seed 41225, ~2 min): obrt iz mrlja u cvet i kanticu sada radi
- [x] 1.2f 2026-10-22: Pre prvog videa pipeline isprazni ComfyUI memoriju (`/free`). Bez toga H3 posle Qwen slika pada sa "hostbuf_file_reader_read failed" (RAM je bio 2,5 GB slobodan od 32)
- [ ] 1.4 Prvi film u `projects/dan-412/final/film.mp4` (vreme po kadru: ___, VRAM: ___)

## Faza 2: 3D blokiranje u Blenderu

- [x] 2.0 Format `.ops.json` i `blender/stage.py` (read, still, render, build), testirano bez prozora sa Blender 4.5
- [ ] 2.1 Slika → 3D scena (grubo pa detaljno), `.ops.json`: alat postoji, ostaje prava lokacija sa slike
- [ ] 2.2 Figure likova: lutke od primitiva (stoji, sedi) gotove; rigovane animacije po potrebi
- [x] 2.3 `blender/camera_moves.py`: 16 pokreta (dolly, truck, dolly zoom, crane, pan, tilt, orbit, spirala, zoom, putanja) + drhtanje iz ruke
- [x] 2.4 Render layout-a i dubine po kadru (8k+1 frejmova); ostaje merenje brzine na GPU-u
- [x] 2.4b 2026-10-22: `pipeline/gen_layout.py`: korak `refs` sam renderuje layout slike iz Blendera (početak i kraj kadra, `kadrovi/layout/`), putanja do Blendera u `BLENDER` u `.env`. Proveren sa Blender 4.5.3 i 5.2.3 LTS (Stefan instalira 5.2.3)
- [ ] 2.5 Video iz 3D-a. Bez LTX-a ide preko slika: Blender layout → Qwen "Layout to Render" → MiniMax H3 sa početnom i krajnjom slikom. Test film `projects/radio/` (kuhinja, Mila i deda Rade, 3 kadra, 16:9 1280x736):
  - [x] Slike: Qwen ~10 s po slici (6 s kad je prompt keširan). s01 orbit: početna i krajnja iz 3D-a; s02: samo početna; s03: početna iz 3D-a, krajnja kao izmena početne
  - [x] s01 (orbit, početna + krajnja): kamera ide oko Mile kao u 3D-u, lampa trepne. `projects/radio/kadrovi/s01_t1.mp4`
  - [x] s02 (samo početna, dolly in iz prompta): Mila okreće dugme radija i progovori. s03 (početna iz 3D-a, krajnja kao izmena): Mila u prvom planu okrene glavu ka dedi u vratima
  - [x] H3 1280x736, 124 frejma: oko 2,2 do 2,6 min po kadru kad je model učitan, oko 3 min sa učitavanjem. Probni spoj: `projects/_testovi/radio/pregled_radio_s01_s02_s03.mp4`
  - [ ] Glas: H3 sam pravi zvuk i govor; ElevenLabs glas (ai33) za dijaloge još nije proban
- [ ] 2.6 MCP alati za scenu

## Faza 3: Web aplikacija

- [ ] Backend (FastAPI + SQLite)
- [ ] Story, Canvas, Stage, Video Editor
- [ ] MCP alati aplikacije za Claude Code
- [ ] Ceo film kroz aplikaciju

## Faza 4: three.js 3D Stage (opciono)

- [ ] Odluka da li je potrebna
