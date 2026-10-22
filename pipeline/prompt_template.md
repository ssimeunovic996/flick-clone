# Kako pipeline pravi prompt za video

Obrazac je preuzet od Flick-a (videli smo ga u njihovim kadrovima): kratke rečenice na engleskom, uvek istim redom. Kod je u `pipeline/prompts.py`; prompt svakog pokušaja se čuva u `takes` u `shotlist.json`, pa se lako vidi šta je model dobio.

## Redosled

1. **Style**: `style` iz shotlist-a, isti za ceo film.
2. **Kontrola** (samo kad kadar ima 3D kontrolni video): model prati kameru i raspored iz videa, a obojene figure su likovi.
3. **Likovi**: ime i opis svakog lika u kadru. Uz kontrolni video ide i boja figure, npr. `Mila (the yellow figure in the control video)`.
4. **Location**: `location_description` kadra.
5. **Camera**: veličina kadra, pokret i objektiv, npr. `medium close-up, static camera, 50mm lens`.
6. **Action**: šta se dešava, po sekundama (`0-2 s: ...; 2-5 s: ...`).
7. **Dijalog**: `Mila says: "..."`, a narator kao `Voice-over (no one on screen speaks)`. U `a2v` modu se dodaje rečenica da usne prate zvuk.
8. **Continuity**: pravila iz `continuity` filma i `Faces, hair and clothing stay identical to the references`.

U `ingredients` modu (MiniMax H3) prompt počinje sa `Reference sheet: <likovi> Generated video: ...`, jer model dobija sheet lika kao referencu.

## Vrednosti za kameru

`camera.shot`: extreme_wide, wide, full, medium, medium_close, close, extreme_close, over_shoulder, insert.

`camera.move`: static, dolly_in, dolly_out, dolly_zoom, crane_up, crane_down, pan_left, pan_right, orbit, tracking, handheld, spiral.

Ista imena pokreta koristi i Blender (`blender/camera_moves.py`), pa kadar opisan u shotlist-u može da se napravi i kao 3D kontrolni video.

## Saveti

- Jedan kadar, jedna radnja. Ako se u kadru dešavaju tri stvari, podeli ga.
- Opis lika piši isto u svakom kadru; zato stoji u `characters`, ne u kadru.
- Ne opisuj ono što se ne vidi (misli, prošlost). Model to ne može da prikaže.
- Za kadar od 5 s dovoljna su dva ili tri vremenska dela u `action`.
