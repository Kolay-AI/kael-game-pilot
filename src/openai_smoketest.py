from __future__ import annotations

import os
import time
from types import SimpleNamespace
from typing import Any, Callable


MODEL = "gpt-5-mini"
PROMPT = "Antworte ausschließlich mit dem Wort OK."
TIMEOUT_SECONDS = 30.0


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _extract_text(response: Any) -> str:
    direct = _field(response, "output_text", "")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in _field(response, "output", []) or []:
        if _field(item, "type") != "message":
            continue
        for content in _field(item, "content", []) or []:
            if _field(content, "type") != "output_text":
                continue
            text = _field(content, "text", "")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def _usage_total(response: Any) -> int:
    usage = _field(response, "usage")
    total = _field(usage, "total_tokens")
    if total is not None:
        return int(total)
    return int(_field(usage, "input_tokens", 0) or 0) + int(
        _field(usage, "output_tokens", 0) or 0
    )


def _request_timeout(seconds: float = TIMEOUT_SECONDS):
    from httpx2 import Timeout

    return Timeout(
        seconds,
        connect=min(10.0, seconds),
        read=seconds,
        write=min(10.0, seconds),
        pool=min(5.0, seconds),
    )


def _create_client(timeout: Any):
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY ist in der Prozessumgebung nicht gesetzt.")
    return OpenAI(api_key=api_key, max_retries=0, timeout=timeout)


def run_smoke(
    *,
    client: Any | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Perform exactly one Responses request; injected clients are for offline tests only."""
    from openai import APIConnectionError, APITimeoutError

    print("[SMOKE] Start", flush=True)
    timeout = _request_timeout()
    try:
        active_client = client if client is not None else _create_client(timeout)
    except RuntimeError as exc:
        print(f"[SMOKE] Konfigurationsfehler: {exc}", flush=True)
        return 2

    started = clock()
    try:
        print("[SMOKE] unmittelbar vor responses.create()", flush=True)
        response = active_client.responses.create(
            model=MODEL,
            input=PROMPT,
            store=False,
            timeout=timeout,
        )
        print("[SMOKE] responses.create() zurückgekehrt", flush=True)
    except KeyboardInterrupt:
        print("[SMOKE] vom Benutzer abgebrochen", flush=True)
        return 130
    except APITimeoutError:
        print(f"[SMOKE] Timeout nach {clock() - started:.1f} s", flush=True)
        return 2
    except APIConnectionError:
        print(f"[SMOKE] Netzwerkfehler nach {clock() - started:.1f} s", flush=True)
        return 2
    except Exception as exc:
        print(f"[SMOKE] Fehlerklasse: {type(exc).__name__}", flush=True)
        return 2

    duration = clock() - started
    status = str(_field(response, "status", "unbekannt"))
    tokens = _usage_total(response)
    print(f"[SMOKE] Dauer: {duration:.1f} s", flush=True)
    print(f"[SMOKE] Status: {status}", flush=True)
    print(f"[SMOKE] Tokens: {tokens}", flush=True)

    if status != "completed":
        print("[SMOKE] Response nicht vollständig", flush=True)
        return 2
    text = _extract_text(response)
    if not text:
        print("[SMOKE] keine Textantwort", flush=True)
        return 2
    print(text, flush=True)
    return 0


def main() -> int:
    return run_smoke()


# Offline tests live here deliberately so this remains the only new file.
def _mock_client(create: Callable[..., Any]) -> Any:
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def test_successful_ok_response(capsys) -> None:
    captured: dict[str, Any] = {}

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            output_text="OK",
            status="completed",
            usage=SimpleNamespace(input_tokens=9, output_tokens=1, total_tokens=10),
        )

    ticks = iter([1.0, 1.25])
    assert run_smoke(client=_mock_client(create), clock=lambda: next(ticks)) == 0
    output = capsys.readouterr().out
    assert "[SMOKE] unmittelbar vor responses.create()" in output
    assert "[SMOKE] responses.create() zurückgekehrt" in output
    assert "[SMOKE] Dauer: 0.2 s" in output
    assert "[SMOKE] Status: completed" in output
    assert "[SMOKE] Tokens: 10" in output
    assert output.rstrip().endswith("OK")
    assert captured["model"] == "gpt-5-mini"
    assert captured["input"] == PROMPT
    assert captured["store"] is False
    assert captured["timeout"].read == 30.0
    assert "tools" not in captured


def test_timeout(capsys) -> None:
    from openai import APITimeoutError
    from httpx2 import Request

    def create(**kwargs):
        raise APITimeoutError(Request("POST", "https://example.invalid"))

    ticks = iter([2.0, 32.0])
    assert run_smoke(client=_mock_client(create), clock=lambda: next(ticks)) == 2
    assert "[SMOKE] Timeout nach 30.0 s" in capsys.readouterr().out


def test_empty_response(capsys) -> None:
    response = SimpleNamespace(output_text="", output=[], status="completed", usage=None)
    assert run_smoke(client=_mock_client(lambda **kwargs: response)) == 2
    assert "[SMOKE] keine Textantwort" in capsys.readouterr().out


def test_incomplete_response_does_not_print_partial_text(capsys) -> None:
    response = SimpleNamespace(
        output_text="NICHT AUSGEBEN", status="incomplete",
        usage=SimpleNamespace(input_tokens=5, output_tokens=4, total_tokens=9),
    )
    assert run_smoke(client=_mock_client(lambda **kwargs: response)) == 2
    output = capsys.readouterr().out
    assert "[SMOKE] Status: incomplete" in output
    assert "[SMOKE] Response nicht vollständig" in output
    assert "NICHT AUSGEBEN" not in output


def test_keyboard_interrupt(capsys) -> None:
    def create(**kwargs):
        raise KeyboardInterrupt

    assert run_smoke(client=_mock_client(create)) == 130
    assert "[SMOKE] vom Benutzer abgebrochen" in capsys.readouterr().out


def test_exception_message_is_not_exposed(capsys) -> None:
    marker = "sensibler-testmarker"

    def create(**kwargs):
        raise RuntimeError(marker)

    assert run_smoke(client=_mock_client(create)) == 2
    output = capsys.readouterr().out
    assert marker not in output
    assert "[SMOKE] Fehlerklasse: RuntimeError" in output


if __name__ == "__main__":
    raise SystemExit(main())
