from __future__ import annotations

import ast
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import httpx2
import openai
import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import openai_chef_router_smoketest as smoke  # noqa: E402
from prompts import SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT  # noqa: E402
from six_agent_contracts import build_chef_router_input  # noqa: E402
from six_agent_openai_bridge import chef_router_text_config  # noqa: E402


FAKE_KEY = "sk-test-router-smoke-secret"
REQUEST = "Einfacher Auftrag mit MARKER-USER-REQUEST"
LIVE_ARGS = ["--live-chef-router-smoke", "--request", REQUEST]
LIVE_ENV = {"MAS6_LIVE_ENABLED": "true"}


def _route(*, full: bool = False, **extra: object) -> str:
    value: dict[str, object] = {
        "schema_version": 1, "planer": full, "analyst": full,
        "umsetzer": True, "tester": full, "pruefer": True,
        "complexity": "KOMPLEX" if full else "EINFACH",
        "reason_code": "VOLLSTAENDIGE_BEARBEITUNG" if full else "DIREKTE_UMSETZUNG",
    }
    value.update(extra)
    return json.dumps(value)


def _completed(text: str, *, response_id: str = "resp-secret-id") -> object:
    return SimpleNamespace(
        status="completed", output_text=text, output=[], id=response_id,
        usage=SimpleNamespace(input_tokens=11, output_tokens=13, total_tokens=24),
    )


class FakeResponses:
    def __init__(self, item: object) -> None:
        self.item = item
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if len(self.calls) > 1:
            raise AssertionError("Unerwarteter zweiter Request")
        if isinstance(self.item, BaseException):
            raise self.item
        return self.item


class FakeFactory:
    def __init__(self, item: object, *, failure: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.client = SimpleNamespace(responses=FakeResponses(item))
        self.failure = failure

    def __call__(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.failure:
            raise self.failure
        return self.client


@pytest.fixture(autouse=True)
def block_real_client_and_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Echter OpenAI-Client oder Netzwerkzugriff ist gesperrt")

    monkeypatch.setattr(openai, "OpenAI", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def _run(item: object, *, env=None, clock=None, secret_loader=None):
    factory = FakeFactory(item)
    ticks = iter([1.0, 1.5]) if clock is None else None
    code = smoke.run_router_smoke(
        LIVE_ARGS,
        environment=LIVE_ENV if env is None else env,
        secret_loader=(lambda: FAKE_KEY) if secret_loader is None else secret_loader,
        client_factory=factory,
        clock=(lambda: next(ticks)) if clock is None else clock,
    )
    return code, factory


@pytest.mark.parametrize(("argv", "environment", "expected"), [
    (["--request", REQUEST], LIVE_ENV, "Live-Gate fehlt"),
    (LIVE_ARGS, {}, "Runtime-Live-Gate fehlt"),
    (["--live-chef-router-smoke"], LIVE_ENV, "Benutzerauftrag fehlt"),
])
def test_nonsecret_gates_block_before_secret(argv, environment, expected, capsys) -> None:
    def forbidden_secret() -> str:
        raise AssertionError("Secret darf noch nicht gelesen werden")

    code = smoke.run_router_smoke(
        argv, environment=environment, secret_loader=forbidden_secret,
        client_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError("kein Client")),
    )
    assert code == smoke.EXIT_CLI_CONFIG_GATE
    assert expected in capsys.readouterr().out


def test_missing_key_blocks_before_client(capsys) -> None:
    factory = FakeFactory(_completed(_route()))

    def missing() -> str:
        raise smoke.RouterSmokeConfigurationError("secret detail")

    code = smoke.run_router_smoke(
        LIVE_ARGS, environment=LIVE_ENV, secret_loader=missing, client_factory=factory,
    )
    assert code == smoke.EXIT_CLI_CONFIG_GATE and factory.calls == []
    output = capsys.readouterr().out
    assert "API-Key fehlt" in output and "secret detail" not in output


def test_minimal_route_exact_request_mapping_usage_and_duration(capsys) -> None:
    code, factory = _run(_completed(_route()))
    assert code == smoke.EXIT_SUCCESS
    assert len(factory.calls) == 1
    assert factory.calls[0]["max_retries"] == 0
    assert factory.calls[0]["api_key"] == FAKE_KEY
    timeout = factory.calls[0]["timeout"]
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (10, 30, 30, 10)
    calls = factory.client.responses.calls
    assert len(calls) == 1
    request = calls[0]
    assert request == {
        "model": "gpt-5-mini",
        "instructions": SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT,
        "input": build_chef_router_input(REQUEST),
        "max_output_tokens": 1000,
        "reasoning": {"effort": "minimal"},
        "text": chef_router_text_config(),
        "store": False,
        "parallel_tool_calls": False,
        "timeout": 30.0,
    }
    output = capsys.readouterr().out
    for expected in (
        "Start", "Modell: gpt-5-mini", "Hard-Limit: 6",
        "unmittelbar vor CHEF_ROUTER Request", "Request zurückgekehrt",
        "ChefRoute validiert", "Required calls: 3", "Budget: OK",
        "input_tokens: 11", "output_tokens: 13", "total_tokens: 24",
        "Dauer: 0.5 s",
    ):
        assert expected in output


def test_full_route_is_valid_and_allowed_by_default_limit_six(capsys) -> None:
    code, factory = _run(_completed(_route(full=True)))
    output = capsys.readouterr().out
    assert code == smoke.EXIT_SUCCESS
    assert len(factory.client.responses.calls) == 1
    assert "ChefRoute validiert" in output
    assert "complexity: KOMPLEX" in output
    assert "Required calls: 6" in output and "Hard limit: 6" in output
    assert "Budget: OK" in output


def test_full_route_is_blocked_with_explicit_runtime_limit_five(capsys) -> None:
    code, factory = _run(
        _completed(_route(full=True)),
        env={"MAS6_LIVE_ENABLED": "true", "MAS6_HARD_MAX_MODEL_CALLS": "5"},
    )
    output = capsys.readouterr().out
    assert code == smoke.EXIT_BUDGET_BLOCK
    assert len(factory.client.responses.calls) == 1
    assert "ChefRoute validiert" in output
    assert "Required calls: 6" in output and "Hard limit: 5" in output
    assert "Budget: BLOCKIERT" in output


def test_full_route_succeeds_only_with_explicit_runtime_limit_six(capsys) -> None:
    code, _ = _run(
        _completed(_route(full=True)),
        env={"MAS6_LIVE_ENABLED": "true", "MAS6_HARD_MAX_MODEL_CALLS": "6"},
    )
    output = capsys.readouterr().out
    assert code == 0 and "Required calls: 6" in output and "Hard limit: 6" in output
    assert "Budget: OK" in output


@pytest.mark.parametrize("bad_output", [
    "kein json", "```json\n" + _route() + "\n```", _route(extra=True),
    _route(ziel_agent="CHEF_FINAL"), json.dumps({"schema_version": 1}),
    _route(schema_version=2), _route(umsetzer=False), _route(pruefer=False),
    _route(complexity="EXTREM"), _route(reason_code="FREI"),
])
def test_invalid_chef_route_is_rejected_without_raw_output(bad_output, capsys) -> None:
    code, factory = _run(_completed(bad_output))
    output = capsys.readouterr().out
    assert code == smoke.EXIT_API_RESPONSE_VALIDATION
    assert len(factory.client.responses.calls) == 1
    assert "InvalidResponse/ChefRoute" in output
    assert bad_output not in output


@pytest.mark.parametrize(("response", "kind"), [
    (SimpleNamespace(
        status="incomplete", output_text="PARTIAL-SECRET", output=[], id="resp-secret-id",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=SimpleNamespace(input_tokens=2, output_tokens=1000, total_tokens=1002),
    ), "IncompleteResponse"),
    (SimpleNamespace(status="failed", output_text="FAILED-SECRET", output=[], usage=None), "InvalidResponse"),
    (SimpleNamespace(status="completed", output_text="", output=[], usage=None), "InvalidResponse"),
])
def test_noncompleted_or_textless_response_fails_closed(response, kind, capsys) -> None:
    code, factory = _run(response)
    output = capsys.readouterr().out
    assert code == smoke.EXIT_API_RESPONSE_VALIDATION
    assert len(factory.client.responses.calls) == 1
    assert f"Fehlerklasse: {kind}" in output
    assert "PARTIAL-SECRET" not in output and "FAILED-SECRET" not in output
    assert "resp-secret-id" not in output
    if kind == "IncompleteResponse":
        assert "incomplete_reason=max_output_tokens" in output


def _sdk_errors():
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    response = httpx2.Response(429, request=request)
    return [
        (openai.APITimeoutError(request), "Timeout"),
        (openai.APIConnectionError(message="secret", request=request), "Connection"),
        (openai.AuthenticationError("secret", response=response, body=None), "Authentication"),
        (openai.RateLimitError("secret", response=response, body=None), "RateLimit"),
        (openai.APIStatusError("secret", response=response, body=None), "APIStatus"),
    ]


@pytest.mark.parametrize(("error", "kind"), _sdk_errors())
def test_sdk_errors_are_classified_sanitized_and_not_retried(error, kind, capsys) -> None:
    code, factory = _run(error)
    output = capsys.readouterr().out
    assert code == smoke.EXIT_API_RESPONSE_VALIDATION
    assert len(factory.client.responses.calls) == 1
    assert f"Fehlerklasse: {kind}" in output
    assert "secret" not in output.lower()


def test_api_status_prints_only_safe_diagnostic_fields(capsys) -> None:
    request = httpx2.Request(
        "POST", "https://example.invalid/v1/responses",
        headers={"Authorization": "Bearer AUTHORIZATION_SECRET"},
    )
    response = httpx2.Response(
        400, request=request,
        headers={"x-request-id": "REQUEST_ID_SECRET", "x-secret": "HEADER_SECRET"},
    )
    error = openai.BadRequestError(
        "RAW_EXCEPTION_SECRET", response=response,
        body={
            "code": "invalid_request_error",
            "type": "bad_request",
            "message": "RAW_BODY_SECRET",
        },
    )
    code, factory = _run(error)
    output = capsys.readouterr().out
    assert code == smoke.EXIT_API_RESPONSE_VALIDATION
    assert len(factory.client.responses.calls) == 1
    for expected in (
        "status_code=400", "api_error_class=BadRequest",
        "api_error_code=invalid_request_error", "api_error_type=bad_request",
    ):
        assert expected in output
    for forbidden in (
        "RAW_EXCEPTION_SECRET", "RAW_BODY_SECRET", "AUTHORIZATION_SECRET",
        "REQUEST_ID_SECRET", "HEADER_SECRET", REQUEST, FAKE_KEY,
    ):
        assert forbidden not in output


def test_keyboard_interrupt_is_exit_130_and_no_retry(capsys) -> None:
    code, factory = _run(KeyboardInterrupt())
    assert code == smoke.EXIT_INTERRUPTED
    assert len(factory.client.responses.calls) == 1
    assert "vom Benutzer abgebrochen" in capsys.readouterr().out


def test_client_factory_failure_is_sanitized(capsys) -> None:
    factory = FakeFactory(_completed(_route()), failure=RuntimeError(FAKE_KEY))
    code = smoke.run_router_smoke(
        LIVE_ARGS, environment=LIVE_ENV, secret_loader=lambda: FAKE_KEY,
        client_factory=factory,
    )
    output = capsys.readouterr().out
    assert code == smoke.EXIT_CLI_CONFIG_GATE and len(factory.calls) == 1
    assert "Client-Erzeugung fehlgeschlagen" in output and FAKE_KEY not in output


def test_no_sensitive_content_is_printed_on_success(capsys) -> None:
    raw = _route()
    code, _ = _run(_completed(raw, response_id="RESP-ID-SECRET"))
    output = capsys.readouterr().out
    assert code == 0
    for forbidden in (
        FAKE_KEY, REQUEST, raw, "RESP-ID-SECRET",
        SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT,
    ):
        assert forbidden not in output


def test_module_imports_no_graph_or_langgraph() -> None:
    source = (SRC_DIR / "openai_chef_router_smoketest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {"graph", "six_agent_graph", "six_agent_integration_graph", "langgraph"}
    assert imports.isdisjoint(forbidden)
    assert "run_six_agent_integration_workflow" not in source
