# GAME PILOT 0.1 – HARD ANIMATION & EFFECT UPDATE STATUS

Stand: 2026-08-26 · Branch: `game-pilot`

1. **Walk-Verbesserungen** – 8 deutlich unterscheidbare Schrittphasen mit Vor-/Rückfuß, sichtbarer Stiefelarbeit, Arm-Gegenschwung und Gewichtsverlagerung.
2. **Sprint-Verbesserungen** – größere Schrittweite, stärkere Beinauslenkung, Vorneigung und dynamischerer Rhythmus.
3. **Gesichts-/Mimik-Verbesserungen** – beide Augen lesbar, sichtbares Idle-Blinzeln und klarerer Kopf-/Stirnbandbereich.
4. **Kael-Formverbesserungen** – organische gestufte Konturen bleiben aktiv; Oberkörper bewegt sich zyklisch, ohne die Fußanker zu verlieren.
5. **Gegner-/Befreiten-Verbesserungen** – Fluch-Wucherungen und eigene organische Freed-Human/Freed-Animal-Silhouetten.
6. **Ember/Frost/Confusion** – Ember-Schaden bleibt erhalten; Frost verlangsamt auf 24 %, blaues Statussymbol und endlicher Timer; Confusion wechselt periodisch die Richtung, zeigt gelbe Desorientierungsmarker und kann nahe Gegner treffen.
7. **Arko-Damage** – exakt 15/15/8 HP, einmal pro Dive, Stun/Flinch, Knockback, Impact-Feedback und Cooldown.
8. **Geänderte Dateien** – `game/gameplay.mjs`, `game/art.mjs`, `game/game.mjs`, `game/rules.mjs`, `game/tests/polish.test.mjs`, `game/tests/rules.test.mjs`, `game/dist/*`.
9. **Tests PASS/FAIL** – PASS: 52/52 Spieltests, Syntaxchecks, Build; FAIL: keine automatischen Tests.
10. **Known Issues** – manueller Screenshot-/Browservergleich bleibt erforderlich; finale Sprite-Sheets und Audio sind außerhalb des Pilots.
11. **Manuelle Prüfung** – Walk/Sprint bei normalem Gameplay beobachten; Idle-Blinken abwarten; jede Flasche auf Gegner einsetzen und Frosttimer/Confusion-Richtungswechsel sichtbar prüfen; Arko-HP und Impact kontrollieren.
12. **CHEF-Status** – automatische Korrekturrunde bestanden; vollständige Freigabe erst nach manueller Sichtabnahme.
