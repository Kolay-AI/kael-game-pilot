# GAME PILOT 0.1 – ART UPGRADE STATUS

Stand: 2026-08-26 · Branch: `game-pilot`

## Abgeschlossen

- Kael an `assets/reference/kael_concept.png` angeglichen: Haarvolumen, Stirnband/Bandenden, Mittelstein, blaue Jacke, helle Kanten, Handschuhe, grüne Hose, Flaschengürtel und schwere Stiefel.
- Sichtbar detailreichere 16-Bit-Pixel-Art mit Material-Highlights, Nähten, Augenlichtern, Stiefelprofilen und animierten Bandenden.
- Kael-Bewegungs-, Angriffs- und Wurfposen mit 8-Frame-Walk/Sprint sowie stabilen Fuß- und Facing-Ankern.
- Detailliertere Farmer-, Tier-, Brute-, Boss- und Freed-Varianten.
- Detailliertere Parallax-Hintergründe, Terrain-Tiles, Pflanzen, Felsen, Büsche, Bäume, Seiten- und Checkpoint-Props.
- Aktiver Draw-Pfad nutzt den neuen Pixel-Art-Renderer; der alte Prototyp-Renderer ist nicht aktiv.
- Arko-Schaden zentral fail-closed geprüft: normale Gegner 15 Schaden/1,1 s Stun, Boss 8 Schaden/0,35 s Flinch; keine Wirkung auf ungültige oder befreite Ziele.
- TESTER abgeschlossen: 49/49 Spieltests bestanden, Syntaxchecks und Build bestanden.
- PRÜFER abgeschlossen: Art-Upgrade-Anforderungen erfüllt.

## Release-Hinweis

Der einzige verbleibende Vorbehalt ist der nicht automatisierbare manuelle Desktop-Browser-Playthrough. Alle deterministischen Spielregeln, der aktive Renderer und der statische Build sind geprüft.
