# GAME PILOT 0.1 – Design und Technik

Der Pilot ist ein dependency-freier horizontaler HTML5-Canvas-Action-Platformer unter `game/`. Der bestehende Python-/LangGraph-Workflow unter `src/` wurde nicht verändert.

## Umfang

- Kael: Laufen, Sprinten, Springen, Ducken, Nahkampf, Schaden, Rückstoß und 100 Energie.
- Arko: sichtbare Begleitbewegung und Sturzflug mit Betäubung.
- Flaschen: Frost, Glut und Verwirrung mit begrenztem Vorrat und getrennten Wirkungen.
- Inhalte: Heilpflanzen, Flaschenressource, drei normale Gegnertypen, Mini-Boss, drei Buchseiten, Freischaltungssequenz, Checkpoint und Respawn.
- Befreiung: sichtbare Hüllenrisse/Splitter, grüne Fluchwolke, normale Form, Blickpause und Abgang; Menschen zeigen `Danke!`.
- Progression: Seite drei erhöht die maximale Kapazität aller Flaschen von vier auf fünf und füllt jeden Typ einmalig um eine Einheit auf.
- Abschluss: Der Mini-Boss durchläuft Hülle, Normalform und Abgang, bevor `LEVEL COMPLETE` erscheint.

## Architektur

- `game/game.mjs`: Canvas-Loop, Eingabe, Level, Entitäten und Darstellung.
- `game/rules.mjs`: DOM-freie, deterministisch testbare Spielregeln.
- `game/tests/`: Node-Regeltests.
- `game/scripts/build.mjs`: reproduzierbarer statischer Build nach `game/dist/`.

Alle sichtbaren Platzhalter werden zur Laufzeit mit Canvas-Primitiven gezeichnet. Es werden keine externen oder geschützten Spielassets verwendet.

Die Korrekturrunde ersetzt Kaels einfachen Block-Platzhalter durch eine codegezeichnete, vollständig spiegelbare Pixel-Art-Figur. Gegner, Pflanzen, Terrain, Hintergrund, HUD, Arko und Befreiungseffekte wurden ebenfalls innerhalb des bestehenden Canvas-Systems überarbeitet.

## Verbindliches Kael-Design

Das endgültige Grunddesign ist durch `assets/reference/kael_concept.png` und `assets/reference/KAEL_DESIGN.md` festgelegt. Der aktuelle codegezeichnete Pilot-Platzhalter bleibt vorerst erhalten; spätere Art-, Sprite- und Animationsarbeiten müssen vor Beginn beide Referenzen berücksichtigen.
