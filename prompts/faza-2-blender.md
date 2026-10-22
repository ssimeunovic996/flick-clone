# Prompt: Faza 2 (3D blokiranje u Blenderu)

```
Pročitaj CLAUDE.md, docs/UPUTSTVO.md (Faza 2), blender/README.md i docs/FLICK-REVERSE-ENGINEERING.md (deo o Convert to 3D).
Alat postoji: blender/stage.py gradi scenu iz .ops.json u Blenderu bez prozora (primer: blender/primeri/kuhinja.ops.json).
Radimo naš Convert to 3D: pogledaj sliku <PUTANJA DO SLIKE LOKACIJE> i napiši projects/<film>/lokacije/<ime>.ops.json u dva prolaza
(prvo grubi blokovi u metrima, pa imenovani objekti od delova) i kameru koja kadrira kao slika.
Posle svakog prolaza renderuj still iz kamere, uporedi sa slikom i popravljaj dok raspored ne odgovara.
Zatim dodaj figure likova u njihovim bojama, kadrove sa pokretima kamere i putanjama, renderuj layout i dubinu za jedan kadar
i testiraj sa LTX-2.5 Union i Layout to Render (workflow ltx-control). Upiši u docs/ODLUKE.md šta radi bolje.
Ažuriraj docs/STATUS.md posle svakog koraka.
```
