# Flick klon: kontekst za Claude Code

Ovaj fajl Claude Code čita na početku svake sesije u folderu `D:\Flick klon`. Sadrži sve što treba da znaš da bi nastavio rad bez ponovnog pitanja.

## Ko i šta

- Korisnik: Stefan. Piše na srpskom; odgovaraj na srpskom. Pretrage i izvori na engleskom.
- Cilj: kratki AI filmovi za YouTube, napravljeni lokalno. Uzor je aplikacija Flick (flick.art). Kloniramo njen način rada, ne njen kvalitet zatvorenih modela.
- Ti (Claude Code, na Stefanovoj pretplati) si agent aplikacije: pišeš scenarije i liste kadrova, upravljaš ComfyUI-jem, Blenderom i ffmpeg-om i sam pregledaš rezultate.

## Hardver i ograničenja (ne menjaj bez Stefanovog odobrenja)

- RTX 5070 Ti, 16 GB VRAM; 32 GB RAM; Windows.
- Sve radi lokalno na ovom računaru. Bez Remote Control-a i bez cloud GPU-a.
- Video modeli: LTX-2.5 (glavni kandidat) i MiniMax H3 (Stefan ga je testirao, dobar za reference). Konačan izbor posle Faze 0, upisan u `docs/ODLUKE.md`.
- **Ne koristimo Seedance** (ni 2.5 ni druge verzije) ni ComfyUI Partner Nodes.
- Slike: Stefanovi lokalni modeli za slike, ne Nano Banana.
- Jedini plaćeni servis: **ElevenLabs API** (glas), poziva se direktno ključem iz `.env`.
- Ne pokreći ništa što troši novac ili kredite bez pitanja.

## Arhitektura ukratko

Detaljno u `docs/ARHITEKTURA.md`.

1. Scenario → lista kadrova (`shotlist.json`, kadrovi od 4 do 5 s) → reference likova i lokacija.
2. Glas: ElevenLabs → `audio/` po kadru.
3. 3D blokiranje (Faza 2): Blender preko Blender MCP-a; scena od primitiva po slici lokacije, figure, kamere, render mape dubine i playblast-a.
4. Video: ComfyUI API, LTX-2.5 (I2V, A2V za govor, IC-LoRA Ingredients za lik, Union/Layout to Render za 3D kontrolu) ili MiniMax H3.
5. Montaža: ffmpeg → `final/`.

## Kako radiš u ovom folderu

- Na početku sesije pročitaj `docs/STATUS.md` i nastavi od prvog nezavršenog koraka iz `docs/UPUTSTVO.md`.
- Posle svakog završenog koraka ažuriraj `docs/STATUS.md` (datum, šta je urađeno, gde su fajlovi, izmereno vreme i VRAM).
- Svaku odluku (model, podešavanje, odbačena opcija) upiši u `docs/ODLUKE.md` sa razlogom.
- Kod ide u `pipeline/`, `blender/`, `comfy-workflows/`, kasnije `app/`. Filmovi idu u `projects/<ime-filma>/`.
- Pre GPU testa proveri da ComfyUI radi (`http://127.0.0.1:8188`). Meri vreme generisanja i zabeleži ga.
- Ključevi samo u `.env` (nikad u kodu ni u git-u). `.gitignore` isključuje modele, izlaze i `.env`.
- Gotove promptove za svaku fazu imaš u `prompts/`.

## Šta znamo o Flick-u (reverse engineering, 21. 10. 2026)

Detaljno u `docs/FLICK-REVERSE-ENGINEERING.md`. Najvažnije:

- Convert to 3D je vision model koji "piše" scenu od primitiva (imenovani objekti, ~370 delova za jednu sobu), prvo grubo pa detaljno. To radimo u Blenderu.
- Flick sam hostuje MiniMax H3 kao najjeftiniji model; Seedance 2.5 je skup (48 kredita/s).
- Alati njihovog agenta (scene read, objekat, kamera, keyframe, putanja, snimak) su uzor za naše MCP alate.
