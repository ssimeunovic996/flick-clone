# Postavka: ti postavljaš likove i kameru

Za kadar u kome je bitno gde ko stoji i odakle gleda kamera, scenu postavljaš ti u Blenderu. Ja iz tvoje postavke napravim sliku iz kamere, Qwen od nje napravi pravu fotografiju sa likovima tačno tamo gde si ih stavio, a H3 od nje napravi video.

## Kako ide

1. Ja napravim postavku za kadar: `python -m pipeline.run projects/<film> postavka --shots s03`. Dobiješ `projects/<film>/lokacije/s03_postavka.blend`: sobu od jednostavnih oblika, lutke za likove (žuta je Mila, plava deda) i kameru tog kadra.
2. Ti je otvoriš u Blenderu, namestiš i sačuvaš (Ctrl+S). Napišeš mi "gotovo" i, ako hoćeš, šta treba da se desi u kadru.
3. Ja pokrenem `refs`. Slika iz tvoje kamere stiže za oko 2 s, a prava početna slika za još oko 10 s. Pošaljem ti je na odobrenje.
4. Posle tvog OK: proba videa (oko 35 s), pa pun kadar (oko 2 min).

Kad postavku ponovo sačuvaš, sledeći `refs` sam vidi da je novija i pravi sliku iznova.

## Tasteri koji su dovoljni

Bez numeričke tastature: Edit > Preferences > Input, uključi Emulate Numpad; tada brojevi u gornjem redu rade kao numerički (0 je kamera). Na laptopu bez srednjeg tastera uključi i Emulate 3 Button Mouse (Alt + levi klik okreće pogled), ili vuci kuglicu sa osama gore desno u prozoru.

| Šta | Kako |
|---|---|
| Pogled kroz kameru | 0 na numeričkoj tastaturi (bez nje: meni View > Cameras > Active Camera) |
| Okretanje pogleda | srednji taster miša; Shift + srednji pomera, točkić zumira |
| Izbor lika | klik na krug kod nogu lutke ili na ime (`mila`, `deda`) u spisku gore desno |
| Pomeranje | G pa miš; G pa Shift+Z pomera samo po podu; klik levim tasterom potvrdi, desnim odustane |
| Okretanje lika | R pa Z, pa miš ili upiši ugao (npr. R Z 90 Enter) |
| Kamera tamo gde gledaš | namesti pogled mišem, pa Ctrl+Alt+0 (meni View > Align View > Align Active Camera to View) |
| Kamera "iz ruke" | u pogledu kroz kameru: N, kartica View, uključi Lock Camera to View; sad okretanje i zum pomeraju kameru |
| Objektiv | desno Properties, zelena ikonica kamere, Lens > Focal Length (24 širok, 35, 50, 85 uzak) |
| Vrati korak | Ctrl+Z |
| Sačuvaj | Ctrl+S |

Nameštaj možeš da pomeraš i brišeš (X). Ako dodaš nešto novo (Shift+D duplira), napiši mi šta je to, jer ja vidim samo blok.

## Kraj kadra (nije obavezno)

Ako kadar mora da završi baš određeno (kamera stigne na tačno mesto, deda stane kod stola):

1. Prvo završi i sačuvaj početak (Ctrl+S).
2. File > Save As, ime `s03_kraj.blend`, u istom folderu.
3. Pomeri šta treba za kraj i sačuvaj (Ctrl+S).

H3 onda dobija i početnu i krajnju sliku, pa mora da stigne tamo. Pokret je tačniji, ali malo ukočeniji. Bez krajnje postavke H3 pokret pravi sam, po opisu koji mi napišeš.

## Šta ide u prompt

Iz postavke ja računam za svaki lik da li je okrenut ka kameri, leđima ili profilom, da li je levo, u sredini ili desno i ko je u prvom planu. To ide u prompt za Qwen, zajedno sa opisom prave scene, pa likovi ne mogu da završe na pogrešnom mestu.
