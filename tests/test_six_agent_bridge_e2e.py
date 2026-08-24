from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import openai
import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from prompts import (  # noqa: E402
    ANALYST_SYSTEM_PROMPT, PLANER_SYSTEM_PROMPT, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
    SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT, TESTER_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT,
)
from route_budget import CorrectionPathName  # noqa: E402
from six_agent_bridge_fake_client import (  # noqa: E402
    FakeOpenAIClient, completed_response, incomplete_response,
)
from six_agent_contracts import (  # noqa: E402
    build_analyst_input, build_chef_router_input, build_implementer_input, build_planner_input,
    build_reviewer_input, build_tester_input,
)
from six_agent_graph import full_route_json, minimal_route_json  # noqa: E402
from six_agent_integration_graph import (  # noqa: E402
    CONTROLLED_FAILURE, DeterministicIntegrationRoles, IntegrationGraphConfig,
    run_six_agent_integration_workflow,
)
from six_agent_openai_bridge import (  # noqa: E402
    SixAgentOpenAIBridge, SixAgentOpenAIConfig, role_text_config,
)
from six_agent_state import ModelRole  # noqa: E402
from structured_routing import ReviewFailureOrigin as ReviewOrigin, validate_chef_route  # noqa: E402


@pytest.fixture(autouse=True)
def _forbid_real_openai_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Ein echter OpenAI-Client darf im E2E-Test nicht erzeugt werden.")
    monkeypatch.setattr(openai, "OpenAI", forbidden)


def _tester(decision="BESTANDEN", origin="UNKLAR", improvements=None) -> str:
    return json.dumps({"entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Tester-Begründung", "verbesserungen": [] if improvements is None else improvements})


def _review(decision="AKZEPTIERT", origin="UNKLAR", improvements=None, **extra) -> str:
    return json.dumps({"entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Review-Begründung", "verbesserungen": [] if improvements is None else improvements, **extra})


def _full_success_responses(*, tokens=False):
    values = ["Plan v1", "Analyse v1", "Umsetzung v1", _tester(), _review()]
    totals = [10, 20, 30, 40, 50]
    return [completed_response(value, input_tokens=(total // 2 if tokens else 0),
                               output_tokens=(total - total // 2 if tokens else 0))
            for value, total in zip(values, totals)]


def _execute(route_text, responses, *, hard, corrections=0, allowed=frozenset(),
             initial_events=None, initial_usage=None, request="Benutzerauftrag"):
    client = FakeOpenAIClient.from_responses([completed_response(route_text), *list(responses)])
    bridge = SixAgentOpenAIBridge(client, SixAgentOpenAIConfig(
        model="gpt-5-mini-test", max_output_tokens=888, request_timeout_seconds=29.5,
    ))
    roles = DeterministicIntegrationRoles()
    config = IntegrationGraphConfig(hard_max_model_calls=hard,
        global_correction_limit=corrections, allowed_correction_paths=allowed)
    result = run_six_agent_integration_workflow(request, bridge, roles, config,
        initial_events=initial_events, initial_usage=initial_usage)
    return result, client, roles


def _roles(client):
    return [call.role for call in client.responses.call_history]


def test_full_e2e_path_has_exact_requests_parameters_and_data_flow() -> None:
    result, client, roles = _execute(full_route_json(), _full_success_responses(tokens=True), hard=6)
    assert result["status"] == "erfolgreich" and result["actual_call_count"] == 6
    assert _roles(client) == [ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert roles.calls == []
    captured = client.responses.captured_requests
    expected_inputs = [
        build_chef_router_input("Benutzerauftrag"),
        build_planner_input("Benutzerauftrag"),
        build_analyst_input("Benutzerauftrag", planning_result="Plan v1"),
        build_implementer_input("Benutzerauftrag", planning_result="Plan v1", analysis_result="Analyse v1"),
        build_tester_input("Benutzerauftrag", "Umsetzung v1", planning_result="Plan v1", analysis_result="Analyse v1"),
        build_reviewer_input("Benutzerauftrag", "Umsetzung v1", planning_result="Plan v1",
            analysis_result="Analyse v1", testing_result=result["testing_result"]),
    ]
    expected_prompts = [SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT, PLANER_SYSTEM_PROMPT, ANALYST_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT,
                        TESTER_SYSTEM_PROMPT, SIX_AGENT_REVIEWER_SYSTEM_PROMPT]
    assert [item["input"] for item in captured] == expected_inputs
    assert [item["instructions"] for item in captured] == expected_prompts
    for index, request in enumerate(captured):
        assert set(request) == {"model", "instructions", "input", "max_output_tokens", "reasoning",
                                "text", "store", "parallel_tool_calls", "timeout"}
        assert request["model"] == "gpt-5-mini-test"
        expected_tokens = 1_600 if index == 3 else 888
        assert request["max_output_tokens"] == expected_tokens
        assert request["reasoning"] == {"effort": "minimal"}
        expected_text = role_text_config(_roles(client)[index])
        assert request["text"] == expected_text
        assert request["store"] is False and request["parallel_tool_calls"] is False
        assert request["timeout"] == 29.5 and "tools" not in request
    assert result["planning_result"] == "Plan v1" and result["analysis_result"] == "Analyse v1"
    assert result["implementation_result"] == result["final_answer"] == "Umsetzung v1"


def test_minimal_e2e_path_has_three_fake_requests_and_three_total_calls() -> None:
    result, client, roles = _execute(minimal_route_json(),
        [completed_response("Umsetzung"), completed_response(_review())], hard=3)
    assert result["status"] == "erfolgreich" and result["actual_call_count"] == 3
    assert result["required_call_budget"] == 3
    assert _roles(client) == [ModelRole.CHEF_ROUTER, ModelRole.UMSETZER, ModelRole.PRUEFER]
    assert roles.calls == [] and result["iteration_counts"].count(ModelRole.CHEF_FINAL) == 0


@pytest.mark.parametrize("router_output", [
    "kein json",
    "```json\n" + minimal_route_json() + "\n```",
    json.dumps({"schema_version": 1}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": True,
                "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG",
                "extra": True}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": True,
                "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG",
                "ziel_agent": "CHEF_FINAL"}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": False, "tester": False, "pruefer": True,
                "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG"}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": False,
                "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG"}),
    json.dumps({"schema_version": 2, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": True,
                "complexity": "EINFACH", "reason_code": "DIREKTE_UMSETZUNG"}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": True,
                "complexity": "EXTREM", "reason_code": "DIREKTE_UMSETZUNG"}),
    json.dumps({"schema_version": 1, "planer": False, "analyst": False,
                "umsetzer": True, "tester": False, "pruefer": True,
                "complexity": "EINFACH", "reason_code": "FREI"}),
])
def test_invalid_router_response_fails_after_exactly_one_fake_request(router_output: str) -> None:
    result, client, roles = _execute(router_output, [], hard=10)
    assert result["status"] == "fehlgeschlagen"
    assert _roles(client) == [ModelRole.CHEF_ROUTER]
    assert result["actual_call_count"] == 1 and roles.calls == []
    assert result["events"][-1]["node"] == CONTROLLED_FAILURE


def test_route_budget_is_checked_after_router_and_blocks_all_later_requests() -> None:
    result, client, _ = _execute(full_route_json(), _full_success_responses(), hard=4)
    assert result["status"] == "fehlgeschlagen"
    assert result["required_call_budget"] == 6
    assert result["actual_call_count"] == 1
    assert _roles(client) == [ModelRole.CHEF_ROUTER]


def test_tester_correction_e2e_has_eight_requests_and_replaces_implementation() -> None:
    responses = [completed_response("Plan v1"), completed_response("Analyse v1"),
        completed_response("Umsetzung v1"),
        completed_response(_tester("FEHLER", "UMSETZUNG", ["Korrigieren"])),
        completed_response("Umsetzung v2"), completed_response(_tester()), completed_response(_review())]
    result, client, _ = _execute(full_route_json(), responses, hard=8, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG}))
    assert _roles(client) == [ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER,
                              ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert len(client.responses.call_history) == 8 and result["actual_call_count"] == 8
    assert result["global_correction_count"] == 1 and result["implementation_result"] == "Umsetzung v2"
    assert "Umsetzung v1" not in client.responses.captured_requests[5]["input"]
    assert "Umsetzung v2" in client.responses.captured_requests[6]["input"]


@pytest.mark.parametrize(("origin", "path", "budget", "downstream"), [
    (ReviewOrigin.PLANUNG, CorrectionPathName.PRUEFER_PLANUNG, 11,
     [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.ANALYSE, CorrectionPathName.PRUEFER_ANALYSE, 10,
     [ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.UMSETZUNG, CorrectionPathName.PRUEFER_UMSETZUNG, 9,
     [ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.TEST, CorrectionPathName.PRUEFER_TEST, 8, [ModelRole.TESTER, ModelRole.PRUEFER]),
])
def test_all_reviewer_correction_paths_are_end_to_end(origin, path, budget, downstream) -> None:
    base = [completed_response("Plan v1"), completed_response("Analyse v1"), completed_response("Umsetzung v1"),
            completed_response(_tester()), completed_response(_review("ABGELEHNT", origin.value, ["Korrigieren"]))]
    next_values = {
        ReviewOrigin.PLANUNG: ["Plan v2", "Analyse v2", "Umsetzung v2", _tester(), _review()],
        ReviewOrigin.ANALYSE: ["Analyse v2", "Umsetzung v2", _tester(), _review()],
        ReviewOrigin.UMSETZUNG: ["Umsetzung v2", _tester(), _review()],
        ReviewOrigin.TEST: [_tester(), _review()],
    }[origin]
    result, client, _ = _execute(full_route_json(), base + [completed_response(x) for x in next_values],
        hard=budget, corrections=1, allowed=frozenset({path}))
    assert _roles(client) == [ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER,
                              ModelRole.TESTER, ModelRole.PRUEFER] + downstream
    assert result["actual_call_count"] == budget and result["status"] == "erfolgreich"
    if origin is ReviewOrigin.PLANUNG:
        assert result["planning_result"] == "Plan v2"
    if origin in {ReviewOrigin.PLANUNG, ReviewOrigin.ANALYSE}:
        assert result["analysis_result"] == "Analyse v2"
    if origin is not ReviewOrigin.TEST:
        assert result["implementation_result"] == "Umsetzung v2"
    assert result["testing_result"].entscheidung.value == "BESTANDEN"
    assert result["review_result"].entscheidung.value == "AKZEPTIERT"
    assert result["current_feedback"] == "" and result["feedback_origin"] is None
    if origin is ReviewOrigin.UMSETZUNG:
        second_implementer = [item["input"] for item in client.responses.captured_requests
                              if item["instructions"] == UMSETZER_SYSTEM_PROMPT][1]
        assert second_implementer.count("Korrigieren") == 1


def test_unclear_review_e2e_fails_without_chef_final() -> None:
    responses = _full_success_responses()[:-1] + [completed_response(_review("UNKLAR", "UNKLAR"))]
    result, client, roles = _execute(full_route_json(), responses, hard=6)
    assert result["status"] == "fehlgeschlagen" and len(client.responses.call_history) == 6
    assert roles.calls == []
    assert result["events"][-1]["node"] == CONTROLLED_FAILURE


@pytest.mark.parametrize("failed_role", [
    ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER,
])
def test_incomplete_max_tokens_at_each_role_stops_all_later_requests(failed_role) -> None:
    sequence = _full_success_responses()
    index = [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER].index(failed_role)
    sequence[index] = incomplete_response("PARTIAL_MUST_NOT_REACH_STATE")
    result, client, _ = _execute(full_route_json(), sequence, hard=6)
    assert result["status"] == "fehlgeschlagen"
    assert len(client.responses.call_history) == index + 2
    assert "PARTIAL_MUST_NOT_REACH_STATE" not in str(result)
    assert result["actual_call_count"] == index + 2  # CHEF_ROUTER plus attempted adapter calls


@pytest.mark.parametrize(("index", "response"), [
    (2, {"status": "failed", "output_text": "PARTIAL", "output": [], "usage": {}}),
    (1, {"status": "completed", "output_text": "", "output": [{"type": "reasoning"}], "usage": {}}),
    (3, completed_response("kein tester-json")),
    (4, completed_response("kein review-json")),
    (4, completed_response(_review(ziel_agent="CHEF_FINAL"))),
])
def test_failed_textless_invalid_and_injected_responses_stop_e2e(index, response) -> None:
    sequence = _full_success_responses()
    sequence[index] = response
    result, client, roles = _execute(full_route_json(), sequence, hard=6)
    assert result["status"] == "fehlgeschlagen" and len(client.responses.call_history) == index + 2
    assert roles.calls == []
    assert result["events"][-1]["node"] == CONTROLLED_FAILURE


def test_usage_totals_are_exact_without_bridge_or_adapter_double_counting() -> None:
    result, client, roles = _execute(full_route_json(), _full_success_responses(tokens=True), hard=6)
    adapter_usage = [item for item in result["usage"] if item["provider"] == "openai-six-agent"]
    chef_usage = [item for item in result["usage"] if item["provider"] == "deterministic-offline"]
    assert len(adapter_usage) == len(client.responses.call_history) == 6
    assert [item["gesamt_tokens"] for item in adapter_usage] == [0, 10, 20, 30, 40, 50]
    assert [item["input_tokens"] for item in adapter_usage] == [0, 5, 10, 15, 20, 25]
    assert [item["output_tokens"] for item in adapter_usage] == [0, 5, 10, 15, 20, 25]
    assert sum(item["gesamt_tokens"] for item in adapter_usage) == 150
    assert chef_usage == [] and roles.calls == []
    assert result["actual_call_count"] == len(client.responses.call_history) == 6


def test_large_audit_and_usage_history_do_not_change_any_e2e_request_input() -> None:
    def execute(events=None, usage=None):
        _, client, _ = _execute(full_route_json(), _full_success_responses(), hard=6,
            initial_events=events, initial_usage=usage)
        return [item["input"] for item in client.responses.captured_requests]
    assert execute() == execute([{"audit": "x" * 10000}] * 100, [{"tokens": 999999}] * 100)


@pytest.mark.parametrize("failed_index", [2, 4])
def test_secret_markers_never_reach_failure_state_events_or_trace(failed_index, capsys) -> None:
    markers = ("TOP_SECRET_PLAN", "TOP_SECRET_USER", "sk-test-secret", "RESPONSE_TEXT_SECRET")
    secret = " ".join(markers)
    sequence = _full_success_responses()
    sequence[failed_index] = incomplete_response(secret)
    result, client, _ = _execute(full_route_json(), sequence, hard=6, request=secret)
    trace = capsys.readouterr().out
    safe_surface = result["failure_reason"] + json.dumps(result["events"]) + trace
    assert all(marker not in safe_surface for marker in markers)
    assert secret in client.responses.captured_requests[0]["input"]  # internal test object only


def test_every_e2e_generate_produces_exactly_one_fake_create() -> None:
    result, client, roles = _execute(full_route_json(), _full_success_responses(), hard=6)
    assert len(client.responses.call_history) == 6
    assert result["actual_call_count"] == 6 and roles.calls == []
    assert len(client.responses.captured_requests) == 6


def test_bridge_e2e_demo_runs_entirely_offline() -> None:
    completed = subprocess.run([sys.executable, str(SRC_DIR / "six_agent_bridge_e2e_demo.py")],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=15, check=False)
    assert completed.returncode == 0
    assert "fake_requests=8" in completed.stdout and "actual_call_count=8" in completed.stdout
    assert "global_correction_count=1" in completed.stdout and "[E2E] FERTIG" in completed.stdout
