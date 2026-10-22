# Radio (3D test)

Test 3D blokiranja sa MiniMax H3, bez LTX-a: 15 s, 16:9, tri kadra u istoj kuhinji, dva lika kojima se vidi lice. Priča je iz `projects/primer`: svake noći lampa trepne, Mila čuje radio, a deda kaže da se to javlja baka.

## Kako je napravljeno

1. Kuhinja, figure i kamere su u `lokacije/kuhinja.ops.json` (scena iz `blender/primeri`, sa jačim pokretima kamere).
2. `refs` renderuje u Blenderu sliku iz kamere na početku i na kraju svakog kadra (`kadrovi/layout/`).
3. Qwen od layout slike i sheet-a lika pravi pravu početnu sliku (Layout to Render). Krajnju sliku pravi od layout slike na kraju kadra i početne slike, da ljudi i svetlo ostanu isti.
4. MiniMax H3 pravi video između početne i krajnje slike (`first_frame` + `last_frame`), pa pokret kamere prati 3D.

| Kadar | Kamera iz 3D-a | Šta se dešava |
|---|---|---|
| s01 | širok, orbit 35° oko Mile | Mila sedi za stolom, kiša, lampa trepne |
| s02 | srednji krupni, dolly in 0,35 m | Mila okreće radio i podigne pogled; "Deda, opet je počelo." |
| s03 | preko ramena, deda ulazi, dolly in 0,4 m | Deda se pojavi na vratima; "Znam. To nam se javlja tvoja baka." |

Glas nije pušten (troši ai33 kredite); H3 pravi svoj zvuk, pa test pokazuje i kako H3 sam izgovara replike.
