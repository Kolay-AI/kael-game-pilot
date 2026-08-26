# GAME PILOT 0.1 - KAEL ANIMATION PASS STATUS

Stand: 2026-08-26; Branch: `game-pilot`

1. **Idle animation** - 8 frames, breathing/weight-cycle and visible blink phases.
2. **Walk animation** - 12 frames with planted contact, passing, push-off, alternating boots and counter-swing.
3. **Sprint animation** - 12 frames with longer stride, stronger lean and higher leg lift.
4. **Jump animation** - separate 4-frame takeoff, 3-frame ascent, 3-frame fall and 6-frame landing states.
5. **Landing animation** - feet-first contact, knee/hip compression and recovery frames.
6. **Crouch animation** - existing collider-safe crouch retained; feet stay planted.
7. **Melee animation** - 8-frame windup/active/follow-through/recovery contract retained.
8. **Bottle throw animation** - 8-frame prepare/release/recovery contract; projectile anchor remains at the hand side.
9. **Hurt animation** - hit pose and knockback/impact feedback retained.
10. **Facial animation** - both eyes readable; idle blink is rendered visibly.
11. **Secondary motion** - hair, headband tails and belt bottles react to movement/jump phases.
12. **Anatomy/form** - organic stepped contours, wider shoulders, articulated limbs and characteristic boots preserved.
13. **Frost** - 12 HP, strong slow (24 percent chase speed), blue status marker, finite 3-second timer.
14. **Confusion** - 6 HP, direction changes every 0.42 seconds, yellow status marker and ally-hit behavior.
15. **Ember** - 38 HP damage and warm impact feedback retained.
16. **Arko damage** - 15/15/8 HP profiles, one target hit per dive, stun/flinch, knockback and cooldown.
17. **Changed files** - gameplay/art/game/rules modules, tests and rebuilt `game/dist/*`.
18. **Tests PASS/FAIL** - PASS: 52/52 game tests, syntax checks and build; FAIL: none automated.
19. **Known Issues** - final production sprite sheets/audio are outside pilot scope; manual visual browser sign-off remains open.
20. **Manual verification** - observe all 12 walk/sprint phases, idle blink, jump/landing weight, bottle effects and Arko HP reduction in the desktop browser.
21. **CHEF status** - conditional pass pending the user's manual visual verification.
