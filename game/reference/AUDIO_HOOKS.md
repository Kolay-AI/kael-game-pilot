# Kael audio hook contract v1

Producer: Orion. Spec only. Codex wires the bus. Auron builds assets after the bus exists.
API: `audio.play(cue, payload?)` one-shots. `audio.music(state)` where state is explore | boss | silence | win | off.
One bus. Three shared samples: boot, impact, glass, plus music states. Pitch/rate variants, not a 40-file library.

Event-based, not hardcoded X:
- `ui_checkpoint` fires on the save event (P1 may move the checkpoint before the arena gate).
- `boss_gate` fires when the boss becomes active/visible (do not bind to x=4300 if the wake point moves).

## One-shots

| Cue | Payload | Fire |
| --- | --- | --- |
| fs_step | gait walk\|sprint | Ground contact walk/sprint, plant frames only |
| jump_takeoff | | Space/W while on ground, vy=-570 |
| jump_land | | Landing (`!wasOn && p.on`) |
| doublejump | | canDoubleJump |
| melee_whoosh | | Combo start, melee windup |
| melee_impact | | canMeleeDamage + overlap |
| player_hurt | | Contact while inv<=0 |
| player_death | | energy<=0 or void, then respawn |
| bottle_throw | | K release, projectile spawn |
| bottle_hit | type frost\|ember\|confusion | Shot hits. No cue on miss |
| arko_call | | startArkoDive (F, ready) |
| arko_dive | | state -> dive |
| arko_hit | target normal\|boss | resolveArkoImpact |
| lib_crack | | beginLiberation / phase crack |
| lib_cloud | | phase cloud |
| lib_sting | | phase look. No VO |
| boss_gate | | Boss becomes active/visible, once per arena entry |
| level_complete | | complete===true overlay |
| ui_page | | collectPage |
| ui_unlock | | Frost mastery overlay, cap 4->5 |
| ui_heal | | heal plant +30 |
| ui_checkpoint | | save event, once |

## Music

explore: spawn, and after liberation look unless in arena/win
boss: boss active
silence: any liberation from crack; boss loop off at beginLiberation
win: complete===true, 4-8s
off: after win / before spawn

silence ducks explore+boss. Do not duck SFX except to keep liberation in front.

## Not in contract

Skid, void-fall, whiff, combo steps, bottle select/empty, status loops, arko_ready, lib reveal/exit, boss phases, idle VO, ambient, material sets, flip.

First asset wave after bus: jump_land, player_hurt, fs_step(walk).
