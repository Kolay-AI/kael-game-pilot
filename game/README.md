# KAEL – Game Pilot 0.1

Dependency-freier HTML5-Canvas-Vertical-Slice. Start: `python -m http.server 8080 -d game` und `http://localhost:8080`. Tests: `node --test game/tests/*.test.mjs`. Build: `node game/scripts/build.mjs`.

Der Korrekturstand besitzt testbare Gegneraktivierung, acht Kael-Posen mit vollständigem Links-/Rechts-Facing, symmetrische Nahkampf-/Wurfanker, eine wiederverwendbare Arko-Fähigkeit mit Drei-Sekunden-Cooldown sowie sichtbare Befreiungsphasen. Über `window.__KAEL_DEBUG__.state` steht im Browser eine schreibgeschützte Zustandsübersicht für manuelle QA bereit.

Alle Grafiken sind zur Laufzeit codegezeichnete originale Pixel-Platzhalter; es werden keine externen Assets verwendet.
