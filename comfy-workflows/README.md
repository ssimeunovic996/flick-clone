# ComfyUI workflow šabloni

Pipeline ne zna ništa o modelima; on samo popunjava polja u workflow-u koji ti izvezeš iz ComfyUI-ja. Zato se novi model dodaje bez menjanja koda: izvezeš workflow, opišeš slotove i upišeš ime u `shotlist.json`.

## Par fajlova po workflow-u

| Fajl | Šta je |
|---|---|
| `<ime>.api.json` | workflow u API formatu: u ComfyUI-ju **Workflow > Export (API)** |
| `<ime>.slots.json` | koja polja pipeline popunjava i kako se pravi prompt |

Ime workflow-a je isto što piše u `model` polju kadra ili u `default_model` filma. Za slike (reference sheet-ovi i početne slike kadrova) pipeline koristi workflow `slika`, osim ako `shotlist.json` ima `image_workflow`.

Workflow-i koje očekujemo posle Faze 0:

| Ime | Model | Za šta |
|---|---|---|
| `slika` | lokalni model slike (npr. Qwen-Image-Edit ili Flux Kontext, sa referencom) | reference sheet-ovi i početne slike |
| `ltx-i2v` | LTX-2.5, slika u video | većina kadrova |
| `ltx-a2v` | LTX-2.5, slika i zvuk u video | kadrovi sa dijalogom (usne prate glas) |
| `ltx-control` | LTX-2.5 sa depth ili layout kontrolom | kadrovi iz Blendera (Faza 2) |
| `minimax-h3` | MiniMax H3 sa LoRA od 4 koraka, slika u video | Stefanov glavni model; prvi film "Day 412" |
| `minimax-h3-ref` | MiniMax H3, referenca lika u video | kadrovi gde je bitna doslednost lika |

## Kako se pravi slots fajl

1. U ComfyUI-ju otvori workflow koji radi i proveri ga jednom ručno.
2. Izvezi ga sa **Workflow > Export (API)** u `comfy-workflows/<ime>.api.json`.
3. Napravi predlog slotova:
   ```
   python -m pipeline.workflows suggest comfy-workflows/<ime>.api.json > comfy-workflows/<ime>.slots.json
   ```
4. Pregledaj predlog uz `python -m pipeline.workflows inspect comfy-workflows/<ime>.api.json` i ispravi šta ne valja. Predlog pogađa po imenima čvorova, pa najčešće treba proveriti `prompt`, `negative` i `output_node`.
5. `python -m pipeline.run projects/<film> check` proverava da li slotovi pokazuju na čvorove koji postoje.

Ovo može Claude Code da uradi sam preko comfy-mcp: otvori workflow, izveze ga i napiše slots fajl.

## Format slots fajla

```json
{
  "slots": {
    "prompt": { "node": "6", "input": "text" },
    "negative": { "node": "7", "input": "text" },
    "image": { "node": "12", "input": "image" },
    "seed": { "node": "25", "input": "noise_seed" },
    "width": { "node": "27", "input": "width" },
    "height": { "node": "27", "input": "height" },
    "frames": [{ "node": "27", "input": "length" }, { "node": "30", "input": "length" }],
    "fps": { "node": "40", "input": "frame_rate" },
    "filename_prefix": { "node": "41", "input": "filename_prefix" }
  },
  "required": ["prompt", "image"],
  "output_node": "41",
  "output_ext": [".mp4"],
  "prompt_mode": "i2v",
  "frames": "8k+1",
  "size_multiple": 32,
  "max_seconds": 10
}
```

| Polje | Značenje |
|---|---|
| `slots` | slot → jedan cilj `{node, input}` ili lista ciljeva. Cilj može imati `scale` (množi broj) i `int` (zaokruži, podrazumevano da) |
| `required` | slotovi bez kojih kadar ne može; pipeline kaže koji korak fali |
| `output_node` | čvor čiji izlaz se preuzima; bez njega se uzima prvi video ili slika |
| `output_ext` | koji tip fajla se uzima kad čvor da više izlaza |
| `prompt_mode` | `i2v`, `a2v` (zvuk vodi usne), `ingredients` (reference sheet), `control` (3D kontrolni video) |
| `frames` | `8k+1` za LTX (5 s pri 24 fps daje 121), `4k+1` za modele kao Wan, ili `exact` (trajanje × fps) |
| `size_multiple` | širina i visina se zaokružuju na ovaj umnožak |
| `max_seconds` | upozorenje ako je kadar duži |

Slotovi koje pipeline zna: `prompt`, `negative`, `image`, `audio`, `control_video`, `reference`, `seed`, `width`, `height`, `frames`, `fps`, `length_seconds`, `filename_prefix`. Slotovi `image`, `audio`, `control_video` i `reference` su fajlovi: pipeline ih prvo pošalje u ComfyUI (`input/flick/`) i upiše ime fajla.

Primeri u `primeri/` pokazuju kako izgledaju slots fajlovi za svaki tip; brojevi čvorova u njima su izmišljeni i moraju se zameniti brojevima iz tvog izvoza.
