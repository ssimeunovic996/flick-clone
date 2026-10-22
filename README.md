# Flick klon

Lični alat za kratke AI filmove za YouTube, po uzoru na Flick (flick.art). Sve radi lokalno: Claude Code (agent), ComfyUI (LTX-2.5 / MiniMax H3), Blender (3D blokiranje), ElevenLabs (glas) i ffmpeg (montaža).

## Odakle da počneš

1. `docs/UPUTSTVO.md`: plan korak po korak, faze 0 do 4.
2. `docs/STATUS.md`: dokle se stiglo.
3. `prompts/`: gotov prompt za Claude Code za svaku fazu. Otvori Claude Code u ovom folderu i nalepi prompt faze na kojoj si.

## Sadržaj

| Fajl | Šta je |
|---|---|
| `CLAUDE.md` | Kontekst koji Claude Code čita na početku svake sesije |
| `docs/UPUTSTVO.md` | Uputstvo korak po korak |
| `docs/STATUS.md` | Napredak, vremena, merenja |
| `docs/ODLUKE.md` | Odluke i razlozi |
| `docs/ARHITEKTURA.md` | Tok rada, folderi, format liste kadrova, alati agenta |
| `docs/FLICK-REVERSE-ENGINEERING.md` | Kako Flick zaista radi |
| `prompts/` | Promptovi po fazama |
| `pipeline/` | Faza 1: od `shotlist.json` do montiranog filma (`python -m pipeline.run`) |
| `comfy-workflows/` | ComfyUI workflow-i i njihovi slots fajlovi |
| `blender/` | Faza 2: 3D scena iz `.ops.json`, pokreti kamere, layout i dubina |
| `projects/primer/` | Mali probni film za proveru pipeline-a |
| `tests/` | `python -m pytest`, bez GPU-a |

Pun izveštaj sa analizom: https://claude.ai/artifact/U3nMybyEG5oVuhh7JwdrDY
