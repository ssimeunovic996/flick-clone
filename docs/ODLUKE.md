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
