# Prompt: Faza 1 (pipeline i prvi film)

```
Pročitaj CLAUDE.md, docs/UPUTSTVO.md (Faza 1), docs/ARHITEKTURA.md, docs/ODLUKE.md, docs/STATUS.md i comfy-workflows/README.md.
Pipeline je već napisan u pipeline/ i testiran bez GPU-a. Pokreni python -m pytest da proveriš da radi i na ovom računaru.
Poveži ga sa mojim workflow-ima: za slika i minimax-h3 (MiniMax H3 sa LoRA od 4 koraka, već instaliran), kasnije ltx-i2v i ltx-a2v, izvezi API format u comfy-workflows/,
napravi slots fajlove (python -m pipeline.workflows suggest), proveri ih sa inspect i pokreni python -m pipeline.run projects/primer check.
U .env upiši adresu ai33 API-ja za glas (pogledaj njihovu API dokumentaciju; vidi .env.example).
Zatim napravi film projects/dan-412 (10 s, scenario je gotov), izmeri vreme i VRAM po kadru i upiši ih u docs/STATUS.md.
Pa prvi film. Moja ideja: <OVDE NAPIŠI IDEJU U 2-3 REČENICE>.
Napiši scenario i shotlist.json (8 do 12 kadrova od 4 do 5 s) i pokaži mi ih pre generisanja; pre glasa mi reci koliko karaktera ide na ElevenLabs.
Posle generisanja sam pregledaj svaki kadar (pregled.md i frejmovi), ponovi loše i javi mi koje verzije da izaberem.
Ažuriraj docs/STATUS.md posle svakog koraka.
```
