# Arhitektura klona

## Tok rada

```
ideja → scenario.md → shotlist.json → reference (likovi, lokacije)
                                     → glas (ElevenLabs)        → audio/
                                     → 3D blokiranje (Blender)  → dubina / playblast
                                     → video (ComfyUI: LTX-2.5 ili MiniMax H3) → kadrovi/
                                     → montaža (ffmpeg)         → final/film.mp4
```

Agent je Claude Code (Stefanova pretplata). On piše scenario i listu kadrova, poziva skripte i alate, i sam pregleda rezultate.

## Struktura foldera

```
D:\Flick klon\
  CLAUDE.md                kontekst za Claude Code
  README.md                kratak pregled
  .env                     ključevi (nije u git-u)
  docs\                    uputstvo, status, odluke, arhitektura, nalazi o Flick-u
  prompts\                 gotovi promptovi po fazama
  comfy-workflows\         ComfyUI workflow JSON fajlovi koje koristimo
  pipeline\                Python skripte (Faza 1)
  blender\                 Blender skripte i alati (Faza 2)
  app\                     web aplikacija (Faza 3)
  projects\
    _testovi\              rezultati Faze 0
    <ime-filma>\
      scenario.md
      shotlist.json
      likovi\              reference sheet-ovi i opisi likova
      lokacije\            slike lokacija, .blend i .ops.json scene
      audio\               glas po kadru, muzika, efekti
      kadrovi\             generisani klipovi (svi pokušaji)
      final\               montiran film
```

## shotlist.json (predlog formata)

```json
{
  "film": "ime-filma",
  "format": { "aspect": "16:9", "fps": 24, "resolution": [1280, 720] },
  "style": "kratak opis vizuelnog stila",
  "characters": {
    "marko": { "ref": "likovi/marko_sheet.png", "color": "blue", "voice_id": "elevenlabs-voice-id" }
  },
  "shots": [
    {
      "id": "s01",
      "duration": 5,
      "location": "lokacije/kuhinja.png",
      "characters": ["marko"],
      "camera": { "shot": "medium", "move": "dolly_in", "lens_mm": 35 },
      "action": "0-2 s: Marko ulazi; 2-5 s: zastaje kod prozora",
      "dialogue": [{ "who": "marko", "text": "Opet kasniš." }],
      "control": { "type": "depth", "video": "lokacije/kuhinja_s01_depth.mp4" },
      "model": "ltx-2.5-a2v",
      "seed": 1234,
      "status": "todo",
      "takes": []
    }
  ]
}
```

`status` ide redom: `todo` → `audio_ok` → `video_ok` → `approved`. U `takes` se beleži svaki pokušaj (fajl, seed, vreme generisanja, ocena).

## 3D scena kao lista operacija

Po uzoru na Flick (njihov servis vraća tok operacija `add` / `remove`), scena se čuva i kao `.ops.json`:

```json
[
  { "op": "add", "id": "rear_wall", "group": "Zadnji zid sa dva prozora", "shape": "box",
    "pos": [0, 1.4, -3], "rot": [0, 0, 0], "size": [6, 2.8, 0.15], "color": "#d9d4cc", "pass": "rough" },
  { "op": "add", "id": "camera_main", "type": "camera", "pos": [3, 1.7, 2.65], "lens_mm": 24, "aspect": "16:9" }
]
```

Tako Claude Code može scenu da sastavi iz početka, izmeni jedan objekat ili je prenese u three.js u Fazi 4.

## Alati agenta (MCP), po uzoru na Flick

Flick-ov agent koristi ove alate (izvučeno iz njihovog koda): `stage_read`, `stage_object`, `stage_camera`, `add_track`, `add_transform_item`, `add_camera_action`, `add_keyframe`, `add_path`, `set_shot`, `set_target`, `look_at_scene`, `search_props`, `remove_item`, pokreti kamere (`crane_up/down`, `dolly_in/out`, `dolly_zoom`, `pan_sweep`), `generate_images`, `image_to_video`, `generate_dialog`, `generate_music`, `choose_voice`, `timeline_edit`, `clip_edit`, `extract_frame`, `inspect_media`.

Naš minimalni skup:

| Alat | Šta radi |
|---|---|
| `scene_read` | vraća objekte, kamere i trajanje scene |
| `scene_build_from_image` | gradi scenu od primitiva iz slike (grubo pa detaljno) |
| `add_object` / `remove_object` | primitiv ili rekvizit sa imenom, pozicijom, veličinom i bojom |
| `add_figure` | obojena lutka za lik, sa animacijom |
| `set_camera` / `camera_move` | kamera, žižna daljina, format, pokret |
| `add_keyframe` / `add_path` | pomeranje lika ili kamere kroz vreme |
| `look_at_scene` | render jednog frejma da agent vidi rezultat |
| `render_take` | playblast i mapa dubine za kadar |
| `generate_video` | šalje kadar u ComfyUI po `shotlist.json` |
| `assemble` | montaža filma |
