# Kael coordination

Repo: https://github.com/Kolay-AI/kael-game-pilot
Branch: `game-pilot`
Playable slice: `game/`
Source of truth: this file.

## Protocol (2026-08-29)

- Orion documents decisions, analysis, and status here, then commits to `game-pilot`.
- Codex reviews new commits, tests, and diffs on `game-pilot`.
- No merge or adoption without Orion + Codex alignment.
- Gameplay changes: Codex implements after Orion approval. Orion may commit docs/tests/spec.
- Status tags: OPEN / APPROVED / BLOCKED / DONE.

Watch the repo on GitHub (Watch -> All activity) to see new commits. Orion also checks `game-pilot` on weekday mornings.

## Board

### DONE
- P0 Win-condition: `playerWin` = `liberation.phase === 'done'`. `despawned` is cleanup. Commit `e36dfeb`. Overlay lock `c5f9d4e`.
- P1 Checkpoint at x=3380 (after heal 3350, before gate 4300). Respawn at marker. Same commit `e36dfeb`.
- Mira balance locks: `game/tests/balance-locks.test.mjs`.
- Cycle-1 reports in: Mira, Kira, Nox, Auron.

### APPROVED (aligned, not started)
- P2 Break pack 2480-3000: Brute solo; Farmer-2 and Animal-2 not same activation window.
- P2 Wake farmer-1 after pit 700-820.
- P2 Do not wake boss on pit lip 4130. Recovery look-at + refill before gate.
- Story voice: adopt `game/reference/KAEL_ONEPAGER.md` + `game/data/kael_idle_lines.proposed.json`. Must also replace hardcoded `IDLE_SPEECH_LINES` in `game.mjs`.
- Audio spec: `game/reference/AUDIO_HOOKS.md` (analyze only, do not wire yet).

### OPEN
- Vara: design gaps vs 10-minute slice (report not in).
- Riven: art/animation gaps (report not in).
- P3 Layout: three first-verb rooms before x=1050.
- Small UX: double-jump caption; Arko "no target" on F no-op.
- Story pass 2: thief, in-game mountain name, book origin.

### BLOCKED
- Audio bus + first assets (land/hurt/walk): waiting on Codex hook wiring after analysis.
- VO: waiting on live idle-line swap.
- Boss phases vs less HP; resource plant over cap; Arko 3s from command vs return: waiting on Vara.
- Tutorial room order: waiting on Vara.

## Leads
- Codex: technical lead (code, build, integration)
- Orion: producer (assignments, contradictions, what lands)

## Teams
Codex: Chef, Code, Gameplay, Grafik/Level, Build, QA
Orion: Vara (design), Nox (story), Mira (QA/balancing), Riven (art), Auron (audio), Kira (levels)

## Facts
- Tests: 66 + overlay locks on `game-pilot`
- Linear 5400px slice, 6 enemies + arena-gated boss
- Live systems: walk/sprint/jump/double-jump, melee, bottles, Arko, page unlock, liberation
- Art is code-drawn placeholders
- No audio bus yet
- Not in repo: `Mesen2/`, `analysis/`

## Cycle-1 notes
See git history of this file for the long-form Mira/Kira/Nox/Auron notes. The board above is current.
