from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any, Callable

from agents import _parse_review
from llm_provider import OpenAIProvider, ProviderError, ProviderResponseError
from prompts import PRUEFER_SYSTEM_PROMPT


ORIGINAL_TASK = (
    "Nenne drei Vorteile regelmäßiger Projekt-Backups. "
    "Die Antwort soll genau drei nummerierte Punkte enthalten."
)
SPECIALIST_ANSWER = (
    "1. Schutz vor Datenverlust.\n"
    "2. Schnellere Wiederherstellung nach Fehlern.\n"
    "3. Bessere Absicherung gegen versehentliche Änderungen."
)
USER_INPUT = (
    f"AUFTRAG:\n{ORIGINAL_TASK}\n\nERGEBNIS:\n{SPECIALIST_ANSWER}\n\n"
    "Prüfe strikt gegen den ursprünglichen Auftrag und antworte im geforderten JSON-Schema."
)


def run_pruefer_test(
    *,
    client: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    print("[PRÜFER-TEST] Start", flush=True)
    api_key = "mock-client" if client is not None else os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[PRÜFER-TEST] OPENAI_API_KEY fehlt in der Prozessumgebung", flush=True)
        return 2

    provider = OpenAIProvider(
        model="gpt-5-mini",
        api_key=api_key,
        max_response_chars=1_200,
        max_output_tokens=1_000,
        timeout_seconds=30.0,
        client=client,
        clock=clock,
        max_attempts=1,
    )
    started = clock()
    try:
        result = provider.generate("PRÜFER", PRUEFER_SYSTEM_PROMPT, USER_INPUT)
    except KeyboardInterrupt:
        print("[PRÜFER-TEST] vom Benutzer abgebrochen", flush=True)
        return 130
    except ProviderError as exc:
        print(f"[PRÜFER-TEST] fehlgeschlagen: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"[PRÜFER-TEST] Fehlerklasse: {type(exc).__name__}", flush=True)
        return 2

    print(f"[PRÜFER-TEST] Dauer: {clock() - started:.1f} s", flush=True)
    print("[PRÜFER-TEST] Status: completed", flush=True)
    print(f"[PRÜFER-TEST] Tokens: {result.usage.total_tokens}", flush=True)
    print(f"[PRÜFER-TEST] Antwortlänge: {len(result.text)} Zeichen", flush=True)

    try:
        decision, reason, improvements = _parse_review(result.text)
    except ProviderResponseError as exc:
        print(f"[PRÜFER-TEST] Parserfehler: {exc}", flush=True)
        return 2

    print(f"[PRÜFER-TEST] Entscheidung: {decision}", flush=True)
    print(f"[PRÜFER-TEST] Begründungslänge: {len(reason)} Zeichen", flush=True)
    print(f"[PRÜFER-TEST] Verbesserungen: {len(improvements)}", flush=True)
    print(result.text, flush=True)
    return 0 if decision == "AKZEPTIERT" else 1


def main() -> int:
    return run_pruefer_test()


def _response(text: str, *, status: str = "completed") -> Any:
    return SimpleNamespace(
        output_text=text,
        output=[],
        status=status,
        incomplete_details=SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None,
        error=None,
        usage=SimpleNamespace(input_tokens=150, output_tokens=30, total_tokens=180),
    )


def _client(create: Callable[..., Any]) -> Any:
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def test_successful_accepted_response_uses_main_parser(capsys) -> None:
    import json

    captured: list[dict[str, Any]] = []
    payload = json.dumps({
        "entscheidung": "AKZEPTIERT",
        "begruendung": "Drei nummerierte Vorteile sind vorhanden.",
        "verbesserungen": [],
    })

    def create(**kwargs):
        captured.append(kwargs)
        return _response(payload)

    ticks = iter([1.0, 1.0, 2.0, 2.0])
    assert run_pruefer_test(client=_client(create), clock=lambda: next(ticks)) == 0
    assert len(captured) == 1
    request = captured[0]
    assert request["model"] == "gpt-5-mini"
    assert request["instructions"] == PRUEFER_SYSTEM_PROMPT
    assert request["input"] == USER_INPUT
    assert request["max_output_tokens"] == 1_000
    assert request["reasoning"] == {"effort": "minimal"}
    assert request["text"] == {"verbosity": "low"}
    assert request["store"] is False
    assert request["parallel_tool_calls"] is False
    assert request["timeout"].read == 30.0
    assert "tools" not in request
    output = capsys.readouterr().out
    assert "[API-METADATEN] rolle=PRÜFER" in output
    assert "[API] PRÜFER unmittelbar vor responses.create()" in output
    assert "[API] PRÜFER unmittelbar nach responses.create()" in output
    assert "[PRÜFER-TEST] Entscheidung: AKZEPTIERT" in output
    assert "[PRÜFER-TEST] Verbesserungen: 0" in output


def test_rejected_response_is_parsed(capsys) -> None:
    import json

    payload = json.dumps({
        "entscheidung": "ABGELEHNT",
        "begruendung": "Ein Punkt fehlt.",
        "verbesserungen": ["Dritten Punkt ergänzen"],
    })
    assert run_pruefer_test(client=_client(lambda **kwargs: _response(payload))) == 1
    output = capsys.readouterr().out
    assert "Entscheidung: ABGELEHNT" in output
    assert "Verbesserungen: 1" in output


def test_invalid_json_is_controlled(capsys) -> None:
    assert run_pruefer_test(client=_client(lambda **kwargs: _response("kein JSON"))) == 2
    assert "[PRÜFER-TEST] Parserfehler: Die Prüferantwort war kein gültiges JSON." in capsys.readouterr().out


def test_timeout_has_no_retry(capsys) -> None:
    from openai import APITimeoutError
    from httpx2 import Request

    calls = 0

    def create(**kwargs):
        nonlocal calls
        calls += 1
        raise APITimeoutError(Request("POST", "https://example.invalid"))

    ticks = iter([1.0, 1.0, 31.0])
    assert run_pruefer_test(client=_client(create), clock=lambda: next(ticks)) == 2
    assert calls == 1
    output = capsys.readouterr().out
    assert "ohne Retry" in output
    assert "vor einmaligem Retry" not in output


def test_incomplete_response_is_controlled(capsys) -> None:
    assert run_pruefer_test(client=_client(lambda **kwargs: _response("Teiltext", status="incomplete"))) == 2
    output = capsys.readouterr().out
    assert "UnvollstaendigeResponse" in output
    assert "Teiltext" not in output


def test_unexpected_exception_does_not_expose_secret(capsys) -> None:
    marker = "sensibler-geheimwert"

    def create(**kwargs):
        raise RuntimeError(marker)

    assert run_pruefer_test(client=_client(create)) == 2
    output = capsys.readouterr().out
    assert marker not in output
    assert "[PRÜFER-TEST] Fehlerklasse: RuntimeError" in output


def test_keyboard_interrupt_is_controlled(capsys) -> None:
    def create(**kwargs):
        raise KeyboardInterrupt

    assert run_pruefer_test(client=_client(create)) == 130
    assert "[PRÜFER-TEST] vom Benutzer abgebrochen" in capsys.readouterr().out


if __name__ == "__main__":
    raise SystemExit(main())
