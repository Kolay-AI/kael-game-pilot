from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import socket
import sys

import httpx2
import openai
import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from six_agent_runtime import (  # noqa: E402
    DEFAULT_HARD_MAX_MODEL_CALLS, LiveGateResult, SixAgentClientCreationError,
    SixAgentRuntimeConfig, SixAgentRuntimeConfigError, build_client_timeout,
    create_openai_client, create_six_agent_bridge, create_six_agent_provider,
    load_nonsecret_runtime_config, parse_bool, parse_positive_float,
    parse_positive_int, validate_live_gate,
)


FAKE_KEY = "sk-test-runtime-secret"


class FakeClientFactory:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.call_count = 0
        self.max_retries = None
        self.timeout = None
        self.api_key_present = False
        self._failure = failure
        self.client = object()

    def __call__(self, **kwargs: object) -> object:
        self.call_count += 1
        self.max_retries = kwargs.get("max_retries")
        self.timeout = kwargs.get("timeout")
        self.api_key_present = bool(kwargs.get("api_key"))
        if self._failure:
            raise self._failure
        return self.client


@pytest.fixture(autouse=True)
def block_real_client_and_network(monkeypatch):
    def forbidden_client(*args, **kwargs):
        raise AssertionError("Echter OpenAI-Konstruktor ist in Runtime-Tests gesperrt")

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Netzwerk ist in Runtime-Tests gesperrt")

    monkeypatch.setattr(openai, "OpenAI", forbidden_client)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)


def test_runtime_defaults_are_safe_and_immutable() -> None:
    config = SixAgentRuntimeConfig()
    assert config == SixAgentRuntimeConfig(
        model="gpt-5-mini", max_output_tokens=1000,
        request_timeout_seconds=30.0, max_retries=0,
        provider_name="openai", live_enabled=False,
        hard_max_model_calls=DEFAULT_HARD_MAX_MODEL_CALLS,
    )
    assert config.hard_max_model_calls == 6
    with pytest.raises(FrozenInstanceError):
        config.model = "other"  # type: ignore[misc]


@pytest.mark.parametrize("value", ["gpt-5-mini", "gpt-5.1", "vendor:model_1"])
def test_valid_model_names(value: str) -> None:
    assert SixAgentRuntimeConfig(model=value).model == value


@pytest.mark.parametrize("value", ["", " ", " gpt-5-mini", "bad model", "x/../../key"])
def test_invalid_model_names_fail_closed(value: str) -> None:
    with pytest.raises(SixAgentRuntimeConfigError):
        SixAgentRuntimeConfig(model=value)


@pytest.mark.parametrize("field,value", [
    ("max_output_tokens", 0), ("max_output_tokens", -1),
    ("request_timeout_seconds", 0), ("request_timeout_seconds", -1),
    ("request_timeout_seconds", 0.9), ("request_timeout_seconds", 121),
    ("max_retries", -1), ("max_retries", 1),
    ("hard_max_model_calls", 0), ("hard_max_model_calls", -2),
    ("hard_max_model_calls", 101),
])
def test_invalid_limits_fail_closed(field: str, value: object) -> None:
    with pytest.raises(SixAgentRuntimeConfigError):
        SixAgentRuntimeConfig(**{field: value})


@pytest.mark.parametrize(("raw", "expected"), [
    ("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
    ("false", False), ("FALSE", False), ("0", False), ("no", False), ("off", False),
])
def test_bool_parser(raw: str, expected: bool) -> None:
    assert parse_bool(raw, "FLAG") is expected


@pytest.mark.parametrize("raw", ["", " ", "maybe", "2", "null"])
def test_invalid_bool_parser(raw: str) -> None:
    with pytest.raises(SixAgentRuntimeConfigError):
        parse_bool(raw, "FLAG")


def test_numeric_parsers() -> None:
    assert parse_positive_int("12", "INT") == 12
    assert parse_positive_float("2.5", "FLOAT") == 2.5
    for raw in ("", "0", "-1", "abc"):
        with pytest.raises(SixAgentRuntimeConfigError):
            parse_positive_int(raw, "INT")
        with pytest.raises(SixAgentRuntimeConfigError):
            parse_positive_float(raw, "FLOAT")


def test_nonsecret_loader_maps_only_named_nonsecret_values() -> None:
    config = load_nonsecret_runtime_config({
        "MAS6_MODEL": "gpt-5-mini",
        "MAS6_MAX_OUTPUT_TOKENS": "800",
        "MAS6_REQUEST_TIMEOUT_SECONDS": "25.5",
        "MAS6_MAX_RETRIES": "0",
        "MAS6_HARD_MAX_MODEL_CALLS": "9",
        "MAS6_LIVE_ENABLED": "true",
        "OPENAI_API_KEY": FAKE_KEY,
        "UNRELATED_SECRET": "secret-marker",
    })
    assert config == SixAgentRuntimeConfig(
        model="gpt-5-mini", max_output_tokens=800,
        request_timeout_seconds=25.5, max_retries=0,
        hard_max_model_calls=9, live_enabled=True,
    )
    assert FAKE_KEY not in repr(config)
    assert "secret-marker" not in repr(config)


@pytest.mark.parametrize(("name", "value"), [
    ("MAS6_MODEL", ""), ("MAS6_MAX_OUTPUT_TOKENS", "x"),
    ("MAS6_REQUEST_TIMEOUT_SECONDS", "999"), ("MAS6_MAX_RETRIES", "-1"),
    ("MAS6_MAX_RETRIES", "1"), ("MAS6_HARD_MAX_MODEL_CALLS", "0"),
    ("MAS6_LIVE_ENABLED", "maybe"),
])
def test_explicit_broken_environment_fails_closed(name: str, value: str) -> None:
    with pytest.raises(SixAgentRuntimeConfigError):
        load_nonsecret_runtime_config({name: value, "OPENAI_API_KEY": FAKE_KEY})


@pytest.mark.parametrize(("live", "key", "second", "allowed"), [
    (False, False, False, False), (False, True, False, False),
    (False, True, True, False), (True, True, False, False),
    (True, True, True, True),
])
def test_live_gate_matrix(live: bool, key: bool, second: bool, allowed: bool) -> None:
    result = validate_live_gate(
        live_enabled=live, api_key_present=key, second_gate_enabled=second,
    )
    assert result == LiveGateResult(live_allowed=allowed, offline_only=not allowed)


@pytest.mark.parametrize("second", [False, True])
def test_live_gate_rejects_enabled_without_key(second: bool) -> None:
    with pytest.raises(SixAgentRuntimeConfigError):
        validate_live_gate(live_enabled=True, api_key_present=False, second_gate_enabled=second)


def test_granular_client_timeout_values() -> None:
    timeout = build_client_timeout(SixAgentRuntimeConfig(request_timeout_seconds=30))
    assert isinstance(timeout, httpx2.Timeout)
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (10, 30, 30, 10)
    short = build_client_timeout(SixAgentRuntimeConfig(request_timeout_seconds=4))
    assert (short.connect, short.read, short.write, short.pool) == (4, 4, 4, 4)


def test_client_factory_receives_key_zero_retries_and_timeout_exactly_once() -> None:
    factory = FakeClientFactory()
    config = SixAgentRuntimeConfig(request_timeout_seconds=22)
    client = create_openai_client(FAKE_KEY, config, client_factory=factory)
    assert client is factory.client
    assert factory.call_count == 1
    assert factory.api_key_present is True
    assert factory.max_retries == 0
    assert (factory.timeout.connect, factory.timeout.read, factory.timeout.write,
            factory.timeout.pool) == (10, 22, 22, 10)
    assert FAKE_KEY not in repr(factory.__dict__)


def test_factory_exception_is_sanitized_and_does_not_chain_secret() -> None:
    factory = FakeClientFactory(failure=RuntimeError(FAKE_KEY))
    with pytest.raises(SixAgentClientCreationError) as caught:
        create_openai_client(FAKE_KEY, SixAgentRuntimeConfig(), client_factory=factory)
    assert factory.call_count == 1
    assert FAKE_KEY not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_bridge_factory_maps_config_and_preserves_injected_client() -> None:
    client = object()
    runtime = SixAgentRuntimeConfig(
        model="gpt-5-mini", max_output_tokens=876,
        request_timeout_seconds=19, hard_max_model_calls=8,
    )
    bridge = create_six_agent_bridge(client, runtime)
    assert bridge._client is client
    assert bridge.config.model == runtime.model
    assert bridge.config.max_output_tokens == runtime.max_output_tokens
    assert bridge.config.request_timeout_seconds == runtime.request_timeout_seconds
    assert not hasattr(bridge.config, "api_key")
    assert FAKE_KEY not in repr(bridge.config)


def test_provider_factory_requires_both_gates_before_client_creation() -> None:
    factory = FakeClientFactory()
    for live, second in ((False, False), (False, True), (True, False)):
        with pytest.raises(SixAgentRuntimeConfigError):
            create_six_agent_provider(
                api_key=FAKE_KEY,
                runtime_config=SixAgentRuntimeConfig(live_enabled=live),
                second_gate_enabled=second,
                client_factory=factory,
            )
    assert factory.call_count == 0


def test_provider_factory_creates_one_client_and_bridge_when_fully_gated() -> None:
    factory = FakeClientFactory()
    bridge = create_six_agent_provider(
        api_key=FAKE_KEY,
        runtime_config=SixAgentRuntimeConfig(live_enabled=True),
        second_gate_enabled=True,
        client_factory=factory,
    )
    assert factory.call_count == 1
    assert bridge._client is factory.client


def test_runtime_architecture_has_no_graph_state_routing_prompt_or_validator_imports() -> None:
    path = SRC_DIR / "six_agent_runtime.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden = (
        "langgraph", "six_agent_state", "graph", "six_agent_graph",
        "six_agent_integration_graph", "structured_routing", "prompts",
        "six_agent_contracts", "target_for_failure_origin",
        "SixAgentWorkflowState",
    )
    assert not any(marker in imported for imported in imports for marker in forbidden)
    assert all(marker not in source for marker in (
        "OPENAI_API_KEY", "target_for_failure_origin", "SixAgentWorkflowState",
    ))


def test_default_official_constructor_is_blocked_during_pytest() -> None:
    with pytest.raises(SixAgentClientCreationError):
        create_openai_client(FAKE_KEY, SixAgentRuntimeConfig())
