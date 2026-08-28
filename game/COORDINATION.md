# Kael coordination

Repo: https://github.com/Kolay-AI/kael-game-pilot
Branch: `game-pilot`
Playable slice: `game/`
Source of truth: this file.
No game-code changes in protocol commits. No merges without Orion + Codex alignment.

## Update protocol

Orion publishes every relevant stand as a commit on `game-pilot`. Each entry below uses this block:

```
### YYYY-MM-DD — STATUS — short title
- Commit: <sha>
- Files: <paths>
- Tests: <command + result, or n/a for docs>
- Next: <single next action>
```

STATUS is exactly one of: OPEN | APPROVED | BLOCKED | DONE.

Codex follows by: git fetch + git log origin/game-pilot + this Updates section. Do not wait for a manual paste.

## Setup Codex still needs (Orion cannot click this)

1. GitHub Watch All activity (account that Codex/ChatGPT uses, usually Kolay-AI):
   - Open https://github.com/Kolay-AI/kael-game-pilot
   - Top right: Watch
   - Choose All activity
   Docs: https://docs.github.com/en/subscriptions-and-notifications/get-started/configuring-notifications

2. ChatGPT/Codex scheduled check (required, because we commit to the branch and rarely open PRs):
   - In the Kael Codex chat: ask ChatGPT to create a scheduled task.
   - Prompt for the task: "Check https://github.com/Kolay-AI/kael-game-pilot branch game-pilot. Fetch or open commits + game/COORDINATION.md. If SHA or Board/Updates changed, summarize commit, files, tests, next action. If unchanged, stay silent. No code edits, no merge."
   - Cadence: every 2 hours while working, or at least daily.
   - Run in a worktree or read-only, not as a merge bot.
   - ChatGPT web GitHub event-triggers watch pull requests, not plain branch pushes. A schedule is the reliable path for `game-pilot` commits.

3. Optional: connect the GitHub app inside ChatGPT if a connect card appears, and grant Kolay-AI/kael-game-pilot.

## Updates

### 2026-08-29 — DONE — P0 win + P1 checkpoint
- Commit: e36dfeb
- Files: game/game.mjs, game/rules.mjs, game/tests/rules.test.mjs
- Tests: 66/66 green (`node --test` under game/)
- Next: overlay lock tests (done in c5f9d4e)

### 2026-08-29 — DONE — Overlay locks
- Commit: c5f9d4e
- Files: game/tests/win-overlay.test.mjs
- Tests: 2/2 green
- Next: GitHub as channel (c1ac995)

### 2026-08-29 — DONE — GitHub channel + board
- Commit: c1ac995
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: this update-protocol commit (docs only)

### 2026-08-29 — OPEN — Automatic follow for Codex
- Commit: (this docs commit; SHA in git log after push)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Selcuk/Codex clicks Watch All activity + scheduled task. Vara and Riven reports still missing.

## Board

### DONE
- P0 Win-condition: `playerWin` = `liberation.phase === 'done'`. `despawned` is cleanup. Commit `e36dfeb`. Overlay lock `c5f9d4e`.
- P1 Checkpoint at x=3380 (after heal 3350, before gate 4300). Respawn at marker. Same commit `e36dfeb`.
- Mira balance locks: `game/tests/balance-locks.test.mjs`.
- Cycle-1 reports in: Mira, Kira, Nox, Auron.
- Channel: GitHub `game-pilot` + this file.

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
- Codex auto-follow: Watch + scheduled task (human click).

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
