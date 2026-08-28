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

## Cycle 1 decisions (Mira QA, 2026-08-28)

Adopted, for Codex after alignment (no silent patch):
- P0 Win-condition: `rules.levelComplete` is liberation `phase==='done'`; `game.mjs` waits for `boss.state==='despawned'`. Player-facing win = phase done, not despawn.
- P1 Checkpoint before arena gate (after heal at x=3350, before gate 4300). Death before the boss must not reset to x=80.

Parked until Vara:
- Boss phases vs less HP/contact
- Resource plant usable over cap / after unlock
- Whether Arko 3s cooldown starts on command or on return

Mira may add regression tests for current numbers (HP/dmg, melee 28, bottle start/cap) but no gameplay edits.

## Cycle 1 decisions (Kira levels, 2026-08-28)

First-run path is ground LTR spawn 80 to gate 4300. Pages 2/3 and Frost mastery are missed. No verb is taught. Dead: 80-530, 3150-4300. Dense: 700-1050 and 2480-3000 (Brute+Farmer-2+Animal-2).

Adopted, no silent layout rewrite:
- P1 Recovery corridor 3150-4300, then checkpoint; refill + look-at before the gate; do not wake the boss on the pit lip at 4130.
- P2 Break pack 2480-3000: Brute solo; Farmer-2 and Animal-2 not in the same activation window.
- P2 Wake farmer-1 only after pit 700-820.
- P3 Next layout cycle: three first-verb rooms before x=1050 (DJ-only gap, bottle dummy, Arko perch). Frost mastery is not first-run prep.
- Small UX: double-jump in the HTML caption; Arko short "no target" when F is a no-op.

Tutorial room order waits on Vara.

## Cycle 1 decisions (Auron audio, 2026-08-28)

Slice has no AudioContext. Adopted 10-min MUST set only. Shared-set (one boot, one impact, one glass) plus pitch variants. No 40-file library. No VO until Nox rewrites idle lines. Music is foothills/meadow, not mountain OST.

MUST: walk/sprint steps, takeoff/land/doublejump, melee whoosh/impact, hurt/death, bottle throw + frost/ember/confusion breaks, Arko call/dive/hit-normal/hit-boss, liberation crack/cloud/sting, boss gate-stinger, explore-loop, mini-boss-loop from gate, silence during liberation, 4-8s win, page/unlock/heal/checkpoint UI.

Parked: skid, void-fall, whiff, status loops, Arko-ready chirp, ambient birds, energy-low.

Assets wait. Next: Auron writes the cue-name hook contract, Codex wires the bus, then first asset wave is Land + Hurt + Walk.

## Cycle 1 decisions (Nox story, 2026-08-28)

Adopted voice: bright SNES adventure, German. Kael is a slightly overwhelmed kid who talks to Arko. Liberation is the reward, not the kill. No doner/lottery/office sarcasm.

Proposal files in repo (not live yet):
- game/reference/KAEL_ONEPAGER.md
- game/data/kael_idle_lines.proposed.json (same ids/animations, new UTF-8 text)

Codex merge must also replace hardcoded IDLE_SPEECH_LINES in game.mjs. JSON swap alone will not change the in-game bubbles.

Parked for story pass 2: thief, mountain name in-game, book origin.

## Cycle 1 decisions (Auron hooks, 2026-08-29)

Hook contract v1 adopted: game/reference/AUDIO_HOOKS.md
Codex analyzes and wires the bus later. No assets yet. ui_checkpoint and boss_gate are event-based so P1 layout can move them.
