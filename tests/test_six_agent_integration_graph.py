from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import six_agent_integration_graph as integration_module  # noqa: E402
from route_budget import CorrectionPathName, RoleLimits  # noqa: E402
from six_agent_contracts import IMPLEMENTER_MAX_CHARS  # noqa: E402
from six_agent_graph import full_route_json, minimal_route_json  # noqa: E402
from six_agent_integration_graph import (  # noqa: E402
    CONTROLLED_FAILURE, DeterministicIntegrationRoles, IntegrationGraphConfig,
    build_six_agent_integration_graph, run_six_agent_integration_workflow,
)
from six_agent_role_adapter import AdapterGenerationResult, AdapterUsageData, DeterministicRoleProvider  # noqa: E402
from six_agent_state import ModelRole, create_initial_six_agent_state  # noqa: E402
from structured_routing import (  # noqa: E402
    ReviewFailureOrigin as ReviewOrigin, TesterDecision as TDecision,
    target_for_failure_origin, validate_chef_route,
)


def _tester_json(decision="BESTANDEN", origin="UNKLAR", improvements=None) -> str:
    return json.dumps({"entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Tester-Begründung", "verbesserungen": [] if improvements is None else improvements})


def _review_json(decision="AKZEPTIERT", origin="UNKLAR", improvements=None, **extra) -> str:
    return json.dumps({"entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Review-Begründung", "verbesserungen": [] if improvements is None else improvements, **extra})


def _provider(*, routers=(), planners=(), analysts=(), implementers=(), testers=(), reviewers=()):
    configured = {}
    for role, values in ((ModelRole.CHEF_ROUTER, routers), (ModelRole.PLANER, planners), (ModelRole.ANALYST, analysts),
                         (ModelRole.UMSETZER, implementers), (ModelRole.TESTER, testers),
                         (ModelRole.PRUEFER, reviewers)):
        if values:
            configured[role] = list(values)
    return DeterministicRoleProvider(configured)


def _run(route_text, provider, *, hard, corrections=0, allowed=frozenset(),
         limits=RoleLimits(), initial_events=None, initial_usage=None):
    provider.responses.setdefault(ModelRole.CHEF_ROUTER, [route_text])
    roles = DeterministicIntegrationRoles()
    config = IntegrationGraphConfig(hard_max_model_calls=hard, role_limits=limits,
        global_correction_limit=corrections, allowed_correction_paths=allowed)
    result = run_six_agent_integration_workflow("Integrationsauftrag", provider, roles, config,
        initial_events=initial_events, initial_usage=initial_usage)
    return result, roles


def _history(provider):
    return [item.role for item in provider.call_history]


def _nodes(result):
    return [event["node"] for event in result["events"] if "node" in event]


def _assert_counts(result, provider, roles):
    assert result["actual_call_count"] == len(provider.call_history)
    assert roles.calls == []
    for role in ModelRole:
        assert result["iteration_counts"].count(role) == _history(provider).count(role)


def test_minimal_path_uses_only_implementer_and_reviewer_adapters() -> None:
    provider = _provider(implementers=("Umsetzung",), reviewers=(_review_json(),))
    result, roles = _run(minimal_route_json(), provider, hard=3)
    assert _history(provider) == [ModelRole.CHEF_ROUTER, ModelRole.UMSETZER, ModelRole.PRUEFER]
    assert roles.calls == []
    assert _nodes(result) == [ModelRole.CHEF_ROUTER.value, ModelRole.UMSETZER.value,
                              ModelRole.PRUEFER.value, "FINALIZATION"]
    assert result["actual_call_count"] == result["required_call_budget"] == 3
    assert result["iteration_counts"].count(ModelRole.CHEF_FINAL) == 0
    _assert_counts(result, provider, roles)


def test_full_path_uses_all_five_adapters_once_without_double_counting() -> None:
    provider = _provider(planners=("Plan v1",), analysts=("Analyse v1",), implementers=("Umsetzung v1",),
        testers=(_tester_json(),), reviewers=(_review_json(),))
    result, roles = _run(full_route_json(), provider, hard=6)
    expected = [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert _history(provider) == [ModelRole.CHEF_ROUTER] + expected
    assert roles.calls == []
    assert result["actual_call_count"] == result["required_call_budget"] == 6
    assert _nodes(result) == [ModelRole.CHEF_ROUTER.value] + [r.value for r in expected] + ["FINALIZATION"]
    _assert_counts(result, provider, roles)


def test_kolay_kickoff_uses_route_d_once_and_finalizes_without_model_call() -> None:
    request = (
        "Plane und analysiere den technischen Start des Projekts KOLAY. Definiere "
        "Architektur, zentrale Komponenten, Abhängigkeiten, Risiken und einen umsetzbaren "
        "ersten Entwicklungsschritt. Danach soll eine erste technische Umsetzung erstellt, "
        "getestet und unabhängig geprüft werden."
    )
    provider = _provider(
        routers=(full_route_json(),), planners=("KOLAY-Plan",),
        analysts=("KOLAY-Analyse",), implementers=("KOLAY-Erstumsetzung",),
        testers=(_tester_json(),), reviewers=(_review_json(),),
    )
    roles = DeterministicIntegrationRoles()
    config = IntegrationGraphConfig(
        hard_max_model_calls=6,
        global_correction_limit=0,
        allowed_correction_paths=frozenset(),
    )
    result = run_six_agent_integration_workflow(request, provider, roles, config)
    expected = [
        ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST,
        ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER,
    ]
    assert _history(provider) == expected
    assert result["required_call_budget"] == result["actual_call_count"] == 6
    assert len(result["usage"]) == 6 and result["global_correction_count"] == 0
    assert result["review_result"].entscheidung.value == "AKZEPTIERT"
    assert result["status"] == "erfolgreich" and result["final_answer"] == "KOLAY-Erstumsetzung"
    assert result["iteration_counts"].count(ModelRole.CHEF_FINAL) == 0
    assert _nodes(result) == [role.value for role in expected] + ["FINALIZATION"]
    router_input = provider.captured_requests[0][2]
    assert request in router_input
    assert all(marker not in request.lower() for marker in (
        "planer=true", "analyst=true", "umsetzer=true", "tester=true", "pruefer=true",
    ))
    _assert_counts(result, provider, roles)


@pytest.mark.parametrize("hard_limit", [6, 7, 20])
def test_route_d_actual_workflow_stays_at_six_when_hard_limit_is_sufficient(hard_limit) -> None:
    provider = _provider(
        planners=("P",), analysts=("A",), implementers=("U",),
        testers=(_tester_json(),), reviewers=(_review_json(),),
    )
    result, roles = _run(full_route_json(), provider, hard=hard_limit)
    assert result["status"] == "erfolgreich"
    assert result["required_call_budget"] == result["actual_call_count"] == 6
    assert len(provider.call_history) == len(result["usage"]) == 6
    assert result["global_correction_count"] == 0
    assert result["iteration_counts"].count(ModelRole.CHEF_FINAL) == 0
    _assert_counts(result, provider, roles)


def test_tester_implementation_correction_exact_order_and_replacement() -> None:
    provider = _provider(planners=("Plan v1",), analysts=("Analyse v1",),
        implementers=("Umsetzung v1", "Umsetzung v2"),
        testers=(_tester_json("FEHLER", "UMSETZUNG", ["Umsetzung korrigieren"]), _tester_json()),
        reviewers=(_review_json(),))
    result, roles = _run(full_route_json(), provider, hard=8, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG}))
    expected = [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER,
                ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert _history(provider) == [ModelRole.CHEF_ROUTER] + expected
    assert result["actual_call_count"] == 8 and result["global_correction_count"] == 1
    assert result["implementation_result"] == "Umsetzung v2"
    assert result["testing_result"].entscheidung is TDecision.BESTANDEN
    assert result["review_result"].entscheidung.value == "AKZEPTIERT"
    second_implementer_input = [text for role, _, text in provider.captured_requests if role is ModelRole.UMSETZER][1]
    second_tester_input = [text for role, _, text in provider.captured_requests if role is ModelRole.TESTER][1]
    reviewer_input = [text for role, _, text in provider.captured_requests if role is ModelRole.PRUEFER][0]
    assert "Umsetzung v1" not in second_implementer_input
    assert "Umsetzung v2" in second_tester_input and "Umsetzung v1" not in second_tester_input
    assert "Umsetzung v2" in reviewer_input and "Umsetzung v1" not in reviewer_input
    _assert_counts(result, provider, roles)


@pytest.mark.parametrize(("origin", "path", "budget", "expected"), [
    (ReviewOrigin.PLANUNG, CorrectionPathName.PRUEFER_PLANUNG, 11,
     [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.ANALYSE, CorrectionPathName.PRUEFER_ANALYSE, 10,
     [ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.UMSETZUNG, CorrectionPathName.PRUEFER_UMSETZUNG, 9,
     [ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]),
    (ReviewOrigin.TEST, CorrectionPathName.PRUEFER_TEST, 8, [ModelRole.TESTER, ModelRole.PRUEFER]),
])
def test_reviewer_corrections_rerun_only_required_adapter_path(origin, path, budget, expected) -> None:
    pc = 2 if origin is ReviewOrigin.PLANUNG else 1
    ac = 2 if origin in {ReviewOrigin.PLANUNG, ReviewOrigin.ANALYSE} else 1
    uc = 2 if origin in {ReviewOrigin.PLANUNG, ReviewOrigin.ANALYSE, ReviewOrigin.UMSETZUNG} else 1
    provider = _provider(planners=tuple(f"Plan v{i+1}" for i in range(pc)),
        analysts=tuple(f"Analyse v{i+1}" for i in range(ac)),
        implementers=tuple(f"Umsetzung v{i+1}" for i in range(uc)),
        testers=(_tester_json(), _tester_json()),
        reviewers=(_review_json("ABGELEHNT", origin.value, [f"Feedback-{origin.value}"]), _review_json()))
    result, roles = _run(full_route_json(), provider, hard=budget, corrections=1, allowed=frozenset({path}))
    base = [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert _history(provider) == [ModelRole.CHEF_ROUTER] + base + expected
    assert result["actual_call_count"] == result["required_call_budget"] == budget
    assert result["planning_result"] == f"Plan v{pc}"
    assert result["analysis_result"] == f"Analyse v{ac}"
    assert result["implementation_result"] == f"Umsetzung v{uc}"
    assert result["testing_result"].entscheidung is TDecision.BESTANDEN
    assert result["review_result"].entscheidung.value == "AKZEPTIERT"
    assert result["current_feedback"] == "" and result["feedback_origin"] is None
    _assert_counts(result, provider, roles)


def test_feedback_reaches_only_matching_adapter_contract() -> None:
    scenarios = [(ReviewOrigin.PLANUNG, CorrectionPathName.PRUEFER_PLANUNG, 11, ModelRole.PLANER),
                 (ReviewOrigin.ANALYSE, CorrectionPathName.PRUEFER_ANALYSE, 10, ModelRole.ANALYST),
                 (ReviewOrigin.UMSETZUNG, CorrectionPathName.PRUEFER_UMSETZUNG, 9, ModelRole.UMSETZER),
                 (ReviewOrigin.TEST, CorrectionPathName.PRUEFER_TEST, 8, None)]
    for origin, path, budget, receiver in scenarios:
        marker = f"Nur-{origin.value}-Feedback"
        provider = _provider(planners=("P1", "P2"), analysts=("A1", "A2"), implementers=("U1", "U2"),
            testers=(_tester_json(), _tester_json()),
            reviewers=(_review_json("ABGELEHNT", origin.value, [marker]), _review_json()))
        _run(full_route_json(), provider, hard=budget, corrections=1, allowed=frozenset({path}))
        receivers = [role for role, _, text in provider.captured_requests if marker in text]
        assert receivers == ([] if receiver is None else [receiver])


def test_reviewer_unclear_routes_to_controlled_failure_without_final() -> None:
    provider = _provider(planners=("P",), analysts=("A",), implementers=("U",),
        testers=(_tester_json(),), reviewers=(_review_json("UNKLAR", "UNKLAR"),))
    result, roles = _run(full_route_json(), provider, hard=6)
    assert result["status"] == "fehlgeschlagen" and _nodes(result)[-1] == CONTROLLED_FAILURE
    assert roles.calls == []
    assert result["actual_call_count"] == 6


def test_review_routing_uses_validated_result_and_target_function(monkeypatch) -> None:
    calls = []
    def tracking(origin):
        calls.append(origin)
        return target_for_failure_origin(origin)
    monkeypatch.setattr(integration_module, "target_for_failure_origin", tracking)
    provider = _provider(planners=("P",), analysts=("A1", "A2"), implementers=("U1", "U2"),
        testers=(_tester_json(), _tester_json()),
        reviewers=(_review_json("ABGELEHNT", "ANALYSE", ["Korrigieren"]), _review_json()))
    result, _ = _run(full_route_json(), provider, hard=10, corrections=1,
        allowed=frozenset({CorrectionPathName.PRUEFER_ANALYSE}))
    assert calls == [ReviewOrigin.ANALYSE] and result["status"] == "erfolgreich"


def test_reviewer_target_injection_fails_before_graph_routing() -> None:
    provider = _provider(implementers=("U",), reviewers=(_review_json(ziel_agent="CHEF_FINAL"),))
    result, roles = _run(minimal_route_json(), provider, hard=3)
    assert result["status"] == "fehlgeschlagen"
    assert _history(provider) == [ModelRole.CHEF_ROUTER, ModelRole.UMSETZER, ModelRole.PRUEFER]
    assert roles.calls == [] and result["actual_call_count"] == 3
    assert _nodes(result)[-1] == CONTROLLED_FAILURE


@pytest.mark.parametrize(("role", "response"), [
    (ModelRole.UMSETZER, RuntimeError("intern")), (ModelRole.UMSETZER, ""),
    (ModelRole.UMSETZER, "x" * (IMPLEMENTER_MAX_CHARS + 1)),
    (ModelRole.PRUEFER, RuntimeError("intern")), (ModelRole.PRUEFER, "kein json"),
    (ModelRole.PRUEFER, _review_json(extra="unbekannt")),
    (ModelRole.PRUEFER, _review_json(decision="AKZEPTIERT", origin="PLANUNG")),
])
def test_new_adapter_failures_stop_graph_after_one_attempt(role, response) -> None:
    provider = _provider(implementers=((response,) if role is ModelRole.UMSETZER else ("U",)),
        reviewers=((response,) if role is ModelRole.PRUEFER else (_review_json(),)))
    result, roles = _run(minimal_route_json(), provider, hard=3)
    assert result["status"] == "fehlgeschlagen" and _history(provider).count(role) == 1
    assert len(provider.call_history) == result["actual_call_count"] and roles.calls == []
    assert _nodes(result)[-1] == CONTROLLED_FAILURE


def test_hard_limit_too_small_blocks_before_first_adapter() -> None:
    provider = _provider(planners=("P",), analysts=("A",), implementers=("U",),
        testers=(_tester_json(),), reviewers=(_review_json(),))
    result, roles = _run(full_route_json(), provider, hard=4)
    assert _history(provider) == [ModelRole.CHEF_ROUTER] and roles.calls == []
    assert result["actual_call_count"] == 1 and result["status"] == "fehlgeschlagen"
    assert result["required_call_budget"] == 6
    assert result["chef_route"].planer and result["chef_route"].analyst


def test_unbudgeted_tester_correction_blocks_before_reviewer() -> None:
    provider = _provider(planners=("P",), analysts=("A",), implementers=("U1", "U2"),
        testers=(_tester_json("FEHLER", "UMSETZUNG", ["x"]), _tester_json()), reviewers=(_review_json(),))
    result, _ = _run(full_route_json(), provider, hard=6, corrections=1)
    assert result["required_call_budget"] == result["actual_call_count"] == 6
    assert ModelRole.PRUEFER not in _history(provider) and result["status"] == "fehlgeschlagen"


def _run_with_preused_role(role):
    route = validate_chef_route(minimal_route_json())
    limits = RoleLimits(umsetzer=1, pruefer=1)
    config = IntegrationGraphConfig(hard_max_model_calls=3, role_limits=limits,
        global_correction_limit=0, allowed_correction_paths=frozenset())
    provider = _provider(implementers=("U",), reviewers=(_review_json(),))
    roles = DeterministicIntegrationRoles()
    provider.responses[ModelRole.CHEF_ROUTER] = [minimal_route_json()]
    state = create_initial_six_agent_state("preused", "Auftrag", hard_max_model_calls=3)
    state["iteration_counts"] = state["iteration_counts"].increment(role, 1)
    return build_six_agent_integration_graph(provider, roles, config).invoke(state), provider


@pytest.mark.parametrize("role", [ModelRole.UMSETZER, ModelRole.PRUEFER])
def test_new_role_limits_block_before_provider(role) -> None:
    result, provider = _run_with_preused_role(role)
    assert result["status"] == "fehlgeschlagen" and _history(provider).count(role) == 0


def test_global_correction_limit_blocks_second_loop_before_target_adapter() -> None:
    provider = _provider(planners=("P1", "P2"), analysts=("A1", "A2"), implementers=("U1", "U2"),
        testers=(_tester_json("FEHLER", "UMSETZUNG", ["x"]), _tester_json()),
        reviewers=(_review_json("ABGELEHNT", "PLANUNG", ["y"]),))
    result, _ = _run(full_route_json(), provider, hard=11, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG, CorrectionPathName.PRUEFER_PLANUNG}))
    assert result["status"] == "fehlgeschlagen" and result["global_correction_count"] == 1
    assert _history(provider).count(ModelRole.PLANER) == 1


def test_usage_and_events_are_exactly_once_per_model_call() -> None:
    def generated(role, text, tokens):
        return AdapterGenerationResult(text, AdapterUsageData(role.value, input_tokens=tokens, total_tokens=tokens))
    provider = _provider(planners=(generated(ModelRole.PLANER, "P", 1),),
        analysts=(generated(ModelRole.ANALYST, "A", 2),),
        implementers=(generated(ModelRole.UMSETZER, "U", 3),),
        testers=(generated(ModelRole.TESTER, _tester_json(), 4),),
        reviewers=(generated(ModelRole.PRUEFER, _review_json(), 5),))
    result, roles = _run(full_route_json(), provider, hard=6)
    assert len(result["events"]) == result["actual_call_count"] + 1 == 7
    assert len(result["usage"]) == result["actual_call_count"] == 6
    assert _nodes(result) == [ModelRole.CHEF_ROUTER.value, ModelRole.PLANER.value, ModelRole.ANALYST.value,
        ModelRole.UMSETZER.value, ModelRole.TESTER.value, ModelRole.PRUEFER.value, "FINALIZATION"]
    adapter_usage = [x for x in result["usage"] if x["provider"] == "fake-role-adapter"]
    deterministic = [x for x in result["usage"] if x["provider"] == "deterministic-offline"]
    assert len(adapter_usage) == 6 and sum(int(x["gesamt_tokens"]) for x in adapter_usage) == 15
    assert deterministic == [] and roles.calls == []


def test_large_initial_history_does_not_change_any_adapter_input() -> None:
    def execute(events=None, usage=None):
        provider = _provider(planners=("P",), analysts=("A",), implementers=("U",),
            testers=(_tester_json(),), reviewers=(_review_json(),))
        _run(full_route_json(), provider, hard=6, initial_events=events, initial_usage=usage)
        return [(x.role, x.user_input_chars) for x in provider.call_history], [x[2] for x in provider.captured_requests]
    assert execute() == execute([{"audit": "x" * 10000}] * 100, [{"tokens": 999999}] * 100)


def test_integration_graph_has_no_openai_network_or_production_graph_imports() -> None:
    source = (SRC_DIR / "six_agent_integration_graph.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module)
    assert imports.isdisjoint({"openai", "httpx", "requests", "socket", "llm_provider", "graph", "six_agent_graph", "os"})
    assert "OPENAI_API_KEY" not in source


def test_updated_integration_demo_is_successful() -> None:
    completed = subprocess.run([sys.executable, str(SRC_DIR / "six_agent_integration_demo.py")],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=15, check=False)
    assert completed.returncode == 0
    assert "actual_call_count=8" in completed.stdout and "global_correction_count=1" in completed.stdout
    assert "[6INT-DEMO] FERTIG" in completed.stdout
