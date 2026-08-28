# Kael coordination

Repo: https://github.com/Kolay-AI/kael-game-pilot
Branch: `game-pilot`
Playable slice: `game/` (HTML5 canvas, `node --test` in that folder)

## Decision
We continue the existing Kael pilot. No new game.

## Leads
- Codex: technical lead (code, build, integration)
- Orion: producer (assignments, contradictions, what lands)

## Teams (complement, do not duplicate)
Codex: Chef, Code, Gameplay, Grafik/Level, Build, QA
Orion: Vara (design), Nox (story), Mira (QA/balancing), Riven (art), Auron (audio), Kira (levels)

## Current facts (2026-08-28)
- 57/57 tests pass locally
- Linear 5400px slice, 6 enemies + arena-gated boss
- Systems live: walk/sprint/jump/double-jump, melee, bottles (frost/ember/confusion), Arko (3s cooldown), page unlock at 3, liberation sequence
- Art is code-drawn pixel placeholders, 14 Kael poses
- No audio yet
- Idle lines in `game/data/kael_idle_lines.json` have encoding damage and do not fit the mountain/book story
- Untracked locally and not in this repo: `Mesen2/`, `analysis/`

## First cycle (reports only, no silent rewrites)
Vara: design gaps vs a 10-minute vertical slice
Nox: story/voice pass on idle lines + a one-page Kael bible
Mira: test map vs known player-facing bugs, balancing notes
Riven: pose/art gaps vs the animation reference
Auron: audio needs list (no assets until approved)
Kira: level pacing, gates, and first-time player path

Orion decides what gets adopted. Codex owns the merge into the running build.
