# LangGraph-Multi-Agenten-Prototyp

Drei-Agenten-Workflow mit austauschbarer Modellschicht. Standard ist der deterministische `FakeLLMProvider`: keine Cloud-Verbindung, kein Schlüssel und keine API-Kosten. Der OpenAI-Live-Modus verwendet das offizielle Python-SDK, die Responses API und `gpt-5-mini`; er startet nur mit zwei unabhängigen Freigaben.

## Ablauf

```text
BENUTZER -> CHEF -> SPEZIALIST -> PRÜFER
                         ^           |
                         +-----------+  bei Ablehnung

PRÜFER -> CHEF -> BENUTZER             bei Annahme
```

Der vollständige Live-Ablauf wurde mit zwei Prüfzyklen erfolgreich nachgewiesen:

```text
START -> CHEF -> SPEZIALIST -> PRÜFER
                              |
                              +-- ABGELEHNT -> SPEZIALIST -> PRÜFER
                                                              |
                                                              +-- AKZEPTIERT -> CHEF -> END
```

Dieser Pfad benötigt sechs logische Modellaufrufe. Der abschließende CHEF präsentiert nur
das geprüfte Ergebnis; er führt keine neue fachliche Prüfung durch.

CHEF, SPEZIALIST und PRÜFER verwenden getrennte System-Prompts aus `src/prompts.py` und ausschließlich die gemeinsame Provider-Schnittstelle aus `src/llm_provider.py`.

## Kostenloser Fake-Modus

```powershell
.\.venv\Scripts\python.exe -m pytest -q .\tests .\src\openai_smoketest.py .\src\openai_specialist_test.py .\src\openai_chef_test.py .\src\openai_pruefer_test.py .\src\openai_chain_test.py
.\.venv\Scripts\python.exe .\src\main.py
```

Der Fake-Modus bleibt Standard und benötigt `OPENAI_API_KEY` nicht.

## Konfiguration

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `MAS_PROVIDER` | `fake` | `fake` oder `openai` |
| `MAS_MODEL` | `gpt-5-mini` | Modell für den OpenAI-Modus |
| `MAS_MAX_REVIEW_CYCLES` | `2` | Prüfzyklen; im Live-Test hart auf höchstens `2` begrenzt |
| `MAS_HARD_MAX_MODEL_CALLS` | `6` | Harte Sicherheitsobergrenze für logische Modellaufrufe |
| `MAS_MAX_RESPONSE_CHARS` | `4000` | Antwortlänge; live höchstens `1200` Zeichen |
| `MAS_MAX_OUTPUT_TOKENS` | `1000` | API-Ausgabelimit; live höchstens `1000` Tokens |
| `MAS_LOGGING` | `true` | JSONL-Audit ein/aus |
| `MAS_REQUEST_TIMEOUT_SECONDS` | `30` | Read-Timeout je HTTP-Versuch in Sekunden |

## Expliziter OpenAI-Live-Test

Beim Start gibt das Programm vor jeder Provider-Erzeugung die tatsächlich geladenen
Dateipfade aus. Alle Start-, Agenten- und API-Diagnosen verwenden `flush=True`. Falls die
PowerShell- oder Host-Umgebung Ausgaben dennoch puffert, kann zusätzlich der unbuffered
Modus `python -u` verwendet werden; für die Programmlogik ist er nicht erforderlich.

Die fest eingebaute Aufgabe lautet:

```text
Nenne drei Vorteile eines regelmäßigen Projekt-Backups. Die Antwort soll genau drei nummerierte Punkte enthalten.
```

Vor dem später ausdrücklich freigegebenen Test müssen die Variablen nur in der aktuellen Prozessumgebung gesetzt werden:

```powershell
$env:OPENAI_API_KEY='<DEIN_API_KEY>'
$env:MAS_PROVIDER='openai'
$env:MAS_MODEL='gpt-5-mini'
.\.venv\Scripts\python.exe .\src\main.py --live-openai
```

Ohne `MAS_PROVIDER=openai` und ohne das zusätzliche Flag `--live-openai` startet keine Anfrage. Fehlt der Schlüssel, endet das Programm kontrolliert vor dem Clientaufruf. Schlüssel niemals in Quellcode, `.env`, JSON, README, Tests oder Logs speichern.

## Live-Schutzgrenzen

- maximal zwei Prüfzyklen und damit standardmäßig sechs erforderliche API-Aufrufe
- das erforderliche Laufzeitbudget wird zentral als `2N + 2` aus den Prüfzyklen berechnet
- ein zusätzlicher workflowweiter Zähler blockiert jede Überschreitung des berechneten Budgets
- die unabhängig konfigurierte harte Obergrenze darf vom benötigten Budget nicht überschritten werden
- `gpt-5-mini` nutzt für diesen kurzen Test `reasoning.effort=minimal`
- maximal ein aktiver Workflow im Prozess
- keine Parallelisierung
- keine Tools, kein Web- oder Dateizugriff durch Agenten
- höchstens ein Retry, nur bei Timeout oder Verbindungsfehler
- kein Retry bei Authentifizierungs-, Ratenlimit- oder sonstigen API-Statusfehlern
- ungültige Prüferantwort beendet den Workflow kontrolliert
- SDK-interne Retries sind deaktiviert
- HTTP-Timeouts bei Standardwert 30 s: Connect 10 s, Read 30 s, Write 10 s, Pool 5 s
- technische Statuszeilen nennen nur Rolle, Dauer, Tokens oder sichere Fehlerklasse
- derselbe Phasen-Timeout wird sowohl am Client als auch explizit an `responses.create(timeout=...)` gesetzt
- Agent-Eintritt/-Austritt und die Grenzen direkt vor/nach `responses.create()` werden sofort geflusht
- `Ctrl+C` beendet kontrolliert mit Exitcode 130 und ohne weitere Modellaufrufe

Ein eigener Retry bleibt Teil desselben logischen Modellaufrufs. Bei sechs logischen
Aufrufen sind daher theoretisch höchstens zwölf HTTP-Versuche möglich. Die Timeouts sind
Phasen-Timeouts des HTTP-Clients; der maßgebliche Wartefall ohne Antwort wird durch den
30-Sekunden-Read-Timeout begrenzt.

Für `N` Prüfzyklen gilt:

- Annahme spätestens in Runde `N`: `1 + 2N + 1 = 2N + 2` Modellaufrufe
- Ablehnung in allen `N` Runden: `1 + 2N` Modellaufrufe; der Abbruch-Node benötigt kein Modell

Bei den Standardwerten `N=2` und harter Obergrenze `6` sind benötigtes Budget und
Sicherheitsgrenze identisch. Eine Konfiguration mit drei Runden und Grenze sechs wird vor
Provider- oder Workflowstart kontrolliert abgelehnt:

```text
[KONFIGURATIONSFEHLER] Für 3 Prüfzyklen werden bis zu 8 Modellaufrufe benötigt,
die Sicherheitsobergrenze erlaubt jedoch nur 6.
```

Drei Runden sind auf Konfigurationsebene nur mit einer ausdrücklich auf mindestens acht
gesetzten Obergrenze zulässig. Der ausdrücklich freizugebende aktuelle Live-Test bleibt
zusätzlich auf höchstens zwei Runden begrenzt.

## Audit und Usage

JSONL-Ereignisse enthalten Workflow-ID, Sender, Empfänger, Durchlauf, Provider, Modell sowie Input-, Output- und Gesamttokens. Vollständige Agenten-Prompts werden nicht protokolliert. Verdächtige Schlüsselwerte werden zusätzlich redigiert.

Am Workflow-Ende werden API-Aufrufe und Tokenwerte summiert. Es sind keine Preise hart codiert und es wird keine Kostenschätzung ausgegeben.

Jeder echte Modellaufruf kann Cloud-Kosten verursachen. Tokenzahlen werden nach dem Lauf
angezeigt und im Audit protokolliert; Preise oder Kostenschätzungen werden bewusst nicht
im Quellcode gepflegt.

## Technische Bestandsaufnahme

- **CHEF:** delegiert den Benutzerauftrag und präsentiert ausschließlich akzeptierte Ergebnisse.
- **SPEZIALIST:** bearbeitet den Arbeitsauftrag und berücksichtigt bei Bedarf die aktuelle Prüferkritik.
- **PRÜFER:** vergleicht Ergebnis und Originalauftrag und liefert eine strukturierte Entscheidung.
- **State:** fachliche Text- und Statusfelder werden ersetzt; nur `events` und `usage` werden absichtlich akkumuliert.
- **Routing:** Annahme führt über den abschließenden CHEF zu `END`; Ablehnung führt bis zum Rundenlimit zurück zum SPEZIALISTEN.
- **Sicherheit:** Live-Freigabe in zwei Stufen, höchstens zwei Live-Prüfzyklen, zentral berechnetes Aufrufbudget, unabhängige harte Obergrenze, keine Tools, keine Parallelisierung und maximal ein eigener Netzwerk-Retry.
- **Audit:** JSONL mit Rollen, Übergängen, Runden, Modell und Tokenzahlen; keine vollständigen Prompts oder Schlüssel.
- **Tests:** deterministischer Fake-Workflow, echter kompilierter LangGraph mit zwei Routingszenarien sowie isolierte Providerdiagnosen ausschließlich mit Mocks.
- **Budgetvalidierung:** Unvereinbare Kombinationen aus Prüfzyklen und harter Modellaufrufgrenze werden vor dem Workflow abgelehnt.

## Diagnoseprogramme

| Datei | Einordnung | Zweck |
| --- | --- | --- |
| `src/openai_smoketest.py` | dauerhaft sinnvoll | Minimale Prüfung von SDK, Responses API, Modell, Netzwerk und Schlüsselkonfiguration |
| `src/openai_specialist_test.py` | temporäre Fehlersuche | Isoliert den Spezialisten; nach erfolgreichem Nachweis weitgehend durch Chain- und Workflowtests abgedeckt |
| `src/openai_chef_test.py` | temporäre Fehlersuche | Isoliert den CHEF; nach erfolgreichem Nachweis weitgehend durch Chain- und Workflowtests abgedeckt |
| `src/openai_pruefer_test.py` | dauerhaft sinnvoll | Prüft zusätzlich die strukturierte Prüferantwort über den echten Parserpfad |
| `src/openai_chain_test.py` | dauerhaft sinnvoll | Referenzkette ohne LangGraph zur Trennung von Provider-/Agenten- und Orchestrierungsfehlern |

Die temporären Dateien bleiben vorerst erhalten und werden in diesem Stabilisierungsschritt
nicht gelöscht.

## Sechs-Agenten-Integration

Der providerneutrale Sechs-Agenten-Pfad verwendet `CHEF_ROUTER`, die dynamisch
ausgewählten Fachrollen und einen deterministischen `CHEF_FINAL`. Ohne Live-Freigabe
läuft der Einstieg ausschließlich mit dem lokalen Fake-Client:

```powershell
.\.venv\Scripts\python.exe .\src\six_agent_main.py
```

Der echte End-to-End-Pfad benötigt gleichzeitig das Runtime-Gate, das explizite
CLI-Gate und einen ausschließlich über die Prozessumgebung injizierten API-Key:

```powershell
$env:MAS6_LIVE_ENABLED='true'
$env:OPENAI_API_KEY='<DEIN_API_KEY>'
.\.venv\Scripts\python.exe .\src\six_agent_main.py --live-six-agent --request '<AUFTRAG>'
```

Die Standardgrenze beträgt sechs Modellaufrufe, SDK-Retries sind deaktiviert und
Korrekturpfade sind im CLI-Einstieg nicht freigegeben. `CHEF_ROUTER` liefert ein
striktes Structured Output; anschließend validieren der bestehende Vertrag und das
RouteBudget fail-closed. Routen mit einem Bedarf über sechs werden unmittelbar nach
dem Router blockiert. Die Live-Zusammenfassung gibt weder Auftrag noch Modellantwort,
Prompts, Schlüssel, Request-IDs oder rohe Exceptions aus.

## Abhängigkeiten

- Python 3.12
- LangGraph 1.2.11
- pytest 9.1.1
- offizielles OpenAI-Python-SDK 3.3.1
