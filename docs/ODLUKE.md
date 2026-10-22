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
