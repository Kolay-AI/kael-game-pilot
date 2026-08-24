from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import six_agent_role_adapter as adapter_module  # noqa: E402
import structured_routing  # noqa: E402
from prompts import SIX_AGENT_REVIEWER_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT  # noqa: E402
from route_budget import RoleLimits  # noqa: E402
from six_agent_contracts import (  # noqa: E402
    IMPLEMENTER_MAX_CHARS,
    IMPLEMENTER_MAX_WORDS,
    build_implementer_input,
    build_reviewer_input,
)
from six_agent_role_adapter import (  # noqa: E402
    AdapterGenerationResult,
    AdapterUsageData,
    DeterministicRoleProvider,
    RoleAdapterConfig,
    run_implementer,
    run_reviewer,
)
from six_agent_state import ModelRole, SixAgentWorkflowState, create_initial_six_agent_state  # noqa: E402
from structured_routing import (  # noqa: E402
    ReviewDecision as RDecision,
    ReviewFailureOrigin as ReviewOrigin,
    TesterFailureOrigin as TFOrigin,
    parse_tester_result,
)


def _state(*, budget=10, hard=10) -> SixAgentWorkflowState:
    state = create_initial_six_agent_state("new-adapter-test", "Benutzerauftrag", hard_max_model_calls=hard)
    state["required_call_budget"] = budget
    state["status"] = "laeuft"
    state["implementation_result"] = "Aktuelle Umsetzung"
    return state


def _provider(role: ModelRole, *responses) -> DeterministicRoleProvider:
    return DeterministicRoleProvider({role: list(responses)})


def _tester_result():
    return parse_tester_result(json.dumps({
        "entscheidung": "BESTANDEN", "fehlerursprung": "UNKLAR",
        "begruendung": "Tester-Marker", "verbesserungen": [],
    }))


def _review_json(decision="AKZEPTIERT", origin="UNKLAR", improvements=None, **extra) -> str:
    return json.dumps({
        "entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Review-Begründung",
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


def _assert_request(provider, role, prompt, expected_input) -> None:
    assert len(provider.call_history) == 1
    call = provider.call_history[0]
    assert call.role is role
    assert call.system_prompt_chars == len(prompt)
    assert call.user_input_chars == len(expected_input)
    assert provider.captured_requests == [(role, prompt, expected_input)]


@pytest.mark.parametrize(("plan", "analysis"), [
    ("", ""), ("Plan", ""), ("", "Analyse"), ("Plan", "Analyse"),
])
def test_implementer_uses_exact_builder_for_minimal_and_optional_context(plan, analysis) -> None:
    state = _state()
    state["planning_result"] = plan
    state["analysis_result"] = analysis
    provider = _provider(ModelRole.UMSETZER, "Neue Umsetzung")
    update = run_implementer(state, provider)
    expected = build_implementer_input("Benutzerauftrag", planning_result=plan, analysis_result=analysis)
    _assert_request(provider, ModelRole.UMSETZER, UMSETZER_SYSTEM_PROMPT, expected)
    assert update["implementation_result"] == "Neue Umsetzung"
    assert update["actual_call_count"] == 1
    assert update["iteration_counts"].umsetzer == 1


def test_implementer_receives_matching_feedback_once_and_excludes_foreign_feedback() -> None:
    matching = _state()
    matching.update({"current_feedback": "Umsetzungsfeedback", "feedback_origin": ReviewOrigin.UMSETZUNG})
    foreign = _state()
    foreign.update({"current_feedback": "Fremdfeedback", "feedback_origin": ReviewOrigin.ANALYSE})
    provider_a = _provider(ModelRole.UMSETZER, "U1")
    provider_b = _provider(ModelRole.UMSETZER, "U2")
    run_implementer(matching, provider_a)
    run_implementer(foreign, provider_b)
    assert provider_a.captured_requests[0][2].count("Umsetzungsfeedback") == 1
    assert "Fremdfeedback" not in provider_b.captured_requests[0][2]


def test_implementer_context_excludes_old_results_review_test_audit_and_usage() -> None:
    state = _state()
    state.update({
        "planning_result": "Aktueller Plan", "analysis_result": "Aktuelle Analyse",
        "implementation_result": "ALTE-UMSETZUNG", "testing_result": _tester_result(),
        "review_result": structured_routing.parse_review_result(_review_json()),
        "events": [{"secret": "AUDIT-HISTORIE"}], "usage": [{"secret": "USAGE-HISTORIE"}],
    })
    provider = _provider(ModelRole.UMSETZER, "Neu")
    run_implementer(state, provider)
    value = provider.captured_requests[0][2]
    for marker in ("ALTE-UMSETZUNG", "Tester-Marker", "Review-Begründung", "AUDIT-HISTORIE", "USAGE-HISTORIE"):
        assert marker not in value


def test_implementer_repeated_calls_replace_result_and_accumulate_only_audit_usage() -> None:
    state = _state()
    provider = _provider(ModelRole.UMSETZER, "Umsetzung v1", "Umsetzung v2")
    state = _merge(state, run_implementer(state, provider))
    state = _merge(state, run_implementer(state, provider))
    assert state["implementation_result"] == "Umsetzung v2"
    assert not isinstance(state["implementation_result"], list)
    assert state["actual_call_count"] == state["iteration_counts"].umsetzer == 2
    assert len(state["events"]) == len(state["usage"]) == 2


def test_implementer_usage_and_safe_event_are_exactly_once() -> None:
    usage = AdapterUsageData("UMSETZER", input_tokens=2, output_tokens=3, total_tokens=5)
    secret = "DO-NOT-LOG-CONTENT"
    provider = _provider(ModelRole.UMSETZER, AdapterGenerationResult(secret, usage))
    update = run_implementer(_state(), provider)
    assert update["usage"] == [usage.as_dict()]
    assert len(update["events"]) == 1
    assert secret not in json.dumps(update["events"])
    assert "prompt" not in json.dumps(update["events"]).lower()


class InvalidContractProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, role, system_prompt, user_input):
        self.calls += 1
        return object()


@pytest.mark.parametrize("response", [
    RuntimeError("provider intern"),
    "",
    "wort " * (IMPLEMENTER_MAX_WORDS + 1),
    "x" * (IMPLEMENTER_MAX_CHARS + 1),
])
def test_implementer_failures_after_provider_count_once_without_retry(response) -> None:
    provider = _provider(ModelRole.UMSETZER, response, "retry darf nicht laufen")
    update = run_implementer(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert update["actual_call_count"] == 1
    assert update["iteration_counts"].umsetzer == 1
    assert len(provider.call_history) == 1
    assert "implementation_result" not in update


def test_implementer_invalid_provider_contract_counts_once() -> None:
    provider = InvalidContractProvider()
    update = run_implementer(_state(), provider)  # type: ignore[arg-type]
    assert update["status"] == "fehlgeschlagen"
    assert update["actual_call_count"] == 1
    assert provider.calls == 1


@pytest.mark.parametrize("blocked", ["budget", "hard", "role"])
def test_implementer_preflight_blocks_without_call_or_increment(blocked) -> None:
    state = _state()
    config = RoleAdapterConfig()
    if blocked == "budget":
        state["required_call_budget"] = 0
    elif blocked == "hard":
        state["hard_max_model_calls"] = 0
    else:
        state["iteration_counts"] = state["iteration_counts"].increment(ModelRole.UMSETZER, 1)
        config = RoleAdapterConfig(RoleLimits(umsetzer=1))
    original_counts = state["iteration_counts"]
    provider = _provider(ModelRole.UMSETZER, "darf nicht laufen")
    update = run_implementer(state, provider, config)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []
    assert update.get("actual_call_count", state["actual_call_count"]) == state["actual_call_count"]
    assert update.get("iteration_counts", original_counts) == original_counts


def test_implementer_input_is_unchanged_when_only_events_and_usage_grow() -> None:
    first = _state()
    second = _state()
    second["events"] = [{"large": "x" * 10_000}] * 100
    second["usage"] = [{"tokens": 999_999}] * 100
    provider_a = _provider(ModelRole.UMSETZER, "U1")
    provider_b = _provider(ModelRole.UMSETZER, "U2")
    run_implementer(first, provider_a)
    run_implementer(second, provider_b)
    assert provider_a.captured_requests[0][2] == provider_b.captured_requests[0][2]
    assert provider_a.call_history[0].user_input_chars == provider_b.call_history[0].user_input_chars


def test_reviewer_minimal_and_full_context_use_exact_builder_and_prompt() -> None:
    minimal = _state()
    full = _state()
    full.update({
        "planning_result": "Plan", "analysis_result": "Analyse", "testing_result": _tester_result(),
    })
    provider_a = _provider(ModelRole.PRUEFER, _review_json())
    provider_b = _provider(ModelRole.PRUEFER, _review_json())
    run_reviewer(minimal, provider_a)
    run_reviewer(full, provider_b)
    _assert_request(
        provider_a, ModelRole.PRUEFER, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
        build_reviewer_input("Benutzerauftrag", "Aktuelle Umsetzung"),
    )
    _assert_request(
        provider_b, ModelRole.PRUEFER, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
        build_reviewer_input(
            "Benutzerauftrag", "Aktuelle Umsetzung", planning_result="Plan",
            analysis_result="Analyse", testing_result=full["testing_result"],
        ),
    )


@pytest.mark.parametrize(("decision", "origin", "improvements"), [
    ("AKZEPTIERT", "UNKLAR", []),
    ("ABGELEHNT", "PLANUNG", ["Plan korrigieren"]),
    ("ABGELEHNT", "ANALYSE", ["Analyse korrigieren"]),
    ("ABGELEHNT", "UMSETZUNG", ["Umsetzung korrigieren"]),
    ("ABGELEHNT", "TEST", ["Test korrigieren"]),
    ("UNKLAR", "UNKLAR", []),
])
def test_reviewer_preserves_every_valid_review_result_without_interpretation(decision, origin, improvements) -> None:
    payload = _review_json(decision, origin, improvements)
    expected = structured_routing.parse_review_result(payload)
    update = run_reviewer(_state(), _provider(ModelRole.PRUEFER, payload))
    assert update["review_result"] == expected
    assert update["review_result"].entscheidung.value == decision
    assert "next_agent" not in update


def test_reviewer_does_not_call_routing_function(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Routing darf im Adapter nicht ausgeführt werden")

    monkeypatch.setattr(structured_routing, "target_for_failure_origin", forbidden)
    update = run_reviewer(
        _state(), _provider(ModelRole.PRUEFER, _review_json("ABGELEHNT", "ANALYSE", ["Korrigieren"])),
    )
    assert update["review_result"].fehlerursprung is ReviewOrigin.ANALYSE
    assert "next_agent" not in update


def test_reviewer_repeated_calls_replace_review_and_accumulate_only_audit_usage() -> None:
    state = _state()
    provider = _provider(
        ModelRole.PRUEFER,
        _review_json("ABGELEHNT", "UMSETZUNG", ["v1"]),
        _review_json(),
    )
    state = _merge(state, run_reviewer(state, provider))
    state = _merge(state, run_reviewer(state, provider))
    assert state["review_result"].entscheidung is RDecision.AKZEPTIERT
    assert not isinstance(state["review_result"], list)
    assert state["actual_call_count"] == state["iteration_counts"].pruefer == 2
    assert len(state["events"]) == len(state["usage"]) == 2


def test_reviewer_context_excludes_old_review_audit_usage_and_routing_history() -> None:
    state = _state()
    state.update({
        "planning_result": "Plan", "analysis_result": "Analyse", "testing_result": _tester_result(),
        "review_result": structured_routing.parse_review_result(
            _review_json("ABGELEHNT", "UMSETZUNG", ["ALTES-REVIEW"]),
        ),
        "events": [{"routing": "ROUTING-HISTORIE"}], "usage": [{"tokens": "USAGE-HISTORIE"}],
    })
    provider = _provider(ModelRole.PRUEFER, _review_json())
    run_reviewer(state, provider)
    value = provider.captured_requests[0][2]
    for marker in ("ALTES-REVIEW", "ROUTING-HISTORIE", "USAGE-HISTORIE"):
        assert marker not in value


@pytest.mark.parametrize("payload", [
    "kein json",
    _review_json(extra="unbekannt"),
    _review_json(ziel_agent="PLANER"),
    _review_json(decision="FREIGEGEBEN"),
    _review_json(decision="ABGELEHNT", origin="QUELLE", improvements=["x"]),
    _review_json(decision="AKZEPTIERT", origin="PLANUNG"),
])
def test_reviewer_validation_failures_count_once_without_retry(payload) -> None:
    provider = _provider(ModelRole.PRUEFER, payload, "retry darf nicht laufen")
    update = run_reviewer(_state(), provider)
    assert update["status"] == "fehlgeschlagen"
    assert update["actual_call_count"] == 1
    assert update["iteration_counts"].pruefer == 1
    assert len(provider.call_history) == 1
    assert "review_result" not in update


def test_invalid_output_keeps_existing_adapter_usage_and_event_semantics() -> None:
    implementer = run_implementer(_state(), _provider(ModelRole.UMSETZER, ""))
    reviewer = run_reviewer(_state(), _provider(ModelRole.PRUEFER, "kein json"))
    for update in (implementer, reviewer):
        assert update["actual_call_count"] == 1
        assert "usage" not in update
        assert "events" not in update


def test_reviewer_provider_exception_and_invalid_contract_count_once() -> None:
    exception_provider = _provider(ModelRole.PRUEFER, RuntimeError("intern"))
    failed = run_reviewer(_state(), exception_provider)
    invalid_provider = InvalidContractProvider()
    invalid = run_reviewer(_state(), invalid_provider)  # type: ignore[arg-type]
    assert failed["actual_call_count"] == invalid["actual_call_count"] == 1
    assert len(exception_provider.call_history) == invalid_provider.calls == 1


@pytest.mark.parametrize("blocked", ["budget", "hard", "role"])
def test_reviewer_preflight_blocks_without_call_or_increment(blocked) -> None:
    state = _state()
    config = RoleAdapterConfig()
    if blocked == "budget":
        state["required_call_budget"] = 0
    elif blocked == "hard":
        state["hard_max_model_calls"] = 0
    else:
        state["iteration_counts"] = state["iteration_counts"].increment(ModelRole.PRUEFER, 1)
        config = RoleAdapterConfig(RoleLimits(pruefer=1))
    original_counts = state["iteration_counts"]
    provider = _provider(ModelRole.PRUEFER, _review_json())
    update = run_reviewer(state, provider, config)
    assert update["status"] == "fehlgeschlagen"
    assert provider.call_history == []
    assert update.get("actual_call_count", state["actual_call_count"]) == state["actual_call_count"]
    assert update.get("iteration_counts", original_counts) == original_counts


def test_reviewer_usage_event_and_context_size_are_exact_and_safe() -> None:
    state_a = _state()
    state_b = _state()
    state_b["events"] = [{"large": "x" * 10_000}] * 100
    state_b["usage"] = [{"tokens": 999_999}] * 100
    usage = AdapterUsageData("PRÜFER", input_tokens=4, output_tokens=5, total_tokens=9)
    payload = _review_json()
    provider_a = _provider(ModelRole.PRUEFER, AdapterGenerationResult(payload, usage))
    provider_b = _provider(ModelRole.PRUEFER, payload)
    update = run_reviewer(state_a, provider_a)
    run_reviewer(state_b, provider_b)
    assert update["usage"] == [usage.as_dict()]
    assert len(update["events"]) == 1
    assert payload not in json.dumps(update["events"])
    assert provider_a.captured_requests[0][2] == provider_b.captured_requests[0][2]
    assert provider_a.call_history[0].user_input_chars == provider_b.call_history[0].user_input_chars
