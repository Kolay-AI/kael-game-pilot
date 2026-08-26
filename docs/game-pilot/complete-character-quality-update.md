# GAME PILOT 0.1 - COMPLETE CHARACTER QUALITY UPDATE

Status: CONDITIONAL PASS pending manual desktop-browser visual verification.

1. Kael Form: chamfered head, hair, jacket, limbs, gloves, knees and boots.
2. Kael Pixel-Tiefe: layered SNES palette clusters, highlights, soles and bottles.
3. Kael Gesicht/Mimik: readable eyes, brow/mouth variants and two idle blink phases.
4. Idle: eight-frame breathing, weight shift and secondary headband motion.
5. Walk: twelve articulated contact/down/passing/up frames, alternating feet and arms.
6. Sprint: twelve longer-stride frames with lean, knee lift and stronger arm drive.
7. Jump: anticipation, push-off, three ascent states and distinct fall states.
8. Fall: three landing-preparation poses, separate from ascent.
9. Landing: six-frame compression/recovery with planted feet.
10. Crouch: real lowered pose and shortened collider, not vertical scaling.
11. Attack: eight windup/active/follow-through/recovery frames and aligned hitbox.
12. Bottle Throw: eight prepare/release/recovery frames; projectile starts at hand.
13. Hurt: hit pose, knockback, impact sparks and recovery timing.
14. Arko Facing: runtime face follows Kael outside dives and targets during dives.
15. Arko Form: organic eagle silhouette with beak, tail and layered wings.
16. Arko Animation: flapping wings, hover correction, dive curve and return.
17. Arko Damage: normal/strong 15, boss 8, one hit per dive and cooldown retained.
18. Ember: damage plus warm fire marker and impact feedback.
19. Frost: finite slow effect with blue status marker.
20. Confusion: direction changes, enemy interaction and yellow status marker.
21. Gegnerformen: cursed shells and distinct farmer, animal, brute and boss silhouettes.
22. Befreite Wesen: separate organic human/animal normal renderers.
23. Befreiung: shell, green cloud, normal reveal, reaction and evacuation sequence.
24. Boden: varied grass edge, dirt tile variants and contact shadows.
25. Plattformen: readable tops with angled, organic underside corners.
26. Trefferfeedback: hit flash, impact sparks, knockback/stagger and status markers.
27. Geaenderte Dateien: `game/art.mjs`, `game/gameplay.mjs`, `game/game.mjs`, `game/rules.mjs`, tests, docs and rebuilt `game/dist/`.
28. Tests: PASS - 54/54 Node tests; syntax checks and production build PASS.
29. Korrekturrunden: previous art pass, hard animation/effects pass, twelve-frame pass and Arko facing pass integrated.
30. Known Issues: no automated screenshot comparison; browser visual inspection remains outstanding.
31. Manuell zu pruefen: walk/sprint readability, blink, Arko left/right facing, Frost/Confusion behavior, all level-complete flows.
32. CHEF status: CONDITIONAL PASS; release gate stays locked until manual browser verification.
