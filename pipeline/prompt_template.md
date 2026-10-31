# Kako pipeline pravi prompt za video

## Prvo: prompt piše Claude, za svaki kadar

Šablon ispod daje spisak etiketa (`Style: … Location: … Continuity: …`). Test "Radio" (31. 10. 2026) je pokazao da MiniMax H3 sa takvim promptom izgleda kruto, a da isti trenutak priče sa promptom napisanim za taj kadar izgleda kao pravi film (`projects/_testovi/radio-b/` na Stefanovom računaru). Zato Claude za svaki kadar upisuje dva polja u `shotlist.json`, a šablon ostaje samo rezerva:

| Polje | Za šta | Kako se koristi |
|---|---|---|
| `image_prompt` | početna slika (Qwen) | doslovno; kad kadar ima sheet lika, pipeline sam doda rečenicu da lik bude isti kao na sheet-u. Kod kadra iz 3D-a zamenjuje opis scene posle uputstva za layout |
| `video_prompt` | video (H3) | doslovno, u svakom modu |

### `image_prompt` (slika)

- Ko je u kadru i šta radi u prvom trenutku, u kojoj pozi i gde gleda.
- Scena puna života: pet do osam konkretnih predmeta, materijali, doba, pohabanost (pločice, ormarići, čajnik na šporetu, kalendar). Prazna soba izgleda kao maketa.
- Svetlo: koji izvori, koje boje i gde padaju senke (topla lampa na licu, hladno plavo sa prozora, tamni uglovi).
- Kamera: veličina kadra, visina (u visini očiju), objektiv u mm, dubinska oštrina.
- Stil na kraju: film still, grain, no text.
- Predmet koji se ponavlja u više kadrova (lampa, radio) opiši istim rečima u svakom kadru.

### `video_prompt` (H3)

- Jedan pasus, 40 do 90 reči, na engleskom, u sadašnjem vremenu.
- Ne opisuj ponovo ono što se već vidi na početnoj slici (odeća, soba). Opiši šta se menja: pokret kamere, pokret ljudi, svetlo, zvuk.
- Kamera: jedan pokret i dokle ide ("slow push-in to a medium close-up"), da bitni predmeti ostanu u kadru.
- Radnja redom kako se dešava, pa jasan kraj kadra ("…and ends looking up at the lamp"). U testu je H3 preskočio poslednji pokret koji nije bio naglašen.
- Zvuk: kiša, šum radija, koraci. H3 pravi svoj zvuk, a montaža mu ujednači glasnoću.
- Replika: `She says quietly: "..."`, ako H3 govori sam; glas iz ElevenLabs-a ide preko `audio`.
- H3 dobija samo početnu sliku. Krajnju sliku (`end_moment` ili 3D `end`) dodaj samo kad kadar mora da završi baš tako, jer ga vezuje sa oba kraja i pokret postane ukočen.

Primer iz testa (početna slika, pa video):

> A cramped, lived-in old Balkan apartment kitchen at night. The woman, in her early 30s with a short black bob and round glasses, wearing a mustard yellow knitted sweater, sits at a small worn wooden kitchen table, leaning forward on her elbows, looking at an old wooden tube radio in front of her. Behind her: green and white tiled backsplash, cream painted wall cabinets, a dented kettle on an old gas stove, a dish rack, a paper calendar on the wall, and a window with rain running down the glass and blurred city lights outside. The only light is a small table lamp with a cream fabric shade, warm tungsten glow on her face and hands, deep shadows in the corners, faint cold blue light from the window. Medium shot at eye level, 35mm lens, shallow depth of field, fine film grain, a still from a European drama film, no text.

> Rain streams down the kitchen window as the camera slowly pushes in toward the woman at the table. She reaches out and gently turns the dial of the old radio; static crackles and a faint, distant melody fades in. The table lamp flickers twice, its warm light stuttering across her face. She freezes with her hand still on the dial and slowly lifts her eyes toward the lamp, uneasy. Soft rain patter, radio static, the quiet hum of the lamp. Natural, realistic motion, cinematic, film grain.

## Šablon (rezerva kad kadar nema svoje promptove)

Obrazac je preuzet od Flick-a (videli smo ga u njihovim kadrovima): kratke rečenice na engleskom, uvek istim redom. Kod je u `pipeline/prompts.py`; prompt svakog pokušaja se čuva u `takes` u `shotlist.json`, pa se lako vidi šta je model dobio.

### Redosled

1. **Style**: `style` iz shotlist-a, isti za ceo film.
2. **Kontrola** (samo kad kadar ima 3D kontrolni video): model prati kameru i raspored iz videa, a obojene figure su likovi.
3. **Likovi**: ime i opis svakog lika u kadru. Uz kontrolni video ide i boja figure, npr. `Mila (the yellow figure in the control video)`.
4. **Location**: `location_description` kadra.
5. **Camera**: veličina kadra, pokret i objektiv, npr. `medium close-up, static camera, 50mm lens`.
6. **Action**: šta se dešava, po sekundama (`0-2 s: ...; 2-5 s: ...`).
7. **Dijalog**: `Mila says: "..."`, a narator kao `Voice-over (no one on screen speaks)`. U `a2v` modu se dodaje rečenica da usne prate zvuk.
8. **Continuity**: pravila iz `continuity` filma i `Faces, hair and clothing stay identical to the references`.

U `ingredients` modu (MiniMax H3) prompt počinje sa `Reference sheet: <likovi> Generated video: ...`, jer model dobija sheet lika kao referencu.

### Vrednosti za kameru

`camera.shot`: extreme_wide, wide, full, medium, medium_close, close, extreme_close, over_shoulder, insert.

`camera.move`: static, dolly_in, dolly_out, dolly_zoom, crane_up, crane_down, pan_left, pan_right, orbit, tracking, handheld, spiral, rack_focus.

Ista imena pokreta (osim `rack_focus`, koji je samo promena fokusa) koristi i Blender (`blender/camera_moves.py`), pa kadar opisan u shotlist-u može da se napravi i kao 3D kontrolni video.

### Saveti

- Jedan kadar, jedna radnja. Ako se u kadru dešavaju tri stvari, podeli ga.
- Opis lika piši isto u svakom kadru; zato stoji u `characters`, ne u kadru.
- Ne opisuj ono što se ne vidi (misli, prošlost). Model to ne može da prikaže.
- Za kadar od 5 s dovoljna su dva ili tri vremenska dela u `action`.
