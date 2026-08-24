from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any, Callable

from llm_provider import OpenAIProvider, ProviderError
from prompts import SPEZIALIST_SYSTEM_PROMPT


TASK = "Nenne drei Vorteile eines Multi-Agenten-Systems. Maximal 60 Wörter."
USER_INPUT = f"ARBEITSAUFTRAG:\n{TASK}"


def run_specialist_test(
    *,
    client: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    print("[SPEZIALIST-TEST] Start", flush=True)
    api_key = "mock-client" if client is not None else os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[SPEZIALIST-TEST] OPENAI_API_KEY fehlt in der Prozessumgebung", flush=True)
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
        result = provider.generate(
            "SPEZIALIST",
            SPEZIALIST_SYSTEM_PROMPT,
            USER_INPUT,
        )
    except KeyboardInterrupt:
        print("[SPEZIALIST-TEST] vom Benutzer abgebrochen", flush=True)
        return 130
    except ProviderError as exc:
        print(f"[SPEZIALIST-TEST] fehlgeschlagen: {exc}", flush=True)
        return 2

    print(f"[SPEZIALIST-TEST] Dauer: {clock() - started:.1f} s", flush=True)
    print("[SPEZIALIST-TEST] Status: completed", flush=True)
    print(f"[SPEZIALIST-TEST] Tokens: {result.usage.total_tokens}", flush=True)
    print(result.text, flush=True)
    return 0


def main() -> int:
    return run_specialist_test()


# Ausschließlich lokale Mock-Tests; pytest sammelt diese Datei wegen des Suffixes _test.py.
def test_exactly_one_specialist_request(capsys) -> None:
    captured: list[dict[str, Any]] = []

    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            output_text="1. Arbeitsteilung. 2. Spezialisierung. 3. Qualitätskontrolle.",
            status="completed",
            usage=SimpleNamespace(input_tokens=120, output_tokens=20, total_tokens=140),
        )

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    ticks = iter([1.0, 1.0, 2.0, 2.0])
    assert run_specialist_test(client=client, clock=lambda: next(ticks)) == 0
    assert len(captured) == 1
    request = captured[0]
    assert request["model"] == "gpt-5-mini"
    assert request["instructions"] == SPEZIALIST_SYSTEM_PROMPT
    assert request["input"] == USER_INPUT
    assert request["max_output_tokens"] == 1_000
    assert request["reasoning"] == {"effort": "minimal"}
    assert request["text"] == {"verbosity": "low"}
    assert request["store"] is False
    assert request["parallel_tool_calls"] is False
    assert request["timeout"].read == 30.0
    assert "tools" not in request
    output = capsys.readouterr().out
    assert "[API-METADATEN] rolle=SPEZIALIST" in output
    assert "system_zeichen=" in output and "user_zeichen=" in output
    assert TASK not in output


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
    assert run_specialist_test(client=client, clock=lambda: next(ticks)) == 2
    assert calls == 1
    output = capsys.readouterr().out
    assert "ohne Retry" in output
    assert "vor einmaligem Retry" not in output


if __name__ == "__main__":
    raise SystemExit(main())
