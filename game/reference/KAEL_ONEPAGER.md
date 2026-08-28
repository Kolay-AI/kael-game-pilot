# Kael – Welt, Figuren, Ton (Pilot 0.1)

Bestehender Action-Platformer, kein Neustart. Branch `game-pilot`.
Sprache im Spiel: Deutsch. Ton: helles SNES-Abenteuer, nicht zynisches Erwachsenen-Gag-Game.

## Was der Pilot schon beweist

Kael tötet nicht. Verfluchte tragen eine Hülle (Bauer, Tier, Brute, Boss). Trifft die Hülle zu Boden, reißt sie, eine grüne Wolke steigt, darunter steht ein Mensch oder Tier, sagt **Danke!** (Boss: **Frei!**), sieht hin, geht. Abschlusszeile: *Die Fluchhülle ist gebrochen.*

Drei gestohlene **Buchseiten** liegen auf dem Weg. Sind sie vereint: **Frost-Meisterschaft**, Flaschenkapazität 4→5. Flaschen am Gürtel: Frost, Glut, Verwirrung. **Arko** stürzt auf Kommando, drei Sekunden Pause, dann wieder bereit.

Das ist die Geschichte, die das Gameplay schon erzählt. Text muss das tragen, nicht kontern.

## Figuren

**Kael.** Jugendlicher Abenteurer, wildes braunes Haar, gelbes Stirnband mit Stein, blaue Jacke, große Handschuhe, Flaschengürtel, schwere Stiefel. Verbindlich: `assets/reference/kael_concept.png` + `KAEL_DESIGN.md`. Stimme: mutig, ein bisschen überfordert, spricht mit Arko, hat Hunger und Lampenfieber. Kein gekündigter Erwachsener.

**Arko.** Adler, Partner, nicht gagiges Haustier. Kael schickt ihn vor, beschwert sich bei ihm, verlässt sich auf ihn.

**Die Verfluchten.** Keine Monster zum Abschlachten. Leute und Tiere unter einer Hülle. Befreiung ist die Belohnung, nicht der Kill.

**Der Berg der Verdammten.** Nur in Orions Story-Kern benannt, nicht in den Repo-Docs. Passt zum Fluch und zur Hülle. Für den Pilot reicht: ein verfluchter Hang, den Kael hoch muss, weil das Buch hier nicht hingehört.

## Ton

Hell, lesbar, hoffnungsvoll trotz Fluch. Humor ja: kindlicher Trotz, Selbstironie, Zwiegespräch mit Arko. Humor nein: Döner, Lotto, WLAN, Kündigung, „Such dir Arbeit, Penner“, Büro-Sarkasmus.

UI bleibt deutsch (`ENERGIE`, `SEITEN`, `ARKO BEREIT`). Idle-Blasen dieselbe Sprache, kurz, sprechbar.

## Lücken (nicht still füllen)

Im Repo steht keine Herkunft des Buchs, kein Dieb, kein Fluchgeber, kein Name für den Berg außer Orions Brief. Das gehört in einen zweiten Story-Pass, nicht in Idle-Gags.

## Idle-Lines, Befund

`game/data/kael_idle_lines.json`: gültiges JSON, aber **doppelt kodiertes UTF-8 über cp1252** (`Döner` → `DÃ¶ner`-Bytes). 61 Zeilen, 47 davon Sarkasmus, plus Food/Döner und 10 Lotto. Dieselbe Stimme liegt hart in `game/game.mjs` (`IDLE_SPEECH_LINES`, Döner-Spezialblase). JSON allein tauschen reicht nicht.

Vorschlag: `kael_idle_lines.proposed.json` (gleiche IDs/Animationen, neuer Text, UTF-8). Nicht committed. Codex merged, wenn Orion übernimmt.
