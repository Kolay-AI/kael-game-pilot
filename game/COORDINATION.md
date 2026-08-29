# Kael coordination

Repo: https://github.com/Kolay-AI/kael-game-pilot
Branch: `game-pilot`
Playable slice: `game/`
Source of truth: this file.
No game-code changes in protocol commits. No merges without Orion + Codex alignment.

## Update protocol

Orion publishes every relevant stand as a commit on `game-pilot`. Each entry below uses this block:

```
### YYYY-MM-DD ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â STATUS ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â short title
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
- Playcheck: Codex implements + `node --test`. Mira plays http://127.0.0.1:8765/ and reports what is visible. Orion marks DONE only after that playcheck. Docs-only commits are not a playable change.
- Local Codex task **Kael GitHub Coordination Monitor**: every 30 minutes, branch game-pilot, SHA + this file. Report only on change. No edits, no merge, no push. ACTIVE. Does not run if the PC is off.

## Updates

### 2026-08-29 - OPEN - Cycle-3 slice 2 jump identity (producer ticket)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Producer: Selcuk play-found that jump reverts Kael to the old look. Slice 1 idle/walk identity (green pants to boot, wrap collar, chunky sole, band) must hold on takeoff, jumpUp, doubleJump, fall, land.
- Orion implements (Codex still idle, next Codex ticket TBD, do not invent work, do not implement this).
- Walk/idle e260fe3 stay signed. Sprint off. No sprites. No clouds/forest/HUD/boss/hills/P2.
- Smoother jump frames (currently 3) is part B after identity holds. Riven spec for keys.
- Next: implement identity-on-jump, then playcheck 8765.


### 2026-08-29 - DONE - Cycle-3 slice 1 Kael identity + walk 24 (Riven play sign-off)
- Commit: e260fe3
- Files: game/art.mjs game/gameplay.mjs game/tests/art-upgrade.test.mjs game/tests/polish.test.mjs
- Tests: 80/80. Riven signed off in a 960x540 play frame: spawn stand (band+tail, wrap collar #f3e4c2, green pants to boot, chunky sole, belt bottles readable) then walk 24@24 (sagittal, planted support, no moonwalk, no sprint chain). Knot/folds in the draw; at play size collar/pants/sole are what read.
- Off this pass: clouds 2784817, forest 1762008, HUD, boss, hills, P2, sprint. No sprites.
- Next: No slice 2 until producer opens it. Codex still idle (next ticket TBD). Do not implement.


### 2026-08-29 - OPEN - Codex next ticket TBD (producer lock)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Producer: Codex is off Cycle-3 graphics/animation. Slice 1 was implemented without Codex at e260fe3 (art.mjs + gameplay.mjs, walk 24). Do not implement, revert, or restyle that slice. Do not start slice 2. Do not recast hills, clouds, forest, HUD, boss, Wonder, sprites.
- Stay tech-lead. Keep reading this file. Next implementation only when producer opens a new ticket with a named task. Task is TBD — do not invent work.
- Next: Codex idle. Wait.

### 2026-08-29 - OPEN - Cycle-3 slice 1 playcheck (Orion build e260fe3)
- Commit: e260fe3
- Files: game/art.mjs game/gameplay.mjs game/tests/art-upgrade.test.mjs game/tests/polish.test.mjs
- Tests: see CODEX.md / local node --test
- Next: Mira/Riven play-sign at http://127.0.0.1:8765/?v=e260fe3 (hard reload). Spawn stand then A/D walk. 960x540 play frame, not a sheet. Orion marks DONE only after that playcheck.


### 2026-08-29 - APPROVED - Cycle-3 slice 1 Kael identity + walk 24 (Riven spec)
- Commit: (this commit)
- Files: game/art.mjs game/gameplay.mjs game/tests/art-upgrade.test.mjs
- Tests: node --test tests/*.test.mjs must stay green
- Next: Codex IMPLEMENT NOW. One commit. Then SHA + files + test result in game/CODEX.md. Playcheck http://127.0.0.1:8765/?v=<sha> hard reload. Riven signs in a 960x540 play frame (spawn stand, then hold A/D walk on meadow). Not a sheet.

IMPLEMENT (Kael only): art.mjs drawKaelCompletePose + gameplay.mjs walk table. Same silhouette, denser draw, twice the walk keys.

A. Identity density (idle + walk share this path; sprint chain off-limits)
Palette lock: yellow #f2ad24 / #ffe36b, blue #123c72 / #1767a8 / #78c9e8, collar/shirt #f3e4c2, pants #39733b / back #2d6134 / #65a545, leather #70402c / #b56b38, outline #171827.
- Band: keep the 32x6 bar + existing tail. Add a knot blob at the tail root (~-16, headY) 6x5 #f2ad24 with 2px #ffe36b. Second tail strand 2px below the first, 18px long.
- Collar: replace the two P.shirt triangles with a wrap collar — 4px #f3e4c2 band around the neck opening. 2px #f3e4c2 cuff on each sleeve where blue meets the leather glove.
- Jacket folds: two 1px #123c72 ticks on the torso front at local y -52 and -48.
- Pants: walk and idle shin limbs are currently P.skin. Paint them P.green (back leg #2d6134) down to the boot. Keep the #65a545 knee tick. Skin stays at the knee cap only.
- Boots: drawBoot sole becomes a 5px #171827 platform; 2px #b56b38 welt above it. Keep metal toe and yellow stitch. Walk still calls drawBoot(boot[0], boot[1]-10) so the contact sole sits at local y=0.

B. Walk in-betweens
ANIMATIONS.walk: {fps:24, frames:24, loop:true}. Same 1.0s cycle as 12@12.
WALK_LEGS 24 rows (12 keys + midpoints, then floor so one support foot is always 0):
[[-12,0,12,-4],[-11,0,12,-4],[-10,0,11,-3],[-8,0,10,-2],[-6,0,8,-2],[-4,0,6,-1],[-2,-1,4,0],[1,-2,0,0],[4,-3,-3,0],[6,-2,-4,0],[9,-1,-6,0],[10,-2,-9,0],[12,-4,-12,0],[12,-4,-11,0],[11,-3,-10,0],[10,-2,-8,0],[8,-2,-6,0],[6,-1,-4,0],[4,0,-2,-1],[0,0,1,-2],[-3,0,4,-3],[-6,0,7,-3],[-8,0,10,-3],[-10,0,11,-4]]
Contact: L planted frames 0-5 and 18-23, R planted 6-17. Every frame has a 0 dy support. Passing ~6 and ~18.
kaelRenderFrame: WALK_LEGS[frame%24]. Walk upperY hold the current 12-cycle two frames each (don't double-speed the bob). Arm swing stays modest opposite (walk branch, right hand ~18 not sprint ~27).
Walk IK stays sagittal. No outward-knee, no pelvisX, no runPose on walk.

Contracts:
- Walk is walk, not sprint. RIGHT_SPRINT_LEGS / SPRINT_LEGS / sprint fps 16 untouched.
- nativeHeroBox ~52x82. Flip still remaps to doubleJump.
- Belt bottles stay readable (#49cde0 / #ed5d4c / #e7d34c).
- Off: clouds 2784817, forest 1762008, HUD, Boss cursedShell, Hills 42x48, P2 layout, idle skip/upperSway.
- No sprite files. No Wonder pipeline. Code-drawn only.

Play-pixel: stand at spawn (collar, knot, green pants to boot, chunky sole), then walk (no pop, no slide, planted foot every frame).


### 2026-08-29 - OPEN - Cycle-3 graphics + animation lift (producer ticket)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Hold 8022806 is lifted for THIS ticket only.
- Producer: Selcuk wants a visible graphic and animation lift in the playable game. Cycle-2 spawn (clouds/forest) did not read as a significant change.
- Scope: still code-drawn (art.mjs + gameplay.mjs). No sprite files this slice. Not a Wonder asset pipeline. Later-art ceiling still stands (no SNES / 16-Mbit cap; Wonder look allowed later).
- Do not reopen: clouds 2784817, forest 1762008, HUD ee86853, boss 200d977, hills-loop 42x48 parked.
- Cadence: one visible change per commit. Playcheck http://127.0.0.1:8765/ after each. Riven signs in a 960x540 play frame. Cache-bust with new SHA.
- Slice 1 (IMPLEMENT ONLY AFTER Orion pastes Riven spec as APPROVED below): Kael body closer to identity (yellow band, blue jacket + white collar, green pants, chunky boots) with more drawn detail; walk smoother (more in-betweens, feet planted, side-gait not sprint). Current walk is 12 frames @ 12fps. Jump is 3 frames (later slice).
- Refs (direction, not copy): Super Mario Wonder richness/readability; classic Mario walk contact. Own ideas ok if they serve identity.
- Codex: do not implement until the slice-1 spec is APPROVED in this file. Then that slice only. Keep tests green. Write SHA + files + test result in game/CODEX.md.
- Next: Riven writes slice-1 spec. Codex idle until APPROVED here.


### 2026-08-29 - DONE - Codex hold (producer lock)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex do not implement. No new game-code, no art, no hills-loop recast, no Wonder pass. Stay tech-lead and keep reading this file. Next implementation only when producer opens a ticket.
### 2026-08-29 - DONE - Hills-loop 42x48 parked (producer lock)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex note only. Do not recast the hills loop. 42x48 boxes remain far-layer; occluded at spawn after forest 1762008. Not a ticket. Cycle-2 spawn art stays closed (identity skip, forest 1762008, clouds 2784817). No new art ticket unless producer opens one.
### 2026-08-29 - DONE - Forest leaf masses hang down trunk (Riven play sign-off)
- Commit: 1762008
- Files: game/art.mjs game/tests/art-upgrade.test.mjs
- Tests: 80/80. Riven signed off in a 960x540 spawn frame (cam 0): 3 masses hang down the trunk. Hill 42x48 boxes on the trunks gone. Same .37 loop. Hills loop untouched. Clouds stay 2784817.
- Next: Cycle-2 spawn art closed (identity skip, forest, clouds). No new art ticket unless producer opens one. Not Wonder. Not sprites.

### 2026-08-29 - DONE - Clouds puffy blobs (Riven play sign-off)
- Commit: 2784817
- Files: game/art.mjs game/tests/art-upgrade.test.mjs
- Tests: 79/79. Riven signed off in a 960x540 spawn frame (cam 0): cloud() is 3 overlapping puffy blobs, not stacked boxes. 8 clouds, wrap, parallax .04 kept. Forest/pit/sky/mountains/hills/dirt/grass/Walk/Kael/HUD/cursedShell off that pass.
- Next: Forest leftover is a separate ticket (1762008). Do not reopen cloud().

### 2026-08-29 - DONE - Forest leaf masses hang down trunk (playcheck, superseded by sign-off below)
- Commit: 1762008
- Files: game/art.mjs game/tests/art-upgrade.test.mjs
- Tests: 80/80. Same .37 loop only. 3 masses grown down (lowest cy+132) so hill 42x48 boxes at y 352-418 sit behind foliage. Hills loop untouched. Clouds 2784817 kept.
- Next: Mira + Riven play-pixel spawn cam 0 at http://127.0.0.1:8765/?v=1762008 (hard reload). Sign if green rectangles on trunks are gone. Orion marks DONE only after that playcheck.

### 2026-08-29 - DONE - Forest canopies leaf blobs (Riven play sign-off)
- Commit: ad03345
- Files: game/art.mjs game/tests/art-upgrade.test.mjs
- Tests: 78/78. Riven signed off in a 960x540 spawn frame (cam 0): clustered canopies, not stacked crates. Sky/clouds/mountains/hills/dirt/grass untouched.
- Next: Cycle-2 continues. Next one-change still code-drawn, not Wonder.
### 2026-08-29 - APPROVED - Later art ceiling (producer lock)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex note only. Do not implement this pass. Cycle-1 art stays closed. Pilot remains code-drawn side-view.
- Lock: later Kael/world art is as beautiful as possible. No SNES cap. No 16-Mbit cap. Super Mario Wonder as a look is allowed. Selcuk's yellow-headband / blue-jacket / green-pants / chunky-boots ref is character identity, not a fidelity ceiling. Not a ticket to start now. No sprite files this cycle unless producer opens one.
### 2026-08-29 — DONE — Boss cursedShell lord purple + horns (Riven play sign-off)
- Commit: 200d977
- Files: game/art.mjs game/tests/art-upgrade.test.mjs
- Tests: 77/77. Riven signed off in a 960×540 arena frame (cam 4260, boss-1 x:4740): body #633a6f, horns above 70×76. farmer/animal/brute unchanged.
- Next: Cycle-1 art closed (idle skipped). 4fps idle upperSway parked. No new art ticket unless producer opens one.
### 2026-08-29 â€” DONE â€” HUD icons (Riven play sign-off)
- Commit: ee86853
- Files: game/game.mjs game/tests/art-upgrade.test.mjs
- Tests: node --test tests/*.test.mjs â†’ 76/76. Riven signed off in a 960Ã—540 play frame at spawn (not a sheet): flask+leaf, 200px bar, three bottles + yellow select, Arko bird, page glyph. F8/walk/P2 untouched.
- Next: Kael idle lock (walk already signed off 8ef11ef). Then boss unique curse color + horns if idle is skipped.
### 2026-08-29 Ã¢â‚¬â€ OPEN Ã¢â‚¬â€ HUD icons (Riven spec)
- Commit: (this commit)
- Files: game/game.mjs game/tests/art-upgrade.test.mjs
- Tests: node --test tests/*.test.mjs Ã¢â€ â€™ 76/76
- Next: Mira playcheck at http://127.0.0.1:8765/ (hard reload). Riven confirm the HUD read: no ENERGIE/SEITEN/FROST/ARKO words, green flask+leaf, three bottles + yellow select frame, Arko bird dim on CD, page glyph + n/3. F8 untouched. Q/E/K/F unchanged.
### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â OPEN ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â P2 playcheck loop
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex implement P2 layout NOW on game-pilot (farmer clamp, brute pack stagger, boss not at 4130). Unit tests green is not enough. After push, write SHA + files + test result in game/CODEX.md. Playcheck is Mira at http://127.0.0.1:8765/ ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Orion marks DONE only after that playcheck, never after docs-only commits.

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â APPROVED ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Riven cycle-1 art locks
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex keep P2 layout-only and honor art constraints (no new tiles/biomes/sprites). Art must-haves after P2.

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â APPROVED ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Vara cycle-1 locks + P2 spec
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex implement P2 layout with farmer-1 activation clamp (must not wake across pit 700-820). Do not ship ammo/Arko-CD/boss-HP in this pass.

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â APPROVED ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Start P2 layout now
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Codex implement the three P2 layout items on game-pilot. Keep tests green. No story/audio wiring. Do not wait on Vara/Riven for this pass.

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Bidirectional channel closed KAEL-PING-CODEX-B
- Commit: 39990b4 (Codex reply), this ack
- Files: game/CODEX.md, game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. No chat paste either way.


### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Comms ping KAEL-PING-20260829-A
- Commit: 3f1ccb2
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. Channel works.

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â P0 win + P1 checkpoint
- Commit: e36dfeb
- Files: game/game.mjs, game/rules.mjs, game/tests/rules.test.mjs
- Tests: 66/66 green (`node --test` under game/)
- Next: overlay lock tests (done in c5f9d4e)

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Overlay locks
- Commit: c5f9d4e
- Files: game/tests/win-overlay.test.mjs
- Tests: 2/2 green
- Next: GitHub as channel (c1ac995)

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â GitHub channel + board
- Commit: c1ac995
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: this update-protocol commit (docs only)

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Automatic follow for Codex
- Commit: 45995d4
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: Watch + scheduled task (now on)

### 2026-08-29 ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â DONE ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Codex monitor active
- Commit: (this docs commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Next: wait for Vara and Riven. No gameplay until then.


## Board

### DONE
- P0 Win-condition: `playerWin` = `liberation.phase === 'done'`. `despawned` is cleanup. Commit `e36dfeb`. Overlay lock `c5f9d4e`.
- P1 Checkpoint at x=3380 (after heal 3350, before gate 4300). Respawn at marker. Same commit `e36dfeb`.
- Mira balance locks: `game/tests/balance-locks.test.mjs`.
- Cycle-1 reports in: Mira, Kira, Nox, Auron, Vara, Riven.
- Channel: GitHub `game-pilot` + this file.
- Codex follow: Watch All activity + 30-minute local monitor (PC must be on).

### APPROVED (aligned, not started)
- P2 Break pack 2480-3000: Brute solo; Farmer-2 and Animal-2 not same activation window. Keep pack close enough that confusion can still hit two bodies. No shared wake with animal-1.
- P2 Wake farmer-1 just after pit 700-820. SPEC LOCK: cannot wake across the pit. Require player.x > 820, or set activation radius so it cannot fire from x<=820 (do not move x and leave activation 520).
- P2 Do not wake boss on pit lip 4130. arenaGate 4300: visible and active both require crossing it. Recovery look-at + refill before gate.
- P2 art constraints (do not break): meadow/forest only; tileSize 16; dirt+grass cap; groundY 470; LEVEL_WIDTH 5400; no new tile materials/palettes/parallax; parallax speeds clouds .04 / mountains .11 / hills .23 / forest .37; decor only grass/flowers/bushes/rocks/trees/stumps; footprints farmer ~46x55, animal 44x38, brute 52x60, boss 70x76; code-drawn only, no sprite files; facing is a flip (no one-sided scenery); no extra lime fills; hero box ~52x82 foot-pivot on ground; checkpoint pole ~364-470.
- After P2 (not this pass): start ammo 2/2/2 cap 4, no overflow; Arko ready-to-ready 3s FROM COMMAND (return is inside the window); boss ~180 HP, 26 contact, no combat phases; one-line prompts on first jump / first melee / first bottle. Heal 320 moves after first farmer fight.
- After P2 art must-haves (code-drawn, no sprite files): (1) enemy silhouettes that survive curse overlay tool/4-leg/wide/horns (2) bottle projectiles bigger, color+shape matched to belt (3) Arko contrast + follow vs dive poses (4) HUD icons for energy/bottles/Arko ready, kill raw labels (5) Kael side-view idle/walk, planted feet, readable belt, stop salto spend (6) boss unique curse color + horns at 960x540.
- Story voice: adopt `game/reference/KAEL_ONEPAGER.md` + `game/data/kael_idle_lines.proposed.json`. Must also replace hardcoded `IDLE_SPEECH_LINES` in `game.mjs`.
- Audio spec: `game/reference/AUDIO_HOOKS.md` (analyze only, do not wire yet).

### OPEN
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


