# Blender: 3D blokiranje kadrova

Naša verzija Flick-ovog Convert to 3D i 3D Stage-a. Scena se opisuje kao lista operacija u `.ops.json` (kao Flick-ov tok `add`/`remove`), a `stage.py` je gradi u Blenderu bez prozora i renderuje kontrolne videe za video model.

Claude Code ne mora da klikće po Blenderu: piše `.ops.json`, renderuje sliku iz kamere, pogleda je i popravlja. Blender MCP ostaje opcija za ručnu doradu.

## Komande

Na Windows-u je Blender obično `"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"`; ovde piše samo `blender`.

```
blender -b --python blender/stage.py -- read   projects/<film>/lokacije/kuhinja.ops.json
blender -b --python blender/stage.py -- still  projects/<film>/lokacije/kuhinja.ops.json --shot s02 --t 2.5
blender -b --python blender/stage.py -- render projects/<film>/lokacije/kuhinja.ops.json --shot s02
blender -b --python blender/stage.py -- build  projects/<film>/lokacije/kuhinja.ops.json --shot s02
```

| Komanda | Šta radi |
|---|---|
| `read` | pregled scene: objekti po grupama, kadrovi, pokreti (radi i bez Blendera: `python blender/stage.py read ...`) |
| `still` | jedna slika iz kamere kadra u trenutku `--t`, za poređenje sa slikom lokacije |
| `render` | `<scena>_<kadar>_layout.mp4` i `<scena>_<kadar>_depth.mp4`, sa istim brojem frejmova kao LTX video (8k+1) |
| `build` | `.blend` sa animiranim kadrom, za ručnu doradu |

Opcije: `--scale 0.5` (brz pregled u pola rezolucije), `--samples N`, `--engine cycles|eevee|workbench` (podrazumevano Cycles, na tvojoj kartici ide preko GPU-a), `--passes layout|depth`, `--depth-mode inverse|linear`, `--out`.

Dubina je bela blizu kamere i crna daleko. Raspon se meri brzim probnim renderom (1. i 99. percentil onoga što kamera stvarno vidi) i važi za ceo kadar, da mapa ne treperi. `inverse` liči na Depth Anything; ako LTX Union bolje radi sa `linear`, to se upisuje u `docs/ODLUKE.md`. Druga opcija koju vredi probati u Fazi 2.5: pustiti `layout` video kroz isti depth preprocesor koji koristi ComfyUI workflow.

Kad je kontrolni video gotov, kadar u `shotlist.json` dobija:

```json
"control": { "type": "depth", "video": "lokacije/kuhinja_s02_depth.mp4" },
"model": "ltx-control"
```

## Format `.ops.json`

Koordinate su kao u three.js (da isti fajl kasnije koristi i Faza 4): **Y je gore**, metri, uglovi u stepenima. Pod je na `y = 0`, kamera "gleda" ka `-Z` kad nema rotaciju.

Operacije se izvršavaju redom:

| `op` | Polja | Značenje |
|---|---|---|
| `add` | `id`, `shape` (`box`, `cylinder`, `sphere`, `cone`, `plane`), `pos` (centar), `size` [širina, visina, dubina], `rot`, `color`, `group`, `pass` | primitiv; oblik staje tačno u `size` |
| `add` | `id`, `type: "figure"`, `pos` (stopala), `height`, `pose` (`stand`, `sit`), `facing` ili `look_at`, `color` | lutka za lik; `facing: 0` gleda ka +Z, 90 ka +X |
| `add` | `id`, `type: "camera"`, `pos`, `look_at` (tačka ili id objekta) ili `rot`, `lens_mm`, `aspect`, `roll` | kamera; `look_at` na figuru cilja visinu očiju |
| `add` | `id`, `type: "light"`, `kind` (`point`, `sun`, `area`, `spot`), `pos`, `look_at`, `energy`, `color` | svetlo; bez svetla dobija se jedno sunce |
| `update` | `id` + polja | menja postojeći objekat |
| `remove` | `id` | briše objekat |
| `shot` | `id` (isti kao u shotlist-u), `camera`, `duration`, `fps`, `resolution`, `frames` (`8k+1` ili `exact`) | kadar |
| `camera_move` | `shot`, `move`, `start`, `end`, `ease` + polja pokreta, `handheld` | pokret kamere u kadru |
| `keyframe` | `shot`, `id`, `t`, `pos`, `facing`, `ease` | gde je objekat u trenutku `t` |
| `path` | `shot`, `id`, `points`, `start`, `end`, `face_direction` | objekat hoda kroz tačke i okreće se u pravcu hoda |

`color` je `#rrggbb` ili ime: yellow, blue, purple, red, green, orange, pink, cyan, white, grey, black. Figure likova imaju istu boju kao `color` lika u `shotlist.json`, jer prompt kaže "Mila (the yellow figure in the control video)".

### Pokreti kamere

| `move` | Polja | Šta radi |
|---|---|---|
| `static` | | ništa |
| `dolly_in`, `dolly_out` | `distance` | napred ili nazad duž pravca gledanja |
| `truck_left`, `truck_right` | `distance` | bočno klizanje |
| `dolly_zoom` | `distance` | prilazi meti, a žižna daljina se menja da subjekat ostane iste veličine (Vertigo) |
| `crane_up`, `crane_down` | `height` | diže se ili spušta, ostaje uperena u metu |
| `pan_left`, `pan_right` | `degrees` | okreće se u mestu |
| `tilt_up`, `tilt_down` | `degrees` | naginje se u mestu |
| `orbit` | `degrees`, `target` | kruži oko mete (pozitivno: suprotno od kazaljke gledano odozgo) |
| `spiral` | `degrees`, `radius_factor`, `height`, `target` | orbit uz približavanje i dizanje |
| `zoom` | `lens_end` | menja samo žižnu daljinu |
| `path` | `points`, `target` | kamera ide kroz tačke; bez `target` gleda napred duž puta |

`ease`: `linear`, `in`, `out`, `in_out` (podrazumevano). `handheld: 0.01` dodaje blago drhtanje iz ruke. Više pokreta u istom kadru ide redom po `start`. Isti nazivi pokreta su i u `camera.move` u `shotlist.json`.

## Kako Claude Code pravi scenu iz slike (Convert to 3D)

1. Pogleda sliku lokacije i proceni razmere u metrima (vrata su oko 2.1 m, sto oko 0.75 m, plafon 2.6 do 2.8 m).
2. Grubi prolaz (`"pass": "rough"`): pod, zidovi, plafon, otvori, veliki nameštaj.
3. Detaljni prolaz (`"pass": "detail"`): imenovani objekti od delova u grupama ("Sto" = ploča i četiri noge), boje sa slike.
4. Kamera sa `lens_mm` i pozicijom tako da `still` kadrira kao slika; poredi i popravlja dok raspored ne odgovara.
5. Figure likova, kadrovi, pokreti i putanje; `render` za svaki kadar.

Primer: `blender/primeri/kuhinja.ops.json` (kuhinja iz probnog filma `projects/primer`, tri kadra).
