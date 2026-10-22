# Flick: kako zaista radi (reverse engineering, 21. 10. 2026)

Urađeno u Stefanovom Chrome-u, na njegovom nalogu: čitanje njihovog JavaScript koda (glavni fajl 12,5 MB) i praćenje mrežnih poziva. Na Stefanovoj slici spavaće sobe pokrenut je Convert to 3D. Sve je posmatrano direktno, osim gde piše "pretpostavka". Pun izveštaj: https://claude.ai/artifact/U3nMybyEG5oVuhh7JwdrDY

## Tehnologija

- **Frontend:** React aplikacija (Vite build), prvobitno napravljena u Lovable-u. 3D je three.js (WebGL). Snimak kadra pravi se u pregledaču (Mediabunny, WebCodecs) kao MP4.
- **Backend:** Supabase na `auth.flick.art`: prijava, Postgres tabele (`projects`, `stage_scenes`, `chat_sessions`, `chat_turns`, `user_media`, ...), Edge funkcije za plaćanje, upload i kredite.
- **Teški servisi:** Python FastAPI na Modal-u (serverless GPU): `chat-websocket` (agent) i `image-to-stage` (Convert to 3D).
- **Ostalo:** Liveblocks (zajednički canvas), PostHog (analitika, snimanje sesija), Stripe, Rewardful, Cloudflare Turnstile.

## Modeli i cene (krediti)

Osnovna cena je za podrazumevano trajanje; kod Seedance-a i MiniMax-a to je 5 s.

| Model | Cena | Napomena |
|---|---|---|
| Seedance 2.5 (reference) | 240 | 48/s, 4 do 30 s |
| Seedance 2.5 Draft | 105 | |
| MiniMax H3 preko API-ja | 95 | 5 do 15 s |
| MiniMax H3 Max / Fast, self-host | 20 | i na besplatnom planu; Flick sam hostuje otvorene težine |
| Veo 3.1 | 160 | |
| Kling 3.0 Pro / O3 | 112 | |
| Gemini Omni Flash | 100 | |
| Wan 3.0 | 60 | |
| Kling Avatar v2 (lip-sync) | 11/s | |
| Auto | 7 | |

Ostalo: Change Angle = Qwen Camera Control (10 po uglu); referenca lika = Nano Banana Pro i 2; dijalog i muzika = ElevenLabs; zvučni efekti iz videa = Mirelo SFX 2.0. Ukupno 21 operacija (slika, video, zvuk).

## Convert to 3D ("To 3D Stage")

- Besplatan.
- Jedan zahtev `POST https://flick--image-to-stage-fastapi-app.modal.run/api/image-to-stage` sa: `image_url`, `prop_index` (katalog životinja, vozila i oružja sa dimenzijama) i `pose_clips` (15 animacija).
- Odgovor je tok JSON linija: `{type:"ops", add, remove, rough}` (prvo grubi sivi blokovi, pa detalji), na kraju `{type:"done", reading}`. Traka napretka je procena po vremenu.
- Test: slika spavaće sobe → za oko 3 min scena "Blue Fireplace Bedroom", 24 imenovana objekta ("Double bed with white bedding and blue runner", "Eight-arm chandelier with small lampshades"...) od oko 370 primitiva sa pozicijom, rotacijom, veličinom i bojom; kamera 24 mm, 16:9.
- Zaključak: nije generator 3D mreže. Model gleda sliku i piše scenu od primitiva. Pretpostavka: vision LLM na serveru (koji, ne vidi se iz pregledača).

## 3D Stage i agent

- Ljudi: jedna lutka `humanoid.glb` sa 15 animacija (walk, walk_formal, idle, idle_talking, sitting_idle, sitting_talking, dance, jump, crouch...).
- Rekviziti: 1.428 GLB modela na `cdn.flick.art/stage-props/` (priroda, srednji vek, nameštaj, zgrade, tamnica, pirati, oružje, vozila...).
- Pokreti kamere: orbit, dolly in/out, dolly zoom, crane up/down, pan sweep, spiral, sopstvena putanja; formati 16:9, 9:16, 1:1, 4:3, 1.85:1, 2.39:1.
- Agent: WebSocket ka Modal servisu; server odlučuje, a alate izvršava pregledač (lista u `ARHITEKTURA.md`). Poruka agentu nosi kontekst: mediji, tekstovi, stanje scene, klipovi, priča, podešavanja projekta. Koji LLM radi u pozadini ne vidi se.
- Record snima take u pregledaču kao MP4; to postaje video čvor na canvasu i referenca za video model.

## Šta to znači za nas

- Convert to 3D radimo isto: Claude Code + Blender MCP, scena od primitiva.
- MiniMax H3 je dovoljno dobar za produkciju (Flick ga koristi); naše ograničenje je 16 GB VRAM-a.
- Lista Flick-ovih alata je uzor za naše MCP alate.
- Lutku i rekvizite uzimamo iz besplatnih paketa.
