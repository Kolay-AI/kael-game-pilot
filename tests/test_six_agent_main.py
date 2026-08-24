from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import sys
from typing import Iterator, Mapping

import openai
import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import six_agent_main as cli  # noqa: E402
from six_agent_bridge_fake_client import FakeOpenAIClient, completed_response  # noqa: E402
from six_agent_runtime import SixAgentRuntimeConfig  # noqa: E402
from six_agent_state import ModelRole  # noqa: E402


SECRET_NAME = "OPENAI" + "_API_KEY"
FAKE_SECRET = "sk-test-six-agent-cli-secret"


class GuardedEnvironment(Mapping[str, str]):
    def __init__(self, values: dict[str, str] | None = None, *, allow_secret: bool = False) -> None:
        self.values = dict(values or {})
        self.requested: list[str] = []
        self.allow_secret = allow_secret

    def __getitem__(self, key: str) -> str:
        self.requested.append(key)
        if key == SECRET_NAME and not self.allow_secret:
            raise AssertionError("Secret-Zugriff ist gesperrt")
        return self.values[key]

    def get(self, key: str, default=None):
        self.requested.append(key)
        if key == SECRET_NAME and not self.allow_secret:
            raise AssertionError("Secret-Zugriff ist gesperrt")
        return self.values.get(key, default)

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


@pytest.fixture(autouse=True)
def block_real_client_and_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Echter Client oder Netzwerkzugriff ist im CLI-Test gesperrt")

    monkeypatch.setattr(openai, "OpenAI", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def _minimal_route(**extra: object) -> str:
    value: dict[str, object] = {
        "schema_version": 1, "planer": False, "analyst": False,
        "umsetzer": True, "tester": False, "pruefer": True,
        "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG",
    }
    value.update(extra)
    return json.dumps(value)


def _review(decision: str = "AKZEPTIERT") -> str:
    return json.dumps({
        "entscheidung": decision,
        "fehlerursprung": "UNKLAR",
        "begruendung": "Offline",
        "verbesserungen": [],
    })


def test_default_offline_cli_is_successful_and_safe(capsys) -> None:
    environment = GuardedEnvironment({SECRET_NAME: FAKE_SECRET})
    assert cli.main([], environment=environment) == cli.EXIT_SUCCESS
    output = capsys.readouterr().out
    assert "[MODUS] OFFLINE" in output and "[FERTIG]" in output
    assert "Modellaufrufe: 3" in output
    assert "RouteBudget: 3" in output
    assert "Hard-Limit: 6" in output
    assert "Fake Requests: 3" in output
    assert "Route freigegeben" in output
    assert SECRET_NAME not in environment.requested
    assert FAKE_SECRET not in output
    assert "Du bist CHEF_ROUTER" not in output


def test_offline_request_is_transported_but_not_dumped(monkeypatch, capsys) -> None:
    captured_clients = []
    original = cli.FakeOpenAIClient.from_responses

    def tracking(responses):
        client = original(responses)
        captured_clients.append(client)
        return client

    monkeypatch.setattr(cli.FakeOpenAIClient, "from_responses", tracking)
    marker = "EINDEUTIGER_AUFTRAGSMARKER"
    assert cli.main(["--request", marker], environment=GuardedEnvironment()) == 0
    output = capsys.readouterr().out
    assert marker not in output
    router_input = captured_clients[0].responses.captured_requests[0]["input"]
    assert marker in router_input


def test_offline_state_has_exact_three_calls_usage_and_direct_finalization(capsys) -> None:
    implementation = "Exakt akzeptierte Umsetzung"
    prepared = [
        completed_response(_minimal_route(), input_tokens=1, output_tokens=2),
        completed_response(implementation, input_tokens=3, output_tokens=4),
        completed_response(_review(), input_tokens=5, output_tokens=6),
    ]
    result = cli.run_offline_cli(
        SixAgentRuntimeConfig(), "Auftrag", prepared_responses=prepared,
    )
    capsys.readouterr()
    state = result.state
    assert result.exit_code == 0 and result.fake_request_count == 3
    assert state["actual_call_count"] == state["required_call_budget"] == 3
    assert state["final_answer"] == state["implementation_result"] == implementation
    assert state["iteration_counts"].count(ModelRole.CHEF_FINAL) == 0
    assert [item["agent"] for item in state["usage"]] == [
        ModelRole.CHEF_ROUTER.value, ModelRole.UMSETZER.value, ModelRole.PRUEFER.value,
    ]
    assert len(state["usage"]) == 3
    assert state["events"][-1]["node"] == "FINALIZATION"
    assert state["events"][-1]["model_call"] is False
    assert sum(int(item["gesamt_tokens"]) for item in state["usage"]) == 21


def test_runtime_default_hard_limit_is_six_for_route_d() -> None:
    assert SixAgentRuntimeConfig().hard_max_model_calls == 6


def test_full_route_with_default_limit_runs_route_d_offline(capsys) -> None:
    assert cli.main(["--demo-full-route"], environment=GuardedEnvironment()) == cli.EXIT_SUCCESS
    output = capsys.readouterr().out
    assert "Erforderliches RouteBudget: 6" in output
    assert "Route freigegeben" in output
    assert "Modellaufrufe: 6" in output and "Fake Requests: 6" in output
    assert "[6INT] PLANER" in output and "[6INT] ANALYST" in output
    assert "[6INT] CHEF_FINAL direkte Ausgabe" in output


@pytest.mark.parametrize("router_output", [
    "kein json",
    _minimal_route(hard_max_model_calls=99),
    _minimal_route(ziel_agent="CHEF_FINAL"),
])
def test_invalid_or_injected_router_output_is_controlled(router_output: str, capsys) -> None:
    response_id = "resp-secret-marker"
    prepared = [completed_response(router_output) | {"id": response_id}]
    code = cli.main([], environment=GuardedEnvironment(), prepared_responses=prepared)
    output = capsys.readouterr().out
    assert code == cli.EXIT_WORKFLOW_FAILURE
    assert "Workflow kontrolliert fehlgeschlagen" in output
    assert "Fake Requests: 1" in output
    assert router_output not in output and response_id not in output


def test_provider_failure_is_sanitized_and_not_retried(capsys) -> None:
    code = cli.main(
        [], environment=GuardedEnvironment(),
        prepared_responses=[RuntimeError(FAKE_SECRET)],
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_WORKFLOW_FAILURE
    assert "Fake Requests: 1" in output
    assert FAKE_SECRET not in output and "Traceback" not in output


def test_controlled_failure_after_reviewer_has_no_finalization(capsys) -> None:
    prepared = [
        completed_response(_minimal_route()), completed_response("Umsetzung"),
        completed_response(_review("UNKLAR")),
    ]
    result = cli.run_offline_cli(
        SixAgentRuntimeConfig(), "Auftrag", prepared_responses=prepared,
    )
    capsys.readouterr()
    assert result.exit_code == cli.EXIT_WORKFLOW_FAILURE
    assert result.fake_request_count == 3
    assert result.state["final_answer"] == ""
    assert all(item["node"] != "FINALIZATION" for item in result.state["events"])


def test_live_flag_without_runtime_gate_is_blocked_without_client(capsys, monkeypatch) -> None:
    def forbidden_fake(*args, **kwargs):
        raise AssertionError("Live-Preflight darf keinen Fake- oder echten Client erzeugen")

    monkeypatch.setattr(cli.FakeOpenAIClient, "from_responses", forbidden_fake)
    code = cli.main(
        ["--live-six-agent", "--request", "Auftrag"],
        environment=GuardedEnvironment(),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_CLI_OR_CONFIG
    assert "Runtime-Live-Gate ist nicht aktiviert" in output
    assert "Kein Live-Aufruf ausgeführt" in output


def test_runtime_gate_without_cli_gate_remains_offline_and_never_creates_official_client(capsys) -> None:
    environment = GuardedEnvironment({"MAS6_LIVE_ENABLED": "true", SECRET_NAME: FAKE_SECRET})
    assert cli.main([], environment=environment) == cli.EXIT_SUCCESS
    output = capsys.readouterr().out
    assert "[MODUS] OFFLINE" in output
    assert SECRET_NAME not in environment.requested
    assert FAKE_SECRET not in output


def _live_environment(**extra: str) -> GuardedEnvironment:
    return GuardedEnvironment(
        {"MAS6_LIVE_ENABLED": "true", SECRET_NAME: FAKE_SECRET, **extra},
        allow_secret=True,
    )


def _budget_four_route() -> str:
    return json.dumps({
        "schema_version": 1, "planer": False, "analyst": False,
        "umsetzer": True, "tester": True, "pruefer": True,
        "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG",
    })


def _tester() -> str:
    return json.dumps({
        "entscheidung": "BESTANDEN", "fehlerursprung": "UNKLAR",
        "begruendung": "Offline", "verbesserungen": [],
    })


def _fake_factory(responses: list[object], captured: list[FakeOpenAIClient]):
    def factory(**kwargs: object) -> FakeOpenAIClient:
        assert kwargs["api_key"] == FAKE_SECRET
        assert kwargs["max_retries"] == 0
        client = FakeOpenAIClient.from_responses(responses)
        captured.append(client)
        return client
    return factory


def test_live_cli_fake_client_runs_budget_four_path_through_chef_final(capsys) -> None:
    captured: list[FakeOpenAIClient] = []
    implementation = "MODEL_OUTPUT_MUST_NOT_BE_PRINTED"
    responses = [
        completed_response(_budget_four_route()), completed_response(implementation),
        completed_response(_tester()), completed_response(_review()),
    ]
    code = cli.main(
        ["--live-six-agent", "--request", "Auftrag"],
        environment=_live_environment(),
        client_factory=_fake_factory(responses, captured),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_SUCCESS
    assert len(captured) == 1
    client = captured[0]
    assert [call.role for call in client.responses.call_history] == [
        ModelRole.CHEF_ROUTER, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER,
    ]
    assert len(client.responses.call_history) == 4
    assert "RouteBudget: 4" in output and "Hard-Limit: 6" in output
    assert "[6INT] CHEF_FINAL direkte Ausgabe" in output
    assert implementation not in output and FAKE_SECRET not in output
    for request in client.responses.captured_requests:
        assert request["timeout"] == 30.0
        assert request["store"] is False
        assert request["parallel_tool_calls"] is False
        assert request["reasoning"] == {"effort": "minimal"}
        assert "tools" not in request and "stream" not in request


def test_live_route_over_hard_limit_stops_after_router(capsys) -> None:
    captured: list[FakeOpenAIClient] = []
    responses = [completed_response(cli._route_json(full=True))]
    code = cli.main(
        ["--live-six-agent", "--request", "Auftrag"],
        environment=_live_environment(MAS6_HARD_MAX_MODEL_CALLS="4"),
        client_factory=_fake_factory(responses, captured),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_SAFETY_BLOCK
    assert len(captured[0].responses.call_history) == 1
    assert captured[0].responses.call_history[0].role is ModelRole.CHEF_ROUTER
    assert "RouteBudget: 6" in output and "durch RouteBudget blockiert" in output


@pytest.mark.parametrize("failed_index", range(4))
def test_live_role_failure_is_not_retried_and_stops_following_calls(failed_index, capsys) -> None:
    captured: list[FakeOpenAIClient] = []
    values: list[object] = [
        completed_response(_budget_four_route()), completed_response("Umsetzung"),
        completed_response(_tester()), completed_response(_review()),
    ]
    values[failed_index] = RuntimeError("SECRET_EXCEPTION_BODY")
    code = cli.main(
        ["--live-six-agent", "--request", "SECRET_PROMPT_BODY"],
        environment=_live_environment(),
        client_factory=_fake_factory(values, captured),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_WORKFLOW_FAILURE
    assert len(captured[0].responses.call_history) == failed_index + 1
    assert "SECRET_EXCEPTION_BODY" not in output
    assert "SECRET_PROMPT_BODY" not in output
    assert FAKE_SECRET not in output and "Traceback" not in output


def test_live_missing_secret_stops_before_client_or_request(capsys) -> None:
    called = False
    def forbidden_factory(**kwargs: object):
        nonlocal called
        called = True
        raise AssertionError
    environment = GuardedEnvironment({"MAS6_LIVE_ENABLED": "true"}, allow_secret=True)
    code = cli.main(
        ["--live-six-agent", "--request", "Auftrag"],
        environment=environment,
        client_factory=forbidden_factory,
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_CLI_OR_CONFIG and not called
    assert "fehlt der API-Key" in output and "Kein Live-Aufruf" in output


def test_live_preflight_requires_request(capsys) -> None:
    code = cli.main(
        ["--live-six-agent"],
        environment=GuardedEnvironment({"MAS6_LIVE_ENABLED": "true"}),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_CLI_OR_CONFIG
    assert "fehlt der Benutzerauftrag" in output


def test_live_preflight_hard_limit_below_minimum_is_safety_block(capsys) -> None:
    code = cli.main(
        ["--live-six-agent", "--request", "Auftrag"],
        environment=GuardedEnvironment({
            "MAS6_LIVE_ENABLED": "true", "MAS6_HARD_MAX_MODEL_CALLS": "2",
        }),
    )
    output = capsys.readouterr().out
    assert code == cli.EXIT_SAFETY_BLOCK
    assert "blockiert bereits den Minimalpfad" in output


@pytest.mark.parametrize(("argv", "environment"), [
    (["--unbekannt"], {}),
    ([], {"MAS6_HARD_MAX_MODEL_CALLS": "kaputt"}),
])
def test_invalid_cli_or_runtime_config_has_deterministic_exit_two(argv, environment, capsys) -> None:
    assert cli.main(argv, environment=GuardedEnvironment(environment)) == cli.EXIT_CLI_OR_CONFIG
    output = capsys.readouterr().out
    assert "[KONFIGURATIONSFEHLER]" in output and "Traceback" not in output


def test_offline_cli_never_reads_secret_or_creates_official_client() -> None:
    environment = GuardedEnvironment({SECRET_NAME: FAKE_SECRET})
    assert cli.main([], environment=environment) == cli.EXIT_SUCCESS
    assert SECRET_NAME not in environment.requested


def test_offline_cli_subprocess_succeeds() -> None:
    completed = subprocess.run(
        [sys.executable, str(SRC_DIR / "six_agent_main.py")],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=15, check=False,
    )
    assert completed.returncode == 0
    assert "Modellaufrufe: 3" in completed.stdout
    assert "Fake Requests: 3" in completed.stdout
    assert "[FERTIG]" in completed.stdout
