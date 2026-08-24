from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any, Callable

from llm_provider import OpenAIProvider, ProviderError
from prompts import CHEF_SYSTEM_PROMPT


TASK = (
    "Nenne drei Vorteile regelmäßiger Projekt-Backups. Formuliere daraus einen kurzen, "
    "klaren Arbeitsauftrag für einen Spezialisten."
)


def run_chef_test(
    *,
    client: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    print("[CHEF-TEST] Start", flush=True)
    api_key = "mock-client" if client is not None else os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[CHEF-TEST] OPENAI_API_KEY fehlt in der Prozessumgebung", flush=True)
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
        result = provider.generate("CHEF", CHEF_SYSTEM_PROMPT, TASK)
    except KeyboardInterrupt:
        print("[CHEF-TEST] vom Benutzer abgebrochen", flush=True)
        return 130
    except ProviderError as exc:
        print(f"[CHEF-TEST] fehlgeschlagen: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"[CHEF-TEST] Fehlerklasse: {type(exc).__name__}", flush=True)
        return 2

    print(f"[CHEF-TEST] Dauer: {clock() - started:.1f} s", flush=True)
    print("[CHEF-TEST] Status: completed", flush=True)
    print(f"[CHEF-TEST] Tokens: {result.usage.total_tokens}", flush=True)
    print(f"[CHEF-TEST] Antwortlänge: {len(result.text)} Zeichen", flush=True)
    print(result.text, flush=True)
    return 0


def main() -> int:
    return run_chef_test()


# Nur lokale Mocks; pytest sammelt diese isolierte Datei über den Suffix _test.py.
def test_successful_chef_call_is_exactly_one_request(capsys) -> None:
    captured: list[dict[str, Any]] = []
    answer = "Formuliere drei kurze Vorteile regelmäßiger Projekt-Backups."

    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            output_text=answer,
            status="completed",
            usage=SimpleNamespace(input_tokens=130, output_tokens=15, total_tokens=145),
        )

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    ticks = iter([1.0, 1.0, 2.0, 2.0])
    assert run_chef_test(client=client, clock=lambda: next(ticks)) == 0
    assert len(captured) == 1
    request = captured[0]
    assert request["model"] == "gpt-5-mini"
    assert request["instructions"] == CHEF_SYSTEM_PROMPT
    assert request["input"] == TASK
    assert request["max_output_tokens"] == 1_000
    assert request["reasoning"] == {"effort": "minimal"}
    assert request["text"] == {"verbosity": "low"}
    assert request["store"] is False
    assert request["parallel_tool_calls"] is False
    assert request["timeout"].read == 30.0
    assert "tools" not in request
    output = capsys.readouterr().out
    assert "[CHEF-TEST] Start" in output
    assert "[API-METADATEN] rolle=CHEF" in output
    assert "[API] CHEF unmittelbar vor responses.create()" in output
    assert "[API] CHEF unmittelbar nach responses.create()" in output
    assert "[CHEF-TEST] Status: completed" in output
    assert f"[CHEF-TEST] Antwortlänge: {len(answer)} Zeichen" in output


def test_timeout_has_no_retry(capsys) -> None:
    from openai import APITimeoutError
    from httpx2 import Request

    calls = 0

    def create(**kwargs):
        nonlocal calls
        calls += 1
        raise APITimeoutError(Request("POST", "https://example.invalid"))

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    ticks = iter([1.0, 1.0, 31.0])
    assert run_chef_test(client=client, clock=lambda: next(ticks)) == 2
    assert calls == 1
    output = capsys.readouterr().out
    assert "ohne Retry" in output
    assert "vor einmaligem Retry" not in output


def test_empty_answer_is_controlled(capsys) -> None:
    response = SimpleNamespace(output_text="", output=[], status="completed", usage=None)
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    assert run_chef_test(client=client) == 2
    assert "LeereResponse" in capsys.readouterr().out


def test_incomplete_response_does_not_expose_partial_text(capsys) -> None:
    partial = "VERTRAULICHER TEILTEXT"
    response = SimpleNamespace(
        output_text=partial,
        output=[],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        error=None,
        usage=SimpleNamespace(input_tokens=20, output_tokens=1_000, total_tokens=1_020),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    assert run_chef_test(client=client) == 2
    output = capsys.readouterr().out
    assert "UnvollstaendigeResponse" in output
    assert partial not in output


def test_unexpected_exception_does_not_expose_secret(capsys) -> None:
    secret_marker = "sensibler-geheimwert"

    def create(**kwargs):
        raise RuntimeError(secret_marker)

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert run_chef_test(client=client) == 2
    output = capsys.readouterr().out
    assert secret_marker not in output
    assert "[CHEF-TEST] Fehlerklasse: RuntimeError" in output


def test_keyboard_interrupt_is_controlled(capsys) -> None:
    def create(**kwargs):
        raise KeyboardInterrupt

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    assert run_chef_test(client=client) == 130
    assert "[CHEF-TEST] vom Benutzer abgebrochen" in capsys.readouterr().out


if __name__ == "__main__":
    raise SystemExit(main())
