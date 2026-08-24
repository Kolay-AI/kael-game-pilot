from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from agents import _parse_review
from llm_provider import OpenAIProvider, ProviderError, ProviderResponseError
from prompts import CHEF_SYSTEM_PROMPT, PRUEFER_SYSTEM_PROMPT, SPEZIALIST_SYSTEM_PROMPT


ORIGINAL_TASK = (
    "Nenne drei konkrete Vorteile regelmäßiger Projekt-Backups und liefere eine kurze, "
    "sachlich korrekte Antwort."
)


def run_chain_test(
    *,
    client: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    print("[CHAIN] Start", flush=True)
    api_key = "mock-client" if client is not None else os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[CHAIN] OPENAI_API_KEY fehlt in der Prozessumgebung", flush=True)
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
    results = []
    try:
        print("[CHAIN] Schritt 1/3 CHEF", flush=True)
        chef_result = provider.generate("CHEF", CHEF_SYSTEM_PROMPT, ORIGINAL_TASK)
        results.append(chef_result)
        print(f"[CHAIN] CHEF -> SPEZIALIST; zeichen={len(chef_result.text)}", flush=True)

        specialist_input = f"ARBEITSAUFTRAG:\n{chef_result.text}"
        print("[CHAIN] Schritt 2/3 SPEZIALIST", flush=True)
        specialist_result = provider.generate(
            "SPEZIALIST", SPEZIALIST_SYSTEM_PROMPT, specialist_input
        )
        results.append(specialist_result)
        print(
            f"[CHAIN] SPEZIALIST -> PRÜFER; antwort_zeichen={len(specialist_result.text)}",
            flush=True,
        )

        reviewer_input = (
            f"AUFTRAG:\n{ORIGINAL_TASK}\n\nERGEBNIS:\n{specialist_result.text}\n\n"
            "Prüfe strikt gegen den ursprünglichen Auftrag und antworte im geforderten JSON-Schema."
        )
        print("[CHAIN] Schritt 3/3 PRÜFER", flush=True)
        reviewer_result = provider.generate("PRÜFER", PRUEFER_SYSTEM_PROMPT, reviewer_input)
        results.append(reviewer_result)
        decision, _reason, _improvements = _parse_review(reviewer_result.text)
    except KeyboardInterrupt:
        print("[CHAIN] vom Benutzer abgebrochen", flush=True)
        return 130
    except ProviderResponseError as exc:
        print(f"[CHAIN] Prüfer-/Responsefehler: {exc}", flush=True)
        return 2
    except ProviderError as exc:
        print(f"[CHAIN] Providerfehler: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"[CHAIN] Fehlerklasse: {type(exc).__name__}", flush=True)
        return 2

    total_tokens = sum(item.usage.total_tokens for item in results)
    print(f"[CHAIN] Entscheidung: {decision}", flush=True)
    print(f"[CHAIN] Gesamtdauer: {clock() - started:.1f} s", flush=True)
    print(f"[CHAIN] API-Aufrufe: {len(results)}", flush=True)
    print(f"[CHAIN] Gesamt-Tokens: {total_tokens}", flush=True)
    print("[CHAIN] Fertig", flush=True)
    print(specialist_result.text, flush=True)
    return 0 if decision == "AKZEPTIERT" else 1


def main() -> int:
    return run_chain_test()


def _response(text: str, *, status: str = "completed", tokens: int = 10) -> Any:
    return SimpleNamespace(
        output_text=text,
        output=[],
        status=status,
        incomplete_details=SimpleNamespace(reason="max_output_tokens") if status == "incomplete" else None,
        error=None,
        usage=SimpleNamespace(input_tokens=tokens - 2, output_tokens=2, total_tokens=tokens),
    )


class _SequentialResponses:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes[len(self.calls) - 1]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _client(outcomes: list[Any]) -> tuple[Any, _SequentialResponses]:
    responses = _SequentialResponses(outcomes)
    return SimpleNamespace(responses=responses), responses


def _accepted_json() -> str:
    import json

    return json.dumps({
        "entscheidung": "AKZEPTIERT",
        "begruendung": "Drei konkrete Vorteile sind vorhanden.",
        "verbesserungen": [],
    })


def test_successful_chain_has_exactly_three_calls_and_real_handoffs(capsys) -> None:
    chef_text = "Nenne genau drei konkrete Vorteile regelmäßiger Projekt-Backups."
    specialist_text = (
        "1. Schutz vor Datenverlust.\n"
        "2. Schnellere Wiederherstellung.\n"
        "3. Nachvollziehbare Versionsstände."
    )
    client, responses = _client([
        _response(chef_text, tokens=11),
        _response(specialist_text, tokens=12),
        _response(_accepted_json(), tokens=13),
    ])
    assert run_chain_test(client=client) == 0
    assert len(responses.calls) == 3
    assert responses.calls[0]["input"] == ORIGINAL_TASK
    assert responses.calls[1]["input"] == f"ARBEITSAUFTRAG:\n{chef_text}"
    assert ORIGINAL_TASK in responses.calls[2]["input"]
    assert specialist_text in responses.calls[2]["input"]
    assert [call["instructions"] for call in responses.calls] == [
        CHEF_SYSTEM_PROMPT, SPEZIALIST_SYSTEM_PROMPT, PRUEFER_SYSTEM_PROMPT
    ]
    assert all(call["model"] == "gpt-5-mini" for call in responses.calls)
    assert all(call["max_output_tokens"] == 1_000 for call in responses.calls)
    assert all(call["reasoning"] == {"effort": "minimal"} for call in responses.calls)
    assert all(call["text"] == {"verbosity": "low"} for call in responses.calls)
    assert all(call["store"] is False for call in responses.calls)
    assert all(call["parallel_tool_calls"] is False for call in responses.calls)
    assert all(call["timeout"].read == 30.0 for call in responses.calls)
    assert all("tools" not in call for call in responses.calls)
    output = capsys.readouterr().out
    assert "[CHAIN] Entscheidung: AKZEPTIERT" in output
    assert "[CHAIN] API-Aufrufe: 3" in output
    assert "[CHAIN] Gesamt-Tokens: 36" in output
    assert output.rstrip().endswith(specialist_text)


def test_existing_parse_review_path_is_called(monkeypatch) -> None:
    original_parser = _parse_review
    calls = 0

    def recording_parser(text: str):
        nonlocal calls
        calls += 1
        return original_parser(text)

    monkeypatch.setitem(run_chain_test.__globals__, "_parse_review", recording_parser)
    client, _ = _client([_response("Auftrag"), _response("Ergebnis"), _response(_accepted_json())])
    assert run_chain_test(client=client) == 0
    assert calls == 1


def test_chef_failure_stops_before_specialist() -> None:
    client, responses = _client([_response("Teil", status="incomplete")])
    assert run_chain_test(client=client) == 2
    assert len(responses.calls) == 1


def test_specialist_failure_stops_before_reviewer() -> None:
    client, responses = _client([_response("Auftrag"), _response("Teil", status="incomplete")])
    assert run_chain_test(client=client) == 2
    assert len(responses.calls) == 2


def test_reviewer_error_is_controlled_after_three_calls(capsys) -> None:
    client, responses = _client([_response("Auftrag"), _response("Ergebnis"), _response("kein JSON")])
    assert run_chain_test(client=client) == 2
    assert len(responses.calls) == 3
    assert "Prüferantwort war kein gültiges JSON" in capsys.readouterr().out


def test_timeout_stops_without_retry() -> None:
    from openai import APITimeoutError
    from httpx2 import Request

    client, responses = _client([APITimeoutError(Request("POST", "https://example.invalid"))])
    assert run_chain_test(client=client) == 2
    assert len(responses.calls) == 1


def test_secret_is_not_logged(capsys) -> None:
    marker = "sensibler-geheimwert"
    client, responses = _client([RuntimeError(marker)])
    assert run_chain_test(client=client) == 2
    assert len(responses.calls) == 1
    output = capsys.readouterr().out
    assert marker not in output
    assert "[CHAIN] Fehlerklasse: RuntimeError" in output


def test_chain_source_does_not_use_graph_framework() -> None:
    import ast

    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = "lang" + "graph"
    assert forbidden not in imported
    assert "graph" not in imported


if __name__ == "__main__":
    raise SystemExit(main())
