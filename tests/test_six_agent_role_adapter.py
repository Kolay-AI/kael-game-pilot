from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import six_agent_role_adapter as adapter_module  # noqa: E402
import structured_routing  # noqa: E402
from prompts import ANALYST_SYSTEM_PROMPT, PLANER_SYSTEM_PROMPT, TESTER_SYSTEM_PROMPT  # noqa: E402
from route_budget import RoleLimits  # noqa: E402
from six_agent_contracts import (  # noqa: E402
    ANALYST_MAX_CHARS,
    PLANNER_MAX_CHARS,
    build_analyst_input,
    build_planner_input,
    build_tester_input,
)
from six_agent_role_adapter import (  # noqa: E402
    AdapterGenerationResult,
    AdapterUsageData,
    DeterministicRoleProvider,
    RoleAdapterConfig,
    run_analyst,
    run_planner,
    run_tester,
)
from six_agent_state import ModelRole, SixAgentWorkflowState, create_initial_six_agent_state  # noqa: E402
from structured_routing import (  # noqa: E402
    ReviewFailureOrigin as ReviewOrigin,
    TesterDecision as TDecision,
    TesterFailureOrigin as TFOrigin,
)


def _state(*, budget=10, hard=10) -> SixAgentWorkflowState:
    state = create_initial_six_agent_state("adapter-test", "Benutzerauftrag", hard_max_model_calls=hard)
    state["required_call_budget"] = budget
    state["status"] = "laeuft"
    state["implementation_result"] = "Aktuelle Umsetzung"
    return state


def _provider(role: ModelRole, *responses) -> DeterministicRoleProvider:
    return DeterministicRoleProvider({role: list(responses)})


def _tester_json(decision="BESTANDEN", origin="UNKLAR", improvements=None, **extra) -> str:
    return json.dumps({
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Kurze Begründung",
        "verbesserungen": [] if improvements is None else improvements,
        **extra,
    })


def _merge(state: SixAgentWorkflowState, update: dict[str, object]) -> SixAgentWorkflowState:
    merged = dict(state)
    for key, value in update.items():
        if key in {"events", "usage"}:
            merged[key] = list(merged[key]) + list(value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged  # type: ignore[return-value]


def _assert_one_call(provider, role, prompt, expected_input) -> None:
    assert len(provider.call_history) == 1
    metadata = provider.call_history[0]
    assert metadata.role is role
    assert metadata.system_prompt_chars == len(prompt)
    assert metadata.user_input_chars == len(expected_input)
    assert provider.captured_requests == [(role, prompt, expected_input)]


def test_planner_valid_call_uses_exact_contract_and_updates_state() -> None:
    state = _state()
    provider = _provider(ModelRole.PLANER, "1. Anforderungen klären")
    update = run_planner(state, provider)
    expected = build_planner_input("Benutzerauftrag")
    _assert_one_call(provider, ModelRole.PLANER, PLANER_SYSTEM_PROMPT, expected)
    assert update["planning_result"] == "1. Anforderungen klären"
    assert update["current_agent"] is ModelRole.PLANER
    assert update["actual_call_count"] == 1
    assert update["iteration_counts"].planer == 1
    assert len(update["events"]) == len(update["usage"]) == 1


def test_planner_feedback_once_and_context_isolation() -> None:
    state = _state()
    state.update({
        "analysis_result": "NICHT-AN-PLANER-ANALYSE",
        "implementation_result": "NICHT-AN-PLANER-UMSETZUNG",
        "testing_result": None,
        "review_result": None,
        "current_feedback": "Planfeedback-einmal",
        "feedback_origin": ReviewOrigin.PLANUNG,
        "events": [{"secret_history": "NICHT-AN-PLANER-EVENT"}],
        "usage": [{"tokens": "NICHT-AN-PLANER-USAGE"}],
    })
    provider = _provider(ModelRole.PLANER, "Plan")
    run_planner(state, provider)
    user_input = provider.captured_requests[0][2]
    assert user_input == build_planner_input(
        state["user_request"], current_feedback=state["current_feedback"],
        feedback_origin=ReviewOrigin.PLANUNG,
    )
    assert user_input.count("Planfeedback-einmal") == 1
    for marker in ("NICHT-AN-PLANER-ANALYSE", "NICHT-AN-PLANER-UMSETZUNG", "NICHT-AN-PLANER-EVENT", "NICHT-AN-PLANER-USAGE"):
        assert marker not in user_input


@pytest.mark.parametrize("output", ["", "x" * (PLANNER_MAX_CHARS + 1)])
def test_planner_invalid_output_fails_closed_without_second_call(output) -> None:
    provider = _provider(ModelRole.PLANER, output, "darf nicht laufen")
    update = run_planner(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert update["actual_call_count"] == 1
    assert len(provider.call_history) == 1
    assert "planning_result" not in update


@pytest.mark.parametrize("blocked", ["role", "budget", "hard"])
def test_planner_limits_block_before_provider(blocked) -> None:
    state = _state()
    config = RoleAdapterConfig()
    if blocked == "role":
        state["iteration_counts"] = state["iteration_counts"].increment(ModelRole.PLANER, 1)
        config = RoleAdapterConfig(RoleLimits(planer=1))
    elif blocked == "budget":
        state["required_call_budget"] = 0
    else:
        state["hard_max_model_calls"] = 0
    provider = _provider(ModelRole.PLANER, "darf nicht laufen")
    update = run_planner(state, provider, config)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []


def test_missing_state_field_fails_before_provider() -> None:
    state = _state()
    del state["user_request"]
    provider = _provider(ModelRole.PLANER, "darf nicht laufen")
    update = run_planner(state, provider)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []


def test_provider_exception_is_fail_closed_without_retry() -> None:
    provider = _provider(ModelRole.PLANER, RuntimeError("sensitive provider detail"), "retry")
    update = run_planner(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert update["actual_call_count"] == 1
    assert "sensitive" not in update["failure_reason"]
    assert len(provider.call_history) == 1


@pytest.mark.parametrize("plan", ["", "Aktueller Plan"])
def test_analyst_works_with_and_without_plan(plan) -> None:
    state = _state()
    state["planning_result"] = plan
    provider = _provider(ModelRole.ANALYST, "Risiken: keine kritischen Risiken")
    update = run_analyst(state, provider)
    expected = build_analyst_input("Benutzerauftrag", planning_result=plan)
    _assert_one_call(provider, ModelRole.ANALYST, ANALYST_SYSTEM_PROMPT, expected)
    assert update["analysis_result"] == "Risiken: keine kritischen Risiken"


def test_analyst_feedback_and_context_isolation() -> None:
    state = _state()
    state.update({
        "planning_result": "Aktueller Plan",
        "current_feedback": "Analysefeedback-einmal",
        "feedback_origin": ReviewOrigin.ANALYSE,
        "implementation_result": "NICHT-AN-ANALYST-UMSETZUNG",
        "events": [{"x": "NICHT-AN-ANALYST-EVENT"}],
        "usage": [{"x": "NICHT-AN-ANALYST-USAGE"}],
    })
    provider = _provider(ModelRole.ANALYST, "Analyse")
    run_analyst(state, provider)
    user_input = provider.captured_requests[0][2]
    assert user_input.count("Analysefeedback-einmal") == 1
    assert "Aktueller Plan" in user_input
    for marker in ("NICHT-AN-ANALYST-UMSETZUNG", "NICHT-AN-ANALYST-EVENT", "NICHT-AN-ANALYST-USAGE"):
        assert marker not in user_input


@pytest.mark.parametrize("output", ["", "x" * (ANALYST_MAX_CHARS + 1)])
def test_analyst_empty_or_long_fails_closed(output) -> None:
    provider = _provider(ModelRole.ANALYST, output, "retry")
    update = run_analyst(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert len(provider.call_history) == 1


@pytest.mark.parametrize("blocked", ["role", "budget"])
def test_analyst_role_or_budget_limit_blocks(blocked) -> None:
    state = _state()
    config = RoleAdapterConfig()
    if blocked == "role":
        state["iteration_counts"] = state["iteration_counts"].increment(ModelRole.ANALYST, 1)
        config = RoleAdapterConfig(RoleLimits(analyst=1))
    else:
        state["required_call_budget"] = 0
    provider = _provider(ModelRole.ANALYST, "darf nicht laufen")
    update = run_analyst(state, provider, config)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []


def test_tester_passed_uses_exact_prompt_input_and_clears_feedback() -> None:
    state = _state()
    state.update({"planning_result": "Plan", "analysis_result": "Analyse", "current_feedback": "alt"})
    provider = _provider(ModelRole.TESTER, _tester_json())
    update = run_tester(state, provider)
    expected = build_tester_input("Benutzerauftrag", "Aktuelle Umsetzung", planning_result="Plan", analysis_result="Analyse")
    _assert_one_call(provider, ModelRole.TESTER, TESTER_SYSTEM_PROMPT, expected)
    assert update["testing_result"].entscheidung is TDecision.BESTANDEN
    assert update["current_feedback"] == ""
    assert update["feedback_origin"] is None


@pytest.mark.parametrize("origin", ["UMSETZUNG", "TEST", "UNKLAR"])
def test_tester_all_existing_failure_origins_are_preserved(origin) -> None:
    provider = _provider(ModelRole.TESTER, _tester_json("FEHLER", origin, ["Korrekturhinweis"]))
    update = run_tester(_state(), provider)
    assert update["testing_result"].entscheidung is TDecision.FEHLER
    assert update["feedback_origin"].value == origin
    assert update["current_feedback"] == "Korrekturhinweis"


@pytest.mark.parametrize("output", [
    "kein json",
    _tester_json(extra="unbekannt"),
    _tester_json(ziel_agent="UMSETZER"),
])
def test_tester_invalid_json_unknown_field_and_target_injection_fail_closed(output) -> None:
    provider = _provider(ModelRole.TESTER, output, "retry")
    update = run_tester(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert "testing_result" not in update
    assert len(provider.call_history) == 1


@pytest.mark.parametrize("blocked", ["role", "budget", "hard"])
def test_tester_limits_block_before_provider(blocked) -> None:
    state = _state()
    config = RoleAdapterConfig()
    if blocked == "role":
        state["iteration_counts"] = state["iteration_counts"].increment(ModelRole.TESTER, 1)
        config = RoleAdapterConfig(RoleLimits(tester=1))
    elif blocked == "budget":
        state["required_call_budget"] = 0
    else:
        state["hard_max_model_calls"] = 0
    provider = _provider(ModelRole.TESTER, _tester_json())
    update = run_tester(state, provider, config)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []


def test_tester_adapter_calls_validate_tester_output(monkeypatch) -> None:
    sentinel = structured_routing.parse_tester_result(_tester_json())
    calls = []

    def fake_validator(value):
        calls.append(value)
        return sentinel

    monkeypatch.setattr(adapter_module, "validate_tester_output", fake_validator)
    provider = _provider(ModelRole.TESTER, "opaque")
    update = run_tester(_state(), provider)
    assert calls == ["opaque"]
    assert update["testing_result"] is sentinel


def test_tester_indirectly_uses_existing_parse_tester_result(monkeypatch) -> None:
    original = structured_routing.parse_tester_result
    calls = []

    def tracking_parser(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(structured_routing, "parse_tester_result", tracking_parser)
    payload = _tester_json()
    run_tester(_state(), _provider(ModelRole.TESTER, payload))
    assert calls == [payload]


def test_tester_context_excludes_review_audit_usage_and_old_implementation() -> None:
    first = _state()
    first.update({
        "implementation_result": "Neue Umsetzung",
        "review_result": None,
        "events": [{"old": "Alte Umsetzung aus Audit"}],
        "usage": [{"old": "Token-Historie"}],
    })
    second = dict(first)
    second["events"] = first["events"] * 500
    second["usage"] = first["usage"] * 500
    provider_a = _provider(ModelRole.TESTER, _tester_json())
    provider_b = _provider(ModelRole.TESTER, _tester_json())
    run_tester(first, provider_a)
    run_tester(second, provider_b)  # type: ignore[arg-type]
    input_a = provider_a.captured_requests[0][2]
    input_b = provider_b.captured_requests[0][2]
    assert input_a == input_b
    assert provider_a.call_history[0].user_input_chars == provider_b.call_history[0].user_input_chars
    assert "Alte Umsetzung" not in input_a and "Token-Historie" not in input_a


@pytest.mark.parametrize(("role", "runner", "response"), [
    (ModelRole.PLANER, run_planner, "Plan"),
    (ModelRole.ANALYST, run_analyst, "Analyse"),
    (ModelRole.TESTER, run_tester, _tester_json()),
])
def test_every_role_input_size_is_unchanged_when_only_events_and_usage_grow(role, runner, response) -> None:
    state_a = _state()
    state_b = _state()
    state_b["events"] = [{"large": "x" * 10_000}] * 100
    state_b["usage"] = [{"tokens": 999_999}] * 100
    provider_a = _provider(role, response)
    provider_b = _provider(role, response)
    runner(state_a, provider_a)
    runner(state_b, provider_b)
    assert provider_a.call_history[0].user_input_chars == provider_b.call_history[0].user_input_chars
    assert provider_a.captured_requests[0][2] == provider_b.captured_requests[0][2]


@pytest.mark.parametrize(("role", "runner", "field", "v1", "v2"), [
    (ModelRole.PLANER, run_planner, "planning_result", "Plan v1", "Plan v2"),
    (ModelRole.ANALYST, run_analyst, "analysis_result", "Analyse v1", "Analyse v2"),
])
def test_text_role_repeated_calls_replace_domain_result_and_accumulate_audit(role, runner, field, v1, v2) -> None:
    state = _state()
    provider = _provider(role, v1, v2)
    state = _merge(state, runner(state, provider))
    state = _merge(state, runner(state, provider))
    assert state[field] == v2
    assert not isinstance(state[field], list)
    assert len(state["events"]) == len(state["usage"]) == 2
    assert state["actual_call_count"] == 2
    assert state["iteration_counts"].count(role) == 2


def test_tester_repeated_calls_replace_result_and_accumulate_audit() -> None:
    state = _state()
    provider = _provider(
        ModelRole.TESTER,
        _tester_json("FEHLER", "UMSETZUNG", ["v1"]),
        _tester_json(),
    )
    state = _merge(state, run_tester(state, provider))
    state = _merge(state, run_tester(state, provider))
    assert state["testing_result"].entscheidung is TDecision.BESTANDEN
    assert state["current_feedback"] == ""
    assert len(state["events"]) == len(state["usage"]) == 2


def test_usage_data_from_provider_is_accumulated_unchanged() -> None:
    usage = AdapterUsageData("PLANER", input_tokens=3, output_tokens=4, total_tokens=7)
    provider = _provider(ModelRole.PLANER, AdapterGenerationResult("Plan", usage))
    update = run_planner(_state(), provider)
    assert update["usage"] == [usage.as_dict()]


def test_adapter_has_no_openai_network_graph_environment_or_secret_dependency() -> None:
    source = (SRC_DIR / "six_agent_role_adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {
        "openai", "httpx", "httpx2", "requests", "urllib", "socket", "llm_provider",
        "graph", "six_agent_graph", "langgraph", "os",
    }
    assert imports.isdisjoint(forbidden)
    assert "OPENAI_API_KEY" not in source
    assert "getenv" not in source and "environ" not in source
