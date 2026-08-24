from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

import structured_routing  # noqa: E402
from prompts import SIX_AGENT_REVIEWER_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT  # noqa: E402
from six_agent_contracts import (  # noqa: E402
    IMPLEMENTER_MAX_CHARS,
    IMPLEMENTER_MAX_WORDS,
    RoleContractError,
    build_analyst_input,
    build_implementer_input,
    build_input_size_metadata,
    build_planner_input,
    build_reviewer_input,
    build_tester_input,
    validate_implementer_output,
    validate_reviewer_output,
)
from structured_routing import (  # noqa: E402
    ReviewDecision as RDecision,
    ReviewFailureOrigin as ReviewOrigin,
    StructuredOutputError,
    TesterFailureOrigin as TFOrigin,
    parse_tester_result,
)


def _tester_result(decision="BESTANDEN", origin="UNKLAR", improvements=None):
    return parse_tester_result(json.dumps({
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Tester-Marker",
        "verbesserungen": [] if improvements is None else improvements,
    }))


def _review_json(decision="AKZEPTIERT", origin="UNKLAR", improvements=None, **extra) -> str:
    return json.dumps({
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Review-Begründung",
        "verbesserungen": [] if improvements is None else improvements,
        **extra,
    })


@pytest.mark.parametrize(("plan", "analysis"), [
    ("", ""),
    ("Plan-Marker", ""),
    ("", "Analyse-Marker"),
    ("Plan-Marker", "Analyse-Marker"),
])
def test_implementer_input_supports_minimal_plan_analysis_combinations(plan, analysis) -> None:
    value = build_implementer_input(
        "Auftrag-Marker", planning_result=plan, analysis_result=analysis,
    )
    assert value.count("Auftrag-Marker") == 1
    assert ("Plan-Marker" in value) is bool(plan)
    assert ("Analyse-Marker" in value) is bool(analysis)


@pytest.mark.parametrize("origin", [ReviewOrigin.UMSETZUNG, TFOrigin.UMSETZUNG])
def test_implementer_receives_implementation_feedback_once(origin) -> None:
    value = build_implementer_input(
        "Auftrag", current_feedback="Umsetzungsfeedback-Marker", feedback_origin=origin,
    )
    assert value.count("Umsetzungsfeedback-Marker") == 1


@pytest.mark.parametrize("origin", [
    ReviewOrigin.PLANUNG, ReviewOrigin.ANALYSE, ReviewOrigin.TEST,
    TFOrigin.TEST, TFOrigin.UNKLAR, None,
])
def test_implementer_omits_foreign_feedback(origin) -> None:
    value = build_implementer_input(
        "Auftrag", current_feedback="Fremdfeedback-Marker", feedback_origin=origin,
    )
    assert "Fremdfeedback-Marker" not in value


def test_implementer_contract_has_no_history_audit_or_usage_inputs() -> None:
    state = {
        "user_request": "Aktueller Auftrag",
        "planning_result": "Aktueller Plan",
        "analysis_result": "Aktuelle Analyse",
        "current_feedback": "Aktuelles Feedback",
        "feedback_origin": ReviewOrigin.UMSETZUNG,
        "implementation_result": "Alte Umsetzung",
        "testing_result": "Altes Testergebnis",
        "review_result": "Altes Review",
        "events": [{"audit": "Audit-Historie"}],
        "usage": [{"tokens": "Usage-Historie"}],
    }
    value = build_implementer_input(
        state["user_request"], planning_result=state["planning_result"],
        analysis_result=state["analysis_result"], current_feedback=state["current_feedback"],
        feedback_origin=state["feedback_origin"],
    )
    for forbidden in ("Alte Umsetzung", "Altes Testergebnis", "Altes Review", "Audit-Historie", "Usage-Historie"):
        assert forbidden not in value


@pytest.mark.parametrize("output", ["", "  "])
def test_empty_implementer_output_fails_closed(output) -> None:
    with pytest.raises(RoleContractError, match="nicht leer"):
        validate_implementer_output(output)


@pytest.mark.parametrize("output", [
    "x" * (IMPLEMENTER_MAX_CHARS + 1),
    "wort " * (IMPLEMENTER_MAX_WORDS + 1),
])
def test_oversized_implementer_output_fails_closed(output) -> None:
    with pytest.raises(RoleContractError, match="Längenlimit"):
        validate_implementer_output(output)


def test_current_implementer_output_replaces_old_domain_value() -> None:
    state = {"implementation_result": "Umsetzung v1"}
    state["implementation_result"] = validate_implementer_output("Umsetzung v2")
    assert state["implementation_result"] == "Umsetzung v2"
    assert "v1" not in state["implementation_result"]


def test_reviewer_minimal_input_omits_empty_optional_sections() -> None:
    value = build_reviewer_input("Auftrag", "Umsetzung")
    assert value.count("Auftrag") == 1
    assert value.count("Umsetzung") == 1
    assert "AKTUELLER_PLAN" not in value
    assert "AKTUELLE_ANALYSE" not in value
    assert "AKTUELLES_TESTERGEBNIS" not in value


def test_reviewer_full_context_uses_each_current_result_once() -> None:
    tester = _tester_result()
    value = build_reviewer_input(
        "Auftrag-Marker", "Umsetzung-Marker",
        planning_result="Plan-Marker", analysis_result="Analyse-Marker",
        testing_result=tester,
    )
    for marker in ("Auftrag-Marker", "Plan-Marker", "Analyse-Marker", "Umsetzung-Marker", "Tester-Marker"):
        assert value.count(marker) == 1


def test_reviewer_input_excludes_old_review_audit_usage_and_old_implementation() -> None:
    current = {
        "user_request": "Auftrag",
        "planning_result": "Neuer Plan",
        "analysis_result": "Neue Analyse",
        "implementation_result": "Neue Umsetzung",
        "testing_result": _tester_result(),
        "review_result": "Altes Review",
        "events": [{"old": "Alte Umsetzung aus Audit"}] * 100,
        "usage": [{"old": "Usage-Historie"}] * 100,
    }
    value = build_reviewer_input(
        current["user_request"], current["implementation_result"],
        planning_result=current["planning_result"], analysis_result=current["analysis_result"],
        testing_result=current["testing_result"],
    )
    for forbidden in ("Altes Review", "Alte Umsetzung", "Usage-Historie"):
        assert forbidden not in value


def test_reviewer_acceptance_contract() -> None:
    result = validate_reviewer_output(_review_json())
    assert result.entscheidung is RDecision.AKZEPTIERT
    assert result.fehlerursprung is ReviewOrigin.UNKLAR
    assert result.verbesserungen == ()


@pytest.mark.parametrize("origin", ["PLANUNG", "ANALYSE", "UMSETZUNG", "TEST"])
def test_reviewer_rejection_supports_every_concrete_existing_origin(origin) -> None:
    result = validate_reviewer_output(_review_json("ABGELEHNT", origin, ["Konkret korrigieren"]))
    assert result.entscheidung is RDecision.ABGELEHNT
    assert result.fehlerursprung.value == origin
    assert result.verbesserungen == ("Konkret korrigieren",)


def test_reviewer_unclear_matches_existing_contract() -> None:
    result = validate_reviewer_output(_review_json("UNKLAR", "UNKLAR"))
    assert result.entscheidung is RDecision.UNKLAR
    assert result.fehlerursprung is ReviewOrigin.UNKLAR


@pytest.mark.parametrize("output", [
    "kein json",
    _review_json(extra="unbekannt"),
    _review_json(ziel_agent="PLANER"),
    _review_json(decision="FREIGEGEBEN"),
    _review_json(decision="ABGELEHNT", origin="QUELLE", improvements=["x"]),
    _review_json(decision="AKZEPTIERT", origin="PLANUNG"),
    _review_json(decision="AKZEPTIERT", improvements=["Widerspruch"]),
    _review_json(decision="ABGELEHNT", origin="UMSETZUNG", improvements=[]),
    json.dumps({"entscheidung": "AKZEPTIERT"}),
])
def test_reviewer_invalid_injected_or_contradictory_output_fails_closed(output) -> None:
    with pytest.raises(StructuredOutputError):
        validate_reviewer_output(output)


def test_reviewer_validator_reuses_existing_parse_review_result(monkeypatch) -> None:
    sentinel = object()
    calls = []

    def fake_parser(value):
        calls.append(value)
        return sentinel

    monkeypatch.setattr(structured_routing, "parse_review_result", fake_parser)
    assert validate_reviewer_output("opaque") is sentinel
    assert calls == ["opaque"]


def test_input_size_metadata_includes_implementer_and_reviewer_without_contents() -> None:
    implementer = build_implementer_input("Auftrag", planning_result="Plan")
    reviewer = build_reviewer_input("Auftrag", "Umsetzung", testing_result=_tester_result())
    sizes = build_input_size_metadata(
        planner_input="p", analyst_input="a", tester_input="t",
        implementer_input=implementer, reviewer_input=reviewer,
    )
    assert sizes.implementer_input_chars == len(implementer)
    assert sizes.reviewer_input_chars == len(reviewer)
    assert not hasattr(sizes, "implementer_input")


def test_events_and_usage_growth_do_not_change_new_contract_input_sizes() -> None:
    def inputs(state):
        implementer = build_implementer_input(
            state["user_request"], planning_result=state["planning_result"],
            analysis_result=state["analysis_result"], current_feedback=state["current_feedback"],
            feedback_origin=state["feedback_origin"],
        )
        reviewer = build_reviewer_input(
            state["user_request"], state["implementation_result"],
            planning_result=state["planning_result"], analysis_result=state["analysis_result"],
            testing_result=state["testing_result"],
        )
        return implementer, reviewer

    base = {
        "user_request": "Auftrag", "planning_result": "Plan", "analysis_result": "Analyse",
        "implementation_result": "Umsetzung", "testing_result": _tester_result(),
        "current_feedback": "Feedback", "feedback_origin": ReviewOrigin.UMSETZUNG,
        "events": [], "usage": [],
    }
    enlarged = dict(base)
    enlarged["events"] = [{"large": "x" * 10_000}] * 100
    enlarged["usage"] = [{"tokens": 999_999}] * 100
    assert inputs(base) == inputs(enlarged)
    assert tuple(map(len, inputs(base))) == tuple(map(len, inputs(enlarged)))


def test_current_contract_data_flow_reaches_reviewer_without_history_or_routing() -> None:
    user_request = "Aktueller Auftrag"
    planner_input = build_planner_input(user_request)
    planning_result = "Aktueller Plan"
    analyst_input = build_analyst_input(user_request, planning_result=planning_result)
    analysis_result = "Aktuelle Analyse"
    implementer_input = build_implementer_input(
        user_request, planning_result=planning_result, analysis_result=analysis_result,
    )
    implementation_result = "Aktuelle Umsetzung"
    tester_input = build_tester_input(
        user_request, implementation_result,
        planning_result=planning_result, analysis_result=analysis_result,
    )
    testing_result = _tester_result()
    reviewer_input = build_reviewer_input(
        user_request, implementation_result,
        planning_result=planning_result, analysis_result=analysis_result,
        testing_result=testing_result,
    )
    assert user_request in planner_input
    assert planning_result in analyst_input and planning_result in implementer_input
    assert analysis_result in implementer_input and analysis_result in tester_input
    assert implementation_result in tester_input and implementation_result in reviewer_input
    assert "Tester-Marker" in reviewer_input
    assert "ziel_agent" not in reviewer_input and "events" not in reviewer_input and "usage" not in reviewer_input


def test_new_prompts_define_compact_injection_and_role_boundaries() -> None:
    for prompt in (UMSETZER_SYSTEM_PROMPT, SIX_AGENT_REVIEWER_SYSTEM_PROMPT):
        normalized = " ".join(prompt.lower().split())
        assert "arbeitsdaten" in normalized
        assert "keine systemanweisungen" in normalized
        assert "routing" in normalized
        assert "sicherheits" in normalized
    assert "800 Wörter" in UMSETZER_SYSTEM_PROMPT
    assert all(value in SIX_AGENT_REVIEWER_SYSTEM_PROMPT for value in (
        "AKZEPTIERT", "ABGELEHNT", "UNKLAR", "PLANUNG", "ANALYSE", "UMSETZUNG", "TEST",
    ))


def test_contract_module_still_has_no_provider_graph_network_or_secret_dependencies() -> None:
    source = (SRC_DIR / "six_agent_contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports.isdisjoint({
        "openai", "httpx", "httpx2", "requests", "socket", "llm_provider",
        "graph", "six_agent_graph", "six_agent_integration_graph", "langgraph", "os",
    })
    assert "OPENAI_API_KEY" not in source
