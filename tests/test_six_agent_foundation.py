from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from route_budget import (  # noqa: E402
    CorrectionPathName,
    RoleLimits,
    RouteBudgetError,
    calculate_route_budget,
    correction_paths_for_route,
    require_valid_route_budget,
)
from six_agent_state import (  # noqa: E402
    ModelRole,
    RoleIterationCounts,
    SixAgentStateError,
    SixAgentWorkflowState,
    create_initial_six_agent_state,
)
from structured_routing import parse_review_result, parse_tester_result, validate_chef_route  # noqa: E402


def _route(*, planer=False, analyst=False, tester=False):
    return validate_chef_route(json.dumps({
        "schema_version": 1,
        "planer": planer,
        "analyst": analyst,
        "umsetzer": True,
        "tester": tester,
        "pruefer": True,
        "complexity": "KOMPLEX" if any((planer, analyst, tester)) else "EINFACH",
        "reason_code": "VOLLSTAENDIGE_BEARBEITUNG" if any((planer, analyst, tester)) else "DIREKTE_UMSETZUNG",
    }))


def test_initial_six_agent_state_is_valid_and_has_no_messages_history() -> None:
    state = create_initial_six_agent_state("wf-1", "Auftrag", hard_max_model_calls=16)
    assert state["status"] == "vorbereitet"
    assert state["iteration_counts"] == RoleIterationCounts()
    assert "messages" not in state
    assert "messages" not in SixAgentWorkflowState.__annotations__


def test_only_events_and_usage_accumulate_while_domain_fields_replace() -> None:
    initial = create_initial_six_agent_state("wf-2", "Auftrag", hard_max_model_calls=16)
    builder = StateGraph(SixAgentWorkflowState)
    old_test = parse_tester_result(json.dumps({
        "entscheidung": "FEHLER", "fehlerursprung": "UMSETZUNG",
        "begruendung": "Alt", "verbesserungen": ["Alt korrigieren"],
    }))
    new_test = parse_tester_result(json.dumps({
        "entscheidung": "BESTANDEN", "fehlerursprung": "UNKLAR",
        "begruendung": "Neu", "verbesserungen": [],
    }))
    old_review = parse_review_result(json.dumps({
        "entscheidung": "ABGELEHNT", "fehlerursprung": "UMSETZUNG",
        "begruendung": "Alt", "verbesserungen": ["Alt korrigieren"],
    }))
    new_review = parse_review_result(json.dumps({
        "entscheidung": "AKZEPTIERT", "fehlerursprung": "UNKLAR",
        "begruendung": "Neu", "verbesserungen": [],
    }))

    def first(state):
        return {
            "planning_result": "alter Plan",
            "analysis_result": "alte Analyse",
            "implementation_result": "alte Umsetzung",
            "testing_result": old_test,
            "review_result": old_review,
            "current_feedback": "altes Feedback",
            "events": [{"step": 1}],
            "usage": [{"tokens": 1}],
        }

    def second(state):
        return {
            "planning_result": "neuer Plan",
            "analysis_result": "neue Analyse",
            "implementation_result": "neue Umsetzung",
            "testing_result": new_test,
            "review_result": new_review,
            "current_feedback": "neues Feedback",
            "events": [{"step": 2}],
            "usage": [{"tokens": 2}],
        }

    builder.add_node("first", first)
    builder.add_node("second", second)
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)
    result = builder.compile().invoke(initial)
    assert result["planning_result"] == "neuer Plan"
    assert result["analysis_result"] == "neue Analyse"
    assert result["implementation_result"] == "neue Umsetzung"
    assert result["testing_result"] == new_test
    assert result["review_result"] == new_review
    assert result["current_feedback"] == "neues Feedback"
    assert result["events"] == [{"step": 1}, {"step": 2}]
    assert result["usage"] == [{"tokens": 1}, {"tokens": 2}]


def test_role_iteration_counts_increment_and_enforce_limit() -> None:
    counts = RoleIterationCounts().increment(ModelRole.UMSETZER, 1)
    assert counts.count(ModelRole.UMSETZER) == 1
    with pytest.raises(SixAgentStateError, match="erreicht"):
        counts.increment(ModelRole.UMSETZER, 1)


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(SixAgentStateError, match="Unbekannte"):
        RoleIterationCounts().count("FREMDROLLE")  # type: ignore[arg-type]


@pytest.mark.parametrize(("kwargs", "base"), [
    ({}, 4),
    ({"planer": True}, 5),
    ({"analyst": True}, 5),
    ({"tester": True}, 5),
    ({"planer": True, "analyst": True, "tester": True}, 7),
])
def test_base_route_counts_only_selected_roles(kwargs, base: int) -> None:
    budget = calculate_route_budget(_route(**kwargs), hard_max_model_calls=30, global_correction_limit=0)
    assert budget.base_calls == base
    assert budget.correction_calls == 0
    assert budget.required_calls == base


def test_scenario_c_full_route_with_one_tester_correction_is_nine() -> None:
    route = _route(planer=True, analyst=True, tester=True)
    budget = calculate_route_budget(
        route,
        hard_max_model_calls=9,
        global_correction_limit=1,
        allowed_correction_paths=frozenset({CorrectionPathName.TESTER_UMSETZUNG}),
    )
    assert budget.base_calls == 7
    assert budget.correction_calls == 2
    assert budget.required_calls == 9
    assert budget.selected_correction_paths == (CorrectionPathName.TESTER_UMSETZUNG,)
    assert budget.max_http_attempts == 18


@pytest.mark.parametrize(("route", "legacy_calls", "deterministic_final_calls"), [
    (_route(), 4, 3),
    (_route(planer=True, analyst=True, tester=True), 7, 6),
])
def test_deterministic_final_budget_profile_is_additive_and_legacy_is_default(
    route, legacy_calls, deterministic_final_calls,
) -> None:
    legacy = calculate_route_budget(
        route, hard_max_model_calls=30, global_correction_limit=0,
    )
    deterministic = calculate_route_budget(
        route, hard_max_model_calls=30, global_correction_limit=0,
        finalizer_is_model=False,
    )
    assert legacy.required_calls == legacy_calls
    assert deterministic.required_calls == deterministic_final_calls
    assert ModelRole.CHEF_FINAL in legacy.selected_base_roles
    assert ModelRole.CHEF_FINAL not in deterministic.selected_base_roles


@pytest.mark.parametrize(("path", "expected"), [
    (CorrectionPathName.PRUEFER_PLANUNG, 11),
    (CorrectionPathName.PRUEFER_ANALYSE, 10),
    (CorrectionPathName.PRUEFER_UMSETZUNG, 9),
    (CorrectionPathName.PRUEFER_TEST, 8),
    (CorrectionPathName.TESTER_UMSETZUNG, 8),
])
def test_deterministic_final_full_route_correction_budgets(path, expected) -> None:
    budget = calculate_route_budget(
        _route(planer=True, analyst=True, tester=True),
        hard_max_model_calls=30,
        global_correction_limit=1,
        allowed_correction_paths=frozenset({path}),
        finalizer_is_model=False,
        http_attempts_per_call=1,
    )
    assert budget.required_calls == expected
    assert budget.max_http_attempts == expected


def test_scenario_d_respects_shared_role_limits_and_is_fifteen() -> None:
    budget = calculate_route_budget(
        _route(planer=True, analyst=True, tester=True),
        hard_max_model_calls=16,
        global_correction_limit=2,
    )
    assert budget.base_calls == 7
    assert budget.correction_calls == 8
    assert budget.required_calls == 15
    assert budget.max_corrections == 2
    assert set(budget.selected_correction_paths) == {
        CorrectionPathName.PRUEFER_PLANUNG,
        CorrectionPathName.PRUEFER_UMSETZUNG,
    }
    assert budget.max_http_attempts == 30


def test_tester_disabled_is_absent_from_base_and_corrections() -> None:
    route = _route(planer=True, analyst=True, tester=False)
    budget = calculate_route_budget(route, hard_max_model_calls=30)
    assert ModelRole.TESTER not in budget.selected_base_roles
    assert all(ModelRole.TESTER not in path.roles for path in correction_paths_for_route(route))
    assert CorrectionPathName.TESTER_UMSETZUNG not in {path.name for path in correction_paths_for_route(route)}


def test_unreachable_analysis_and_planning_paths_are_not_considered() -> None:
    names = {path.name for path in correction_paths_for_route(_route())}
    assert CorrectionPathName.PRUEFER_ANALYSE not in names
    assert CorrectionPathName.PRUEFER_PLANUNG not in names
    assert CorrectionPathName.PRUEFER_TEST not in names


def test_unclear_has_no_static_correction_path() -> None:
    names = {path.name.value for path in correction_paths_for_route(_route(planer=True, analyst=True, tester=True))}
    assert "UNKLAR" not in names


def test_global_correction_limit_zero_excludes_all_corrections() -> None:
    budget = calculate_route_budget(
        _route(planer=True, analyst=True, tester=True),
        hard_max_model_calls=7,
        global_correction_limit=0,
    )
    assert budget.required_calls == 7
    assert budget.max_corrections == 0


def test_role_limits_exclude_an_individually_too_expensive_combination() -> None:
    limits = RoleLimits(planer=1, analyst=1, umsetzer=2, tester=2, pruefer=2)
    budget = calculate_route_budget(
        _route(planer=True, analyst=True, tester=True), limits=limits,
        hard_max_model_calls=20, global_correction_limit=2,
    )
    assert CorrectionPathName.PRUEFER_PLANUNG not in budget.selected_correction_paths
    assert CorrectionPathName.PRUEFER_ANALYSE not in budget.selected_correction_paths


def test_hard_limit_blocks_and_sufficient_limit_allows() -> None:
    route = _route(planer=True, analyst=True, tester=True)
    blocked = calculate_route_budget(route, hard_max_model_calls=14)
    assert not blocked.valid and blocked.required_calls == 15
    with pytest.raises(RouteBudgetError, match="benötigt bis zu 15.*nur 14"):
        require_valid_route_budget(blocked)
    allowed = calculate_route_budget(route, hard_max_model_calls=15)
    assert require_valid_route_budget(allowed).valid


def test_http_attempt_multiplier_is_deterministic() -> None:
    budget = calculate_route_budget(
        _route(), hard_max_model_calls=20, global_correction_limit=0,
        http_attempts_per_call=2,
    )
    assert budget.required_calls == 4
    assert budget.max_http_attempts == 8


def test_budget_module_has_no_provider_network_secret_or_model_dependencies() -> None:
    source_path = PROJECT_DIR / "src" / "route_budget.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {"openai", "httpx", "httpx2", "requests", "llm_provider", "os", "graph", "langgraph"}
    assert imports.isdisjoint(forbidden)
    assert "OPENAI_API_KEY" not in source
    assert "generate(" not in source
