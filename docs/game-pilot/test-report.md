# Testbericht – GAME PILOT 0.1

Stand: 2026-08-26

## Automatische Prüfungen

- `node --test game/tests/*.test.mjs`: 39/39 bestanden.
- `node --check game/game.mjs`: bestanden.
- `node --check game/gameplay.mjs`: bestanden.
- `node --check game/level-data.mjs`: bestanden.
- `node --check game/rules.mjs`: bestanden.
- `node game/scripts/build.mjs`: bestanden; Build unter `game/dist/` erzeugt.
- SHA-256-Vergleich von `index.html`, `style.css`, `game.mjs`, `gameplay.mjs`, `level-data.mjs` und `rules.mjs` zwischen Quelle und Build: 6/6 identisch.
- Python-/LangGraph-Regression einschließlich Diagnoseprogramme: 634/634 bestanden.

## Korrekturschleife

Der erste TESTER-Lauf fand vier Fehler: blockierte Boss-Befreiung, Mehrfachtreffer pro Nahkampfangriff, framerateabhängige Verwirrungstreffer und einen rein visuellen Duck-Zustand. Der UMSETZER korrigierte alle vier Punkte. Der PRÜFER forderte anschließend eine echte Wirkung der dritten Seite sowie eine vollständig gestaffelte Befreiungsdarstellung. Auch diese Punkte wurden korrigiert. Die finale Suite prüft zusätzlich idempotente Progression und die geordnete Befreiungsfolge bis zum Abschluss.

## Noch offene Abnahme

Der lokale HTTP-Server startete erfolgreich. Ein steuerbarer Browser war in der Ausführungsumgebung jedoch nicht verfügbar. Deshalb ist ein visueller/interaktiver End-to-End-Durchlauf auf einem Desktop-Browser noch offen und wird nicht als bestanden ausgewiesen.

## Gesamtkorrekturrunde – manueller Befund

Nach dem ersten manuellen Pilot-Test wurden Facing, Grafikqualität, verschwundene Gegner und Arkos einmalige Nutzung korrigiert. Die Ursachen waren global zu früh aktive Gegner, fehlende Facing-Spiegelung und eine unvollständige Arko-Zustandsmaschine.

Der unabhängige TESTER gab die Umsetzung zweimal zurück: zuerst wegen einer inkonsistenten Duck-Höhe und zu tief gesetzter Bauern-Spawns, danach wegen eines abgesenkten visuellen Crouch-Fußankers und asymmetrischer realer Projektilzentren. Nach den Korrekturen bestätigt die Suite unter anderem:

- sechs stabile Gegner-Spawns und alle vier Pflicht-Typen,
- Aktivierung, Sichtbarkeitskorridor, Boss-Gate, Tether und Void-Reset,
- acht Kael-Posen in beiden Richtungen sowie symmetrische Wurf- und Nahkampfanker,
- fünf Arko-Einsätze mit Rückkehr, Zielverlustbehandlung und gemessenem Drei-Sekunden-Cooldown,
- sichtbare Befreiungszustände für Hülle, Wolke, Normalform, Blick und Abgang.

## Art-Upgrade-Abschluss

- `node --test game/tests/*.test.mjs`: 50/50 bestanden, einschließlich zentralem Arko-Impact-Gate, echtem HP-Abzug, Knockback-Richtung und ungültigen Zielen.
- Kael-Renderer gegen die verbindliche Referenz geprüft; zusätzliche 16-Bit-Details und Animationsakzente sind in `game/art.mjs` umgesetzt.
- Gegner-, Freed-, Arko-, Terrain- und Parallax-Renderer geprüft; der alte Prototyprenderer wird im aktiven Draw-Pfad nicht mehr verwendet.
- TESTER: bestanden. PRÜFER: bestanden unter dem Vorbehalt des weiterhin offenen manuellen Browser-Gates.

## Polish-Runde – Bewegung, Animation und Evakuierung

- Frameunabhängige Beschleunigung, Bremsung, Richtungswechsel, Luftkontrolle und geschützter Knockback sind bei 30/60/120 Hz geprüft.
- Walk und Sprint besitzen je acht diskrete Bein-/Stiefelphasen mit getrennten Timings; Takeoff, Jump-up, Fall, Land, Crouch und Hit sind eigene Zustände.
- Nahkampf und Flaschenwurf besitzen Windup-, Active/Release- und Recovery-Phasen; Schaden beziehungsweise Projektil entstehen nur in der vorgesehenen Phase.
- Der Freed-State deaktiviert Gegner-KI und Hitbox dauerhaft. Die Renderfolge ist strikt `crack → cloud → normal/look/exit/done → despawned`; kein Freed-Zustand erreicht wieder den Fluchrenderer.
- Mensch und Tier evakuieren mit unterschiedlichen Geschwindigkeiten, springen kleine Lücken, meiden große Schluchten und despawnen erst offscreen nach der Phase `done`.
- Drei Rückgaben an den UMSETZER waren erforderlich: Runtime-/Fuß-/Melee-/Evakuierungsintegration, visuelle Freed-Phasenfolge sowie das vom PRÜFER gefundene vorzeitige Offscreen-Despawn.
