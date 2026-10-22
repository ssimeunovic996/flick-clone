# Odluke

Svaka odluka: datum, šta, zašto. Nova odluka koja menja staru ide ispod, a stara se ne briše.

## 2026-10-21

- **Kloniramo način rada Flick-a, ne njegove zatvorene modele.** Flick-ov kvalitet dolazi od Seedance 2.5, koji je zatvoren i skup; aplikacija oko njega se može napraviti.
- **Sve lokalno na Stefanovom računaru** (RTX 5070 Ti 16 GB, 32 GB RAM). Claude Code radi direktno na računaru; bez Remote Control-a i cloud GPU-a.
- **Bez Seedance-a i bez ComfyUI Partner Nodes.** Jedini plaćeni servis je ElevenLabs API, pozvan direktno.
- **Agent je Claude Code na Stefanovoj pretplati**, ne Claude API. Povezan je sa Blenderom (Blender MCP) i ComfyUI-jem (HTTP API).
- **Video: LTX-2.5 kao glavni kandidat, MiniMax H3 kao konkurent.** LTX-2.5 NVFP4 staje u 16 GB uz offloading i ima IC-LoRA kontrolu (Ingredients, Union, Layout to Render). MiniMax H3 je bolji za reference (Stefan ga je testirao, a Flick ga sam hostuje), ali je težak za 16 GB. Konačna odluka posle Faze 0.
- **3D blokiranje prvo u Blenderu, three.js tek opciono.** Blender daje kamere, putanje i mape dubine odmah; sopstveni editor je posao od nedelja.
- **Convert to 3D radimo kao Flick:** model gleda sliku i gradi scenu od imenovanih primitiva, grubo pa detaljno (potvrđeno reverse engineering-om).
- **Film se pravi kadar po kadar, 4 do 5 s**, umesto jednog dugog generisanja sa više kadrova kao u Seedance-u.
- **Predlog nadogradnje:** 64 GB RAM-a, ako offloading bude usko grlo.

## 2026-10-22

- **Kod za Fazu 1 i osnovu Faze 2 napisan unapred, bez Stefanovog računara** (grana `claude/faza-1-pipeline`). Testiran je bez GPU-a (lažni ComfyUI i ElevenLabs, pravi ffmpeg i Blender bez prozora); pravi test na GPU-u ide posle Faze 0.
- **Model kadra je ime workflow-a.** `model: "ltx-a2v"` znači `comfy-workflows/ltx-a2v.api.json` + `ltx-a2v.slots.json`. Slots fajl kaže koja polja pipeline popunjava, kako se pravi prompt i broj frejmova, pa novi model ne traži promenu koda. Razlog: tačni ComfyUI čvorovi zavise od Stefanove instalacije, a ovako se vezuju tek u Fazi 0.
- **Blender se pokreće bez prozora preko `blender/stage.py`, a scena je `.ops.json`.** Claude Code piše operacije, renderuje sliku iz kamere i poredi je sa slikom lokacije. Blender MCP ostaje za ručnu doradu. Razlog: komanda je ponovljiva, radi bez otvorenog Blendera, a isti fajl kasnije čita three.js (Faza 4).
- **`.ops.json` koristi three.js koordinate** (Y gore, metri, stepeni); Blender skripta ih pretvara. Razlog: Faza 4 i Flick-ov format su u three.js.
- **Mapa dubine: bela blizu, crna daleko, raspon meren probnim renderom i fiksan za ceo kadar.** Podrazumevano `inverse` (kao Depth Anything); `linear` je opcija ako LTX Union bolje radi sa njom.
- **Figure likova su za sada lutke od primitiva** (stoji, sedi). Rigovana lutka sa animacijama (Mixamo) ostaje za korak 2.2 ako blokiranje bez nje ne bude dovoljno.
- **Stefan: video ide na MiniMax H3 sa LoRA od 4 koraka** (već instaliran kod njega). To je `minimax-h3` workflow, slika u video; prvi film "Day 412" ga koristi za oba kadra. LTX-2.5 ostaje kao druga opcija (A2V za govor, kontrola iz 3D-a).
- **2026-10-22: `minimax-h3` workflow je napravljen po Stefanovom "H3 MAIN" workflow-u**, jer su to podešavanja koja mu već rade na 16 GB: model `DasiwaMinimaxH3_dasiwaHybridV2_int8_r` (hibrid FL2VA i Ref2VA, pa radi i slika u video), LoRA `minimax_h3_DMAD_4step_full_lora_avg_rank_39_bf16` jačine 1, sampler `er_sde` sa `simple`, 8 koraka (LoRA je za 4; 8 je kao kod Stefana, za kvalitet), `comfy kitchen attention`, bez CFG-a (H3 je destilovan). Početna slika ide kroz `MiniMaxH3ImageToVideo` (`first_frame`), posle `ImageScale` sa sečenjem po centru da se ne razvuče. Izlaz je `VHS_VideoCombine` mp4 sa H3 zvukom. H3 traži 17k+5 frejmova na 24 fps (5 s daje 124), pa pipeline sada zna pravilo `Nk+M`. Odbačeno: zvanični Comfy I2V šablon (traži `fl2va` model, koji Stefan nema) i `SaveVideo` (dinamički format ulazi su nezgodni za API).
- **Stefan: glas preko ai33**, servisa koji daje ElevenLabs preko svog API-ja. Pipeline ima podesivu adresu (`ELEVENLABS_BASE_URL`) i radi i kad servis vrati id posla umesto zvuka (`ELEVENLABS_TASK_URL`). Tačne adrese iz ai33 dokumentacije se upisuju u `.env` na Stefanovom računaru (iz oblaka sajt nije bio dostupan).
