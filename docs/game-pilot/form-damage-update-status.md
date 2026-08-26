# GAME PILOT 0.1 – FORM & DAMAGE UPDATE STATUS

Stand: 2026-08-26 · Branch: `game-pilot`

1. **Kael-Formverbesserungen** – gestufte Pixelkonturen für Kopf, Gesicht, Beine und Stiefel; organischere Gelenke, Handschuhe, Haar-/Bandbewegung und weiterhin Referenzfarben/-silhouette.
2. **Gegner-Formverbesserungen** – deformierte Fluchhülle mit Wucherungen sowie gestufte Silhouetten für Bauer, Tier, Brute und Boss.
3. **Befreite Wesen** – normale Menschen und Tiere werden mit organischeren Körper-, Kopf-, Bein- und Fellkonturen gezeichnet.
4. **Boden-Verbesserungen** – leicht unregelmäßige Gras-/Erdkante und zusätzliche Oberflächenpixel ohne Änderung der Kollisionsflächen.
5. **Plattform-Unterseiten** – kleine Plattformen besitzen abgesetzte, abgeschrägte Unterseiten statt harter Rechteckkanten.
6. **Arko-Damage-Status** – normal/stärker: 15 HP plus kurzer Stun; Mini-Boss: 8 HP plus kurzer Flinch; ein Treffer pro Dive, Knockback vom Spieler weg, danach Rückkehr/Cooldown.
7. **Trefferfeedback** – Hit-Flash, Impact-Sparks, Reaktionsbewegung und Knockback für Nahkampf/Arko.
8. **Geänderte Dateien** – `game/art.mjs`, `game/game.mjs`, `game/gameplay.mjs`, `game/tests/art-upgrade.test.mjs`, `game/dist/*` sowie diese Statusdokumentation.
9. **Tests PASS/FAIL** – PASS: 51/51 Spieltests, Syntaxchecks, Build; FAIL: keine automatischen Tests.
10. **Known Issues** – ein manueller Desktop-Browser-Playthrough ist weiterhin erforderlich; finale Sprite-Sheets und Audio gehören nicht zum Pilotumfang.
11. **Manuell zu prüfen** – Spiel starten, Arko sichtbar auf jeden Gegnertyp einsetzen, HP-Balken/Hit-Flash/Knockback prüfen, Freed-Formen und Plattformkanten bei Bewegung/Jump ansehen.
12. **CHEF-Status** – technisch abnahmebereit; vollständiges Release-PASS erst nach manuellem Browser-Test.
