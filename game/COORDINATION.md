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

### 2026-08-30 - APPROVED - Mira playcheck 463b9d5 idle+walk PASS
- Play: http://127.0.0.1:8765/?v=463b9d5
- Spawn is Wonder later-art sheets, not a924184/868c989 voxel clay.
- Identity holds idle and walk. Bottles cyan/red/yellow readable. Idle may show a 4th blob (cork/buckle), not a fail this slice.
- Jump still code-drawn. World/Arko still voxel, out of slice.


### 2026-08-30 - DONE - Hugo 463b9d5 Wonder idle+walk sprites in 8765
- Commit: 463b9d5 (pushed)
- Play: http://127.0.0.1:8765/?v=463b9d5
- Tests: 84/84
- Files: game/sprites/kael-idle.png, game/sprites/kael-walk.png, art.mjs drawWonderKael for idle+walk only
- a924184 stays rejected
- Jump still code-drawn. Jumper HOLD lifted, base is 463b9d5
- Mira: playcheck opened on 463b9d5 (must not look like a924184)


### 2026-08-30 - BLOCKED - Hugo a924184 rejected (not Wonder in 8765)
- Commit: a924184 is an 8-line code-drawn tweak, not later-art sprites. User sees no visual change.
- Hugo: redo Slice 1. Idle+walk must read as the Wonder sheets, not a denser SNES Kael.
- Jumper: HOLD. Do not build jump on a924184. Wait for a new base SHA.


### 2026-08-30 - OPEN - Jumper sprite slice 2 (Kael jump/fall/land into 8765)
- Assignee: Jumper (not Hugo, not Codex)
- Base: a924184 (Hugo idle+walk). Do not rewrite idle/walk.
- Files: extend Hugo's hero sprite pipeline for takeoff, jumpUp, doubleJump, fall, land
- Goal: Wonder identity holds in the air. No new gameplay.
- Identity: yellow band #f2ad24 two tails, jacket #1767a8, cream collar/cuffs #f3e4c2, pants #39733b to chunky boots (no tan shins), three belt bottles. Skin hands. Not Mario.
- Codex: idle. Hugo: idle+walk done, do not take jump.
- Done: SHA + play http://127.0.0.1:8765/?v=<sha>, tests green, report to Orion.


### 2026-08-30 - DONE - Hugo a924184 idle+walk in 8765
- Commit: a924184
- Play: http://127.0.0.1:8765/?v=a924184
- Tests: 83/83
- Slice 1: Wonder idle+walk. Jump still code-drawn. Codex idle. Jumper gets jump when that agent exists.
- Mira: playcheck opened.


### 2026-08-30 - DONE - Hugo sprite slice 1 (Kael idle+walk into 8765)
- Assignee: Hugo (not Codex)
- Files: game/art.mjs and whatever sprite pipeline is needed
- Playable today: 868c989 code-drawn. Wonder later-art is not in 8765 yet.
- Goal: Kael idle + walk in the locked Wonder 2.5D claymation look. Identity must hold in idle AND in motion. No jump/world/enemies this slice. No new gameplay.
- Identity: yellow band #f2ad24 two tails, blue jacket #1767a8, cream collar/cuffs #f3e4c2, green pants #39733b to chunky brown boots (no tan shins), three belt bottles frost/ember/confusion. Skin hands, not gloves. Not Mario.
- Codex: idle. Do not take this ticket.
- Done: SHA + play link http://127.0.0.1:8765/?v=<sha>, tests green, report to Orion.


### 2026-08-29 - APPROVED - Wonder space sheets (Riven)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs. Playable stays 868c989. No sprites in 8765.
- Lock: Later-art space sheets only. P2 coordinates stay. No art.mjs.
- Pit: missing bite of the same loaf (yellow dirt / green shell-lip / thick brown clay cut). Lip breaks, crumbs, shadow in the void, opposite lip same shell. See-through to haze hills. First-jump width. Not a black rectangle.
- Forest-ends ~3150-4300: trees thin, grape-cluster canopies fewer. Gate = forest edge opening onto the arena slab. Not a dungeon door. No climb. Berg grows as haze snow-peak beyond.
- Berg der Verdammten: picture-book haze peak. Beautiful, a little too still. Promise, not a climb. Not horror, not jagged alpine.
- Flowers white/muted. Identity and Vara play-reads unchanged.
- Codex: do not implement. No sprite ticket.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder character bible (Riven)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs. Playable build stays 868c989 (code-drawn). No sprites in 8765.
- Lock: Wonder 2.5D claymation / toy volume is the only later-art look. Not Mario. Not pixel upscale. Not SNES. Medium: matte painted clay / vinyl toy. Rounded chunky volume, soft studio light, slight surface pores. Large head, large hands, oversized boots. Cream collar is the loudest jacket read.
- Identity hex (must hold in every pose): yellow band #f2ad24 knot at back two long flat tails; blue jacket #1767a8; cream wrap collar + cuffs #f3e4c2 (fleece); green pants #39733b to the boot cuff, no tan shins; chunky brown boots thick dark sole molded laces/straps; belt three corked bottles frost round cyan, ember squat red, confusion taller yellow.
- Bottles in-hand: frost = round flask + snowflake stamp; ember = squat angular vial + flame; confusion = tall corked bottle + question mark. Gold clay glints, not spark particles. Hands are skin + cream cuffs, not brown gloves.
- Do not: Mario hat/overalls/gloves, pixel grid, SNES dither, glass-photoreal, extra lime grass, fourth belt bottle.
- Sheets this drop: sprint, hurt/recoil, throw (frost leaving the hand, two bottles remain on belt), bottles-in-hand. Idle + spawn already locked.
- Same toy volume later (not this drop): cursed-shell farmer/animal/brute, boss purple horns #633a6f, freed villagers.
- Codex: do not implement. No art.mjs. No sprite ticket yet.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder QA gate (Mira)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs; playtest only after sprites land in 8765
- Lock: 868c989 stays the playable code-drawn build. No Wonder sprite playtest until a SHA is in 8765.
- FAIL if any pose drops identity (idle/walk/jump/fall/doubleJump/melee/throw/hit/crouch): yellow band + two tails, blue jacket + cream collar/cuffs, green pants to chunky brown boots (no tan shins), belt with cyan/red/yellow bottles.
- FAIL if it reads as Mario (red cap, overalls, mustache, red/blue Nintendo silhouette).
- FAIL if unreadable at 960x540: curse-shell vs freed form, bottle type (frost/ember/confusion) in throw, Arko as bird (ready vs dim on cooldown).
- PASS only if identity holds in idle AND in the air, clay/Wonder read (round, toy, not SNES boxes), and bottles/Arko/curse/freed are distinguishable at canvas size.
- Codex: do not implement sprites. No playcheck ticket until a sprite SHA exists.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder level-art spaces (Kira)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Lock: Later-art space map only. P2 coordinates stay. No code, no new pass.
- Read grammar: walkable = yellow dirt + green shell-lip + thick brown clay cut. The lip is the jump silhouette. Play strip sharp; mid/BG tilt-shift soft. No box-hills: loaves and hills only.
- Spawn 80-530 = the plate. Forest room, dirt band, fences as depth not collision. Puffy tree wall keeps the path readable. Berg der Verdammten already sits here as a haze snow-peak on the horizon (promise, not playable).
- Pits 700, 1320, 2130, 3150, 4130: missing piece of the same loaf, not a black rectangle. Lip breaks, cut looks into the gap, shadow in the void, opposite lip same shell + clay crumbs. See-through to haze hills. Width stays locked (~120-130). First jump single. A DJ-only gap (P3) is a wider missing loaf, not a taller box.
- High plats: same loaves, round, slightly set into the tree layer. Pages sit on the loaf, not on a box-stair.
- Path to the mountain: background of this pass only. LTR forest thins from ~3150, peak grows. Corridor 3150-4300 reads as forest-ends. Gate = forest edge. Arena slab locked. Mountain behind as goal, no climb.
- Codex: do not implement. No sprites, no geometry change.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder play-reads (Vara)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Lock: Play at 960x540. Identity track = yellow band + blue jacket + boot mass (green pants may sink into grass). Silhouette: spiky hair, trailing band, cream collar, boot bricks. Collar may shrink in-play; belt bottles cannot. Chibi ok; Mario hat/overalls/gloves/coin-dot eyes not.
- Bottles: frost cyan, ember red, confusion gold. Three on belt, never four. Distinct from jacket-blue and from ground flowers (flowers white/muted, no bottle hues). HUD selected bottle matches belt glow of same type.
- Arko: white head + yellow beak + chunky talons. Perch = partner not power-up. Dive = short clay streak + talon-hit, then stun/flinch as now. Never tanooki tail or hat.
- Pages: book-page silhouette, not flower/coin/Wonder-seed. One read at 32px: cream sheet + dark mark. Plants (heal/resource) are leaf-clumps, not bottles.
- Curse vs freed: cursed = opaque shell, sick green/purple, HP pip. Freed = human/animal clay, Danke!/Frei!, walk-off. Liberation spark = shell-crack + green curse-cloud, not coin burst/stamp/stomp-kill. HP bars should not read as a kill-game.
- Juice: squash/stretch on land and hit. Melee = clay impact not sparkle. Throw = bottle-shaped blob by type. Hit = white flash + knockback in one frame. No Wonder purple-sparkle on attacks.
- Not Mario: no question blocks, coins, pipes, red/blue mushrooms, stamp cards, or collect-3-sparks. Wonder is material and camera, not the verb set. We free shells. We do not stomp.
- Scale at 960x540: Kael ~56px. Belt bottles >= 6px color-locked. Arko dive >= 24px. Page >= 16px. Curse shell outline >= 2px vs grass. Play strip higher-contrast, less floral than lush BG.
- Riven owns the look. These play-reads cannot drop. Codex: do not implement. No sprites.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder tone (Nox)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Lock: Claymation is material, not a Nintendo quote. Curse sits on the beauty: shells feel closed, forest too still, mountain looks like a picture book on purpose. Liberation = the diorama is right again (Danke!/Frei!), not kill fireworks. Copy words: Wald, Hang, Hülle, Buch, Adler. Never pipes, Wonder-flowers, franchise. Idle voice stays. Thief/book origin still parked.
- Codex: do not implement story/copy. No sprites.
- Next: specialists keep creating the look. No game-code.


### 2026-08-29 - APPROVED - Wonder audio mood (Auron)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Lock: Explore = warm foothills, wood/leaf/air, orchestra/folk, toy-volume. Walk = dull earth thud + moss squish, never stone/military. Jump/land = plump boof/pop (clay boy). Impact vs curse = thick resin/glass, not flesh. Bottles = toy-lab glass (frost cool, ember short-warm, confusion friendly-skewed). Curse = hollow, slightly detuned, still toy; no horror drone. Liberation = peak (sugar/resin crack, soft-green cloud, short warm bells), then silence, then explore. Boss-gate = thinner darker pulse, same world, not FF wall; on beginLiberation drop to silence then crack. Arko = short proud call, dive = wing body, hit = claws in resin.
- Out: chip-only bed, 8-bit arps as bed, metal, dry kick, horror stinger, Berg-Verdammnis OST.
- Codex: do not implement audio. No files this pass.
- Next: wait for a sound ticket. Art look lock still Wonder 2.5D.


### 2026-08-29 - APPROVED - Wonder 2.5D look lock (producer)
- Commit: (this commit)
- Files: game/COORDINATION.md
- Tests: n/a docs
- Lock: Super Mario Bros Wonder claymation 2.5D is the ONLY later-art look. Not a Mario copy. Identity stays: yellow band + knot/tails, blue jacket, cream wrap collar, green pants to chunky brown boots, belt bottles. No SNES cap. No pixel upscale of the code-drawn hero.
- Playable game-pilot stays the code-drawn build at 868c989 until producer opens a sprite/pipeline ticket. Do not drop Wonder sprites into art.mjs this pass.
- Codex: still idle, next code ticket TBD. Do not invent work. Do not implement this look.
- Specialists create the look: Riven art bible + sheets, Vara readability/juice locks, Nox tone, Kira level-art spaces, Auron mood, Mira identity QA. Orion coordinates and keeps generating later-art.
- Next: specialists return their locks. No game-code until a new ticket.


### 2026-08-29 - DONE - Cycle-3 slice 2 jump identity + in-betweens (Riven play sign-off)
- Commit: 868c989
- Files: game/art.mjs game/gameplay.mjs game/tests/art-upgrade.test.mjs game/tests/polish.test.mjs
- Tests: 82/82. Riven signed off in 960x540 play poses: takeoff/jumpUp/fall/land/doubleJump green pants to boot, no tan shins. Wrap collar, band, chunky sole hold in the air. jumpUp 6@16, fall 6@16, takeoff 8@18, land 8@18. Walk/idle e260fe3 locked. Sprint off.
- Next: No slice 3 until producer opens it. Codex still idle (next ticket TBD). Do not implement.


### 2026-08-29 - OPEN - Cycle-3 slice 2 playcheck (868c989)
- Commit: 868c989
- Files: game/art.mjs game/gameplay.mjs game/tests/art-upgrade.test.mjs game/tests/polish.test.mjs
- Tests: 82/82
- Next: Riven + Mira play-sign at http://127.0.0.1:8765/?v=868c989 (hard reload). 960x540: spawn, Space through takeoff/jumpUp/fall/land, F/doubleJump. Green pants must stay in the air. Orion marks DONE only after that playcheck. Codex still idle TBD.


### 2026-08-29 - APPROVED - Cycle-3 slice 2 jump identity + in-betweens (Riven spec)
- Commit: (this commit)
- Files: game/art.mjs game/gameplay.mjs game/tests/*.test.mjs
- Tests: node --test tests/*.test.mjs must stay green
- Next: Orion IMPLEMENT NOW (Codex still idle, TBD, do not implement). Playcheck http://127.0.0.1:8765/?v=<sha> hard reload. Riven signs 960x540: spawn, then Space through takeoff/jumpUp/fall/land, and F/doubleJump. Not a sheet.

Walk/idle/sprint OFF LIMITS. Walk e260fe3 locked.

A. Identity leak (takeoff, jumpUp, doubleJump, fall, land)
- Shin: P.green (back #2d6134), knee tick #65a545. Skin only 3x2 knee cap. No P.skin shin.
- Jacket: drop normalJump poly. Use idle/walk blob + wrap collar (#f3e4c2 24x4 at neck, 4x6 tabs) + two #123c72 fold ticks + shirt cuffs at gloves. Band knot + two tails stay.
- Boots: drawBoot 5px #171827 sole, #b56b38 welt. Air poses drawBoot(x,y) without walk dy-10 plant.
- doubleJump: identity only. Keep 10-frame table / armSwing. No salto restyle.

B. Jump in-betweens
ANIMATIONS: takeoff {fps:18, frames:8, loop:false}; jumpUp {fps:16, frames:6, loop:false}; fall {fps:16, frames:6, loop:false}; land {fps:18, frames:8, loop:false}; doubleJump stays 10@12.
TAKEOFF_LEGS 8: [[-2,3,3,2],[-2,3,3,2],[-2,2,3,1],[-2,2,3,0],[-3,1,4,-2],[-3,0,4,-3],[-3,0,4,-4],[-3,0,4,-4]]
JUMP_UP_LEGS 6: [[-3,1,5,-3],[-2,0,4,-4],[-2,0,4,-5],[0,-1,4,-6],[1,-2,5,-6],[2,-3,5,-7]]
FALL_LEGS 6: [[4,-3,-4,0],[5,-2,-5,1],[6,-1,-6,2],[4,0,-4,3],[3,1,-2,4],[2,2,-1,5]]
LAND_LEGS 8: [[2,-1,-2,0],[1,0,-1,0],[0,2,2,1],[0,2,1,1],[0,1,1,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]]
kaelRenderFrame: index by frame, no leftover %3. takeoff/land upperY: frames 0-2 = 5, else 2. jumpKneeLift can stay (takeoff 4, jumpUp 8, fall 4). IK default sagittal leg().

Off: clouds 2784817, forest 1762008, HUD, boss, hills, P2, sprites, Wonder pipeline. nativeHeroBox ~52x82. Belt bottles readable. Flip remaps to doubleJump.


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


