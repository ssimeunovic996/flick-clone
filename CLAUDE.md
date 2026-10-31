# Flick klon: kontekst za Claude Code

Ovaj fajl Claude Code čita na početku svake sesije u folderu `D:\Flick klon`. Sadrži sve što treba da znaš da bi nastavio rad bez ponovnog pitanja.

## Ko i šta

- Korisnik: Stefan. Piše na srpskom; odgovaraj na srpskom. Pretrage i izvori na engleskom.
- Cilj: kratki AI filmovi za YouTube, napravljeni lokalno. Uzor je aplikacija Flick (flick.art). Kloniramo njen način rada, ne njen kvalitet zatvorenih modela.
- Ti (Claude Code, na Stefanovoj pretplati) si agent aplikacije: pišeš scenarije i liste kadrova, upravljaš ComfyUI-jem, Blenderom i ffmpeg-om i sam pregledaš rezultate.

## Hardver i ograničenja (ne menjaj bez Stefanovog odobrenja)

- RTX 5070 Ti, 16 GB VRAM; 32 GB RAM; Windows.
- Sve radi lokalno na ovom računaru, bez cloud GPU-a. Remote Control sesija iz Claude niti je dozvoljena (Stefan, 31. 10. 2026): tada Claude Code radi ovde, u D:\Flick klon, i pokreće pipeline direktno.
- Video modeli: **MiniMax H3 sa LoRA od 4 koraka** je Stefanov izbor (već instaliran; workflow `minimax-h3`). LTX-2.5 ostaje za A2V govor i kontrolu iz 3D-a. Detalji u `docs/ODLUKE.md`.
- **Ne koristimo Seedance** (ni 2.5 ni druge verzije) ni ComfyUI Partner Nodes.
- Slike: Stefanovi lokalni modeli za slike, ne Nano Banana.
- Jedini plaćeni servis: **ElevenLabs glas preko ai33** (servis sa ElevenLabs API-jem), ključ i adresa u `.env` (`ELEVENLABS_API_KEY`, `ELEVENLABS_BASE_URL`, po potrebi `ELEVENLABS_TASK_URL`).
- Ne pokreći ništa što troši novac ili kredite bez pitanja.

## Arhitektura ukratko

Detaljno u `docs/ARHITEKTURA.md`.

1. Scenario → lista kadrova (`shotlist.json`, kadrovi od 4 do 5 s) → reference likova i lokacija.
2. Glas: ElevenLabs → `audio/` po kadru.
3. 3D blokiranje (Faza 2): `blender/stage.py` gradi scenu od primitiva iz `.ops.json` u Blenderu bez prozora (figure, kamere, pokreti), renderuje mapu dubine i layout video. Blender MCP je za ručnu doradu.
4. Video: ComfyUI API, MiniMax H3 sa LoRA od 4 koraka (glavni) ili LTX-2.5 (A2V za govor, IC-LoRA Ingredients za lik, Union/Layout to Render za 3D kontrolu).
5. Montaža: ffmpeg → `final/`.

## Kako radiš u ovom folderu

- Na početku sesije pročitaj `docs/STATUS.md` i nastavi od prvog nezavršenog koraka iz `docs/UPUTSTVO.md`.
- Posle svakog završenog koraka ažuriraj `docs/STATUS.md` (datum, šta je urađeno, gde su fajlovi, izmereno vreme i VRAM).
- Svaku odluku (model, podešavanje, odbačena opcija) upiši u `docs/ODLUKE.md` sa razlogom.
- Kod ide u `pipeline/`, `blender/`, `comfy-workflows/`, kasnije `app/`. Filmovi idu u `projects/<ime-filma>/`.
- Pre GPU testa proveri da ComfyUI radi (`http://127.0.0.1:8188`). Meri vreme generisanja i zabeleži ga.
- Ključevi samo u `.env` (nikad u kodu ni u git-u). `.gitignore` isključuje modele, izlaze i `.env`.
- Gotove promptove za svaku fazu imaš u `prompts/`.
- Repo: GitHub `ssimeunovic996/flick-clone` (privatni). Pre izmene koda pokreni `python -m pytest`; testovi ne traže GPU.
- Pipeline: `python -m pipeline.run projects/<film> check|voice|refs|video|review|approve|assemble|all` (uputstvo u `pipeline/run.py`). Model kadra je ime workflow-a u `comfy-workflows/`.
- Za svaki kadar sam napiši `image_prompt` i `video_prompt` u `shotlist.json` (pravila i primer u `pipeline/prompt_template.md`); šablon je samo rezerva. H3 dobija samo početnu sliku, osim kad kadar mora da završi baš određeno. 3D blokiranje koristi samo kad su bitni tačna kamera ili raspored likova, i tada scenu opremi pravim nameštajem.
- Kad Stefan hoće sam da postavi likove i kameru: `python -m pipeline.run projects/<film> postavka --shots <kadar>`, pa on uređuje `lokacije/<kadar>_postavka.blend` (uputstvo `docs/POSTAVKA.md`); posle njegovog "gotovo" pokreni `refs`, pokaži mu početnu sliku i tek posle njegovog OK pravi video.
- Glas košta: pre `voice` ili `all` reci Stefanu koliko karaktera ide na ElevenLabs (`check` to ispisuje).

## Šta znamo o Flick-u (reverse engineering, 21. 10. 2026)

Detaljno u `docs/FLICK-REVERSE-ENGINEERING.md`. Najvažnije:

- Convert to 3D je vision model koji "piše" scenu od primitiva (imenovani objekti, ~370 delova za jednu sobu), prvo grubo pa detaljno. To radimo u Blenderu.
- Flick sam hostuje MiniMax H3 kao najjeftiniji model; Seedance 2.5 je skup (48 kredita/s).
- Alati njihovog agenta (scene read, objekat, kamera, keyframe, putanja, snimak) su uzor za naše MCP alate.
