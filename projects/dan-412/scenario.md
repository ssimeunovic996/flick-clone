# Day 412 (Dan 412)

Kratki film od 10 sekundi, uspravan (9:16) za YouTube Shorts. Prvi pravi film kroz pipeline: dva kadra, jedan lik, glas preko radija.

## Ideja

Astronautkinja na Marsu posadi prvu biljku i to javi bazi. Kamera izoštri pozadinu: nekoliko metara dalje već raste veliki crveni cvet, a pored njega stoji stara zarđala kantica za zalivanje. Neko je već bio ovde.

## Kadrovi

| Kadar | Trajanje | Šta vidimo | Glas (radio, astronautkinja) |
|---|---|---|---|
| s01 | 5 s | Širok kadar, crvena pustinja u svitanje. Astronautkinja kleči i posadi malu zelenu klicu. Kamera polako prilazi. | "Day four hundred twelve. First plant on Mars." |
| s02 | 5 s | Makro kadar klice i rukavice. Fokus prelazi u pozadinu: visok crveni cvet i zarđala kantica. Ruka se ukoči. | "...Or not." (šapatom, u 3.6 s) |

## Zašto ovako

- **Lice se ne vidi** (zlatni vizir), pa nema problema sa doslednošću lica između kadrova.
- **Video je MiniMax H3 sa LoRA od 4 koraka**, slika u video (workflow `minimax-h3`), za oba kadra.
- **Glas ide preko radija**, kao narator, pa ne treba sinhronizacija usana.
- **Obrt je u fokusu, ne u pokretu kamere**: cvet je od početka u kadru, samo zamućen, pa model ne mora da izmišlja novi sadržaj usred kadra.
- Replike su na engleskom zbog YouTube publike; za srpsku verziju se menjaju samo dve linije teksta.

## Šta treba pre pokretanja

1. Izaberi miran ženski ElevenLabs glas (preko ai33) i upiši njegov ID umesto `ELEVENLABS_VOICE_ID_ASTRONAUTKINJE`. Ukupno je 55 karaktera teksta.
2. U `.env` ai33 ključ i adresa njihovog API-ja (`ELEVENLABS_BASE_URL`, po potrebi `ELEVENLABS_TASK_URL`; vidi `.env.example`).
3. Workflow `minimax-h3` je gotov (napravljen po tvom "H3 MAIN"). Fali još `slika` za početne slike kadrova (uputstvo u `comfy-workflows/README.md`).
4. Zatim:
   ```
   python -m pipeline.run projects/dan-412 check
   python -m pipeline.run projects/dan-412 all
   python -m pipeline.run projects/dan-412 approve s01
   python -m pipeline.run projects/dan-412 approve s02
   python -m pipeline.run projects/dan-412 assemble
   ```

Opciono: tiha ambijentalna muzika u `audio/muzika.mp3` i polje `music` u `shotlist.json` (primer u `projects/primer`).
