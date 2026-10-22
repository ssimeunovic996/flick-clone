# Uputstvo korak po korak: lični Flick

Ovo je plan izgradnje od nule do aplikacije. Svaki korak ima tri dela: šta radiš ti, šta radi Claude Code i kada je korak gotov. Vremena su procene za rad direktno na tvom računaru. Najveći deo vremena odlazi na generisanje na GPU-u, ne na pisanje koda.

Pravilo: jedna faza je jedna sesija (ili jedan thread). Na početku sesije Claude Code čita `CLAUDE.md` i `docs/STATUS.md`. Gotov prompt za svaku fazu je u folderu `prompts/`.

| Faza | Šta dobijaš | Vreme |
|---|---|---|
| 0 | Instaliran alat, 4 test klipa, izabran glavni video model | pola dana |
| 1 | Pipeline: scenario → kadrovi → glas → video → montaža; prvi film | oko 1 dan |
| 2 | 3D blokiranje u Blenderu (naš Convert to 3D i 3D Stage) | 2 do 3 dana |
| 3 | Web aplikacija: Story, Canvas, Stage, Editor | 3 do 5 dana |
| 4 | Sopstveni 3D Stage u pregledaču (three.js), opciono | 1 do 2 nedelje |

---

## Faza 0: Priprema i testovi (pola dana)

### 0.1 Osnovni programi

**Ti**, u PowerShell-u (preskoči ono što već imaš):

```powershell
winget install Git.Git
winget install Python.Python.3.12
winget install astral-sh.uv
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
winget install BlenderFoundation.Blender
```

Instaliraj i najnoviji NVIDIA drajver (RTX 50 serija traži novije CUDA verzije u ComfyUI-ju).

**Gotovo kad:** `git --version`, `python --version`, `uv --version`, `node --version`, `ffmpeg -version` i Blender rade.

### 0.2 Claude Code u ovom folderu

**Ti:**

```powershell
irm https://claude.ai/install.ps1 | iex
cd "D:\Flick klon"
claude
```

U Claude Code-u prijavi se svojim Claude nalogom (`/login`), da troši pretplatu, a ne API kredite.

**Claude Code:** pravi `git init`, `.gitignore` (modeli, `projects/*/kadrovi`, `.env`), `.env.example` i strukturu foldera iz `docs/ARHITEKTURA.md`.

**Gotovo kad:** prvi git commit postoji.

### 0.3 ComfyUI i modeli

Već koristiš ComfyUI sa LTX-2.5 i MiniMax H3. Ažuriraj ComfyUI i ComfyUI-LTXVideo čvorove, pa proveri da imaš:

- LTX-2.5 22B distilled u **NVFP4** (najbolje za 16 GB) i Gemma tekst enkoder (INT8 verzija štedi memoriju)
- IC-LoRA **Ingredients** (`ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors`) za konzistentnost lika
- IC-LoRA **Union** (dubina, poza, ivice) i **Layout to Render** za kontrolu iz 3D-a
- Primer workflow-e iz ComfyUI-LTXVideo: I2V, A2V (zvuk u video), `LTX-2.5_ICLoRA_Ingredients_Single_Stage_Distilled.json`
- Tvoj postojeći MiniMax H3 workflow

Napomena: sa 32 GB RAM-a offloading je na granici. Ako ComfyUI puca ili mnogo swap-uje, zatvori druge programe; 64 GB RAM-a je najisplativija nadogradnja.

**Claude Code:** kopira workflow-e koje koristimo u `comfy-workflows/` i za svaki zapisuje šta radi i koje ulaze ima.

### 0.4 MCP veze i ključevi

**Ti** (Claude Code ti pokazuje tačne korake):

```powershell
claude mcp add blender -- uvx mcp-for-blender
```

U Blenderu instaliraj dodatak Blender MCP-a i u bočnom panelu (taster N) klikni Connect. Za ComfyUI Claude Code koristi direktno njegov HTTP API (`http://127.0.0.1:8188`), što je pouzdanije od MCP servera. `comfyui-mcp` je opcija ako zatreba.

Upiši `ELEVENLABS_API_KEY=...` u `.env`.

**Gotovo kad:** Claude Code napravi kocku u Blenderu preko MCP-a i pošalje jedan workflow ComfyUI-ju.

### 0.5 Četiri testa na GPU-u

**Claude Code** pokreće testove, a **ti** ocenjuješ izgled. Rezultati idu u `projects/_testovi/`, a beleške u `docs/STATUS.md`.

1. **Brzina:** LTX-2.5 I2V, 5 s, osnovna rezolucija. Beleži vreme i VRAM.
2. **Konzistentnost lika:** isti lik u 3 različita kadra, LTX-2.5 Ingredients (reference sheet) naspram MiniMax H3 sa referencom.
3. **Govor:** jedna rečenica iz ElevenLabs-a, pa LTX-2.5 A2V (usne prate glas).
4. **3D kontrola:** Claude Code u Blenderu napravi sobu od blokova i kameru koja se kreće, renderuje mapu dubine, a LTX-2.5 Union prati tu kameru.

**Gotovo kad:** u `docs/ODLUKE.md` piše koji model koristimo za koji tip kadra (npr. H3 za likove, LTX za kontrolu kamere i govor).

---

## Faza 1: Pipeline bez interfejsa (oko 1 dan)

Cilj: ceo film iz komandne linije, a Claude Code je režiser.

### 1.1 Struktura filma

**Claude Code** pravi `projects/<ime-filma>/` sa folderima `likovi/`, `lokacije/`, `audio/`, `kadrovi/`, `final/` i fajlovima `scenario.md` i `shotlist.json` (format u `docs/ARHITEKTURA.md`).

### 1.2 Skripte

**Claude Code** piše u `pipeline/`:

- `comfy_client.py`: šalje workflow na ComfyUI API, čeka rezultat, preuzima izlaz
- `gen_refs.py`: reference likova (reference sheet) i lokacija preko tvog lokalnog modela za slike
- `gen_voice.py`: ElevenLabs dijalog po kadru u `audio/`
- `gen_video.py`: za svaki kadar bira workflow (I2V, A2V, Ingredients, Union) po `shotlist.json`
- `assemble.py`: ffmpeg montaža, prelazi, muzika, titlovi
- `run.py`: pokreće sve redom, preskače gotove kadrove i upisuje status u `shotlist.json`

### 1.3 Šablon prompta

Po Flick obrascu: stil, uloga svake reference, boja figure → lik, šta se dešava po sekundama, pravila kontinuiteta, ko govori. Šablon ide u `pipeline/prompt_template.md`.

### 1.4 Prvi film

**Ti** daješ ideju u par rečenica. **Claude Code** piše scenario i listu od 8 do 12 kadrova, generiše, sam pregleda kadrove (izvlači frejmove), ponavlja loše i montira. **Ti** biraš između verzija i odobravaš glasove.

**Gotovo kad:** `projects/<film>/final/film.mp4` od 30 do 60 s postoji, a Claude Code ga može ponoviti jednom komandom.

---

## Faza 2: 3D blokiranje u Blenderu (2 do 3 dana)

Ovo je naša verzija Flick-ovog Convert to 3D i 3D Stage-a. Reverse engineering je pokazao da je i kod njih to model koji gradi scenu od primitiva, pa je pristup isti.

### 2.1 Slika → 3D scena

**Claude Code** gleda sliku lokacije i preko Blender MCP-a gradi scenu u dva prolaza:

1. Grubo: pod, zidovi, otvori, veliki nameštaj, u metrima.
2. Detaljno: imenovani objekti složeni od delova (npr. "krevet" = okvir, dušek, jastuci), boje, i kamera koja kadrira kao originalna slika.

Sve komande se beleže u `lokacije/<ime>.ops.json`, da scena može ponovo da se sastavi. Sačuvaj i `.blend`.

**Gotovo kad:** render iz kamere scene liči na originalnu sliku po rasporedu.

### 2.2 Likovi kao figure

Rigovana lutka sa osnovnim animacijama (hod, stajanje, sedenje, govor), iz besplatnog paketa ili Mixamo-a. Svaki lik ima svoju boju, kao u Flick-u (plavi = lik A, ljubičasti = lik B). Claude Code ih postavlja i daje im putanje.

### 2.3 Kamere i pokreti

**Claude Code** pravi `blender/camera_moves.py`: orbit, dolly in/out, dolly zoom, crane up/down, pan, spirala i putanja po tačkama, sa žižnom daljinom i formatom slike (16:9, 9:16, 2.39:1).

### 2.4 Render za kontrolu

Za svaki kadar: playblast (brz render) i mapa dubine, u rezoluciji i broju frejmova koje LTX-2.5 očekuje.

### 2.5 Video iz 3D-a

Testira se šta daje najbolji rezultat:

- mapa dubine → LTX-2.5 Union
- playblast → Layout to Render
- uz Ingredients reference za izgled likova

**Gotovo kad:** jedan kadar sa pokretom kamere i dva lika prati blokiranje iz Blendera, a izgled likova odgovara referencama.

### 2.6 MCP alati po uzoru na Flick

Kad osnova radi, Claude Code ih pakuje u alate: `scene_read`, `add_object`, `set_camera`, `camera_move`, `add_keyframe`, `add_path`, `render_take`. Tako svaki kadar pravi kratkom rečenicom ("kamera kreće iza Marka i polako mu prilazi").

---

## Faza 3: Web aplikacija, lični Flick (3 do 5 dana)

Radi se tek kad Faze 1 i 2 rade, jer aplikacija samo pakuje isti pipeline.

- **Frontend:** Vite, React i TypeScript. Canvas sa čvorovima (React Flow) za slike, video i zvuk, sa @referencama kao u Flick-u.
- **Backend:** Python FastAPI na tvom računaru; most ka ComfyUI-ju, ElevenLabs-u, Blenderu i ffmpeg-u. Baza je SQLite (jedan korisnik, bez Supabase-a i Liveblocks-a).
- **Stranice:** Story (scenario i lista kadrova), Canvas, Stage (pregled Blender scene i takeova), Video Editor (timeline i export).
- **Agent:** ostaje Claude Code na tvojoj pretplati. Aplikacija mu izlaže MCP alate (iste kao u 2.6, plus canvas i timeline), a za chat unutar aplikacije može lokalno da poziva `claude -p`.

**Gotovo kad:** ceo kratki film napraviš kroz aplikaciju, bez komandne linije.

---

## Faza 4: Sopstveni 3D Stage u pregledaču (opciono, 1 do 2 nedelje)

Samo ako ti Blender bude spor za blokiranje. three.js scena kao Flick-ova: primitivi, lutka sa animacijama, GLB rekviziti, pomeranje (W/E/R), timeline sa keyframe-ovima, pokreti kamere i snimanje u MP4 u pregledaču (WebCodecs). Agent koristi iste alate kao za Blender.

---

## Posle svake faze

1. Claude Code ažurira `docs/STATUS.md` i `docs/ODLUKE.md`.
2. Git commit.
3. Ako se plan menja, menja se i ovo uputstvo.
