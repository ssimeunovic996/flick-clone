# Prompt: Faza 1 (pipeline i prvi film)

```
Pročitaj CLAUDE.md, docs/UPUTSTVO.md (Faza 1), docs/ARHITEKTURA.md, docs/ODLUKE.md, docs/STATUS.md i comfy-workflows/README.md.
Pipeline je već napisan u pipeline/ i testiran bez GPU-a. Pokreni python -m pytest da proveriš da radi i na ovom računaru.
Poveži ga sa workflow-ima koje smo izabrali u Fazi 0: za slika, ltx-i2v, ltx-a2v (i minimax-h3 ako ostaje) izvezi API format u comfy-workflows/,
napravi slots fajlove (python -m pipeline.workflows suggest), proveri ih sa inspect i pokreni python -m pipeline.run projects/primer check.
Zatim generiši jedan kadar iz projects/primer, izmeri vreme i VRAM i upiši ih u docs/STATUS.md.
Pa prvi film. Moja ideja: <OVDE NAPIŠI IDEJU U 2-3 REČENICE>.
Napiši scenario i shotlist.json (8 do 12 kadrova od 4 do 5 s) i pokaži mi ih pre generisanja; pre glasa mi reci koliko karaktera ide na ElevenLabs.
Posle generisanja sam pregledaj svaki kadar (pregled.md i frejmovi), ponovi loše i javi mi koje verzije da izaberem.
Ažuriraj docs/STATUS.md posle svakog koraka.
```
