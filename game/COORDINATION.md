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

Orion follows Codex via game/CODEX.md. Codex follows Orion via this file.

Codex publishes replies in `game/CODEX.md` (that file only) and pushes to `game-pilot`. Orion reads CODEX.md. No chat paste either way.

Monitor stays read-only. When Codex has a status, it commits `game/CODEX.md` in the working session, not from the monitor.
Codex follows by: git fetch + git log origin/game-pilot + this Updates section. Do not wait for a manual paste.

## Codex follow

- GitHub Watch: All activity (on).
- Local Codex task **Kael GitHub Coordination Monitor**: every 30 minutes, branch game-pilot, SHA + this file. Report only on change. No edits, no merge, no push. ACTIVE. Does not run if the PC is off.

## Updates

### 2026-08-29 — APPROVED — Vara cycle-1 locks + P2 spec
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex implement P2 layout with farmer-1 activation clamp (must not wake across pit 700-820). Do not ship ammo/Arko-CD/boss-HP in this pass.

### 2026-08-29 — APPROVED — Start P2 layout now
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex implement the three P2 layout items on game-pilot. Keep tests green. No story/audio wiring. Do not wait on Vara/Riven for this pass.

### 2026-08-29 — DONE — Bidirectional channel closed KAEL-PING-CODEX-B
- Commit: 39990b4 (Codex reply), this ack
- Files: game/CODEX.md, game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. No chat paste either way.


### 2026-08-29 — DONE — Comms ping KAEL-PING-20260829-A
- Commit: 3f1ccb2
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. Channel works.

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

### 2026-08-29 — DONE — Automatic follow for Codex
- Commit: 45995d4
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Watch + scheduled task (now on)

### 2026-08-29 — DONE — Codex monitor active
- Commit: (this docs commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. No gameplay until then.


## Board

### DONE
- P0 Win-condition: `playerWin` = `liberation.phase === 'done'`. `despawned` is cleanup. Commit `e36dfeb`. Overlay lock `c5f9d4e`.
- P1 Checkpoint at x=3380 (after heal 3350, before gate 4300). Respawn at marker. Same commit `e36dfeb`.
- Mira balance locks: `game/tests/balance-locks.test.mjs`.
- Cycle-1 reports in: Mira, Kira, Nox, Auron, Vara.
- Channel: GitHub `game-pilot` + this file.
- Codex follow: Watch All activity + 30-minute local monitor (PC must be on).

### APPROVED (aligned, not started)
- P2 Break pack 2480-3000: Brute solo; Farmer-2 and Animal-2 not same activation window. Keep pack close enough that confusion can still hit two bodies. No shared wake with animal-1.
- P2 Wake farmer-1 just after pit 700-820. SPEC LOCK: cannot wake across the pit. Require player.x > 820, or set activation radius so it cannot fire from x<=820 (do not move x and leave activation 520).
- P2 Do not wake boss on pit lip 4130. arenaGate 4300: visible and active both require crossing it. Recovery look-at + refill before gate.
- After P2 (not this pass): start ammo 2/2/2 cap 4, no overflow; Arko ready-to-ready 3s FROM COMMAND (return is inside the window); boss ~180 HP, 26 contact, no combat phases; one-line prompts on first jump / first melee / first bottle. Heal 320 moves after first farmer fight.
- Story voice: adopt `game/reference/KAEL_ONEPAGER.md` + `game/data/kael_idle_lines.proposed.json`. Must also replace hardcoded `IDLE_SPEECH_LINES` in `game.mjs`.
- Audio spec: `game/reference/AUDIO_HOOKS.md` (analyze only, do not wire yet).

### OPEN
- Riven: art/animation gaps (report not in).
- P3 Layout: DROPPED extra rooms. Teach on the existing strip (walk, jump pit, melee farmer, then bottles/Arko, page as reward).
- Small UX: double-jump caption; Arko "no target" on F no-op.
- Story pass 2: thief, in-game mountain name, book origin.

### BLOCKED
- Audio bus + first assets (land/hurt/walk): waiting on Codex hook wiring after analysis.
- VO: waiting on live idle-line swap.
- Start ammo 2/2/2, Arko CD-from-command, boss ~180, first-verb prompts: waiting on P2 layout landing first.

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


