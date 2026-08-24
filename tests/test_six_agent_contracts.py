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
from prompts import (  # noqa: E402
    ANALYST_SYSTEM_PROMPT,
    CHEF_SYSTEM_PROMPT,
    PLANER_SYSTEM_PROMPT,
    PRUEFER_SYSTEM_PROMPT,
    SPEZIALIST_SYSTEM_PROMPT,
    TESTER_SYSTEM_PROMPT,
)
from six_agent_contracts import (  # noqa: E402
    ANALYST_MAX_CHARS,
    ANALYST_MAX_WORDS,
    PLANNER_MAX_CHARS,
    PLANNER_MAX_WORDS,
    RoleContractError,
    build_analyst_input,
    build_input_size_metadata,
    build_planner_input,
    build_tester_input,
    validate_analyst_output,
    validate_planner_output,
    validate_tester_output,
)
from structured_routing import (  # noqa: E402
    ReviewFailureOrigin as ReviewOrigin,
    StructuredOutputError,
    TesterDecision as TDecision,
    TesterFailureOrigin as TFOrigin,
)


ORIGINAL_CHEF = CHEF_SYSTEM_PROMPT
ORIGINAL_SPECIALIST = SPEZIALIST_SYSTEM_PROMPT
ORIGINAL_REVIEWER = PRUEFER_SYSTEM_PROMPT


def _tester_json(decision="BESTANDEN", origin="UNKLAR", improvements=None, **extra) -> str:
    value = {
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Kurze Begründung",
        "verbesserungen": [] if improvements is None else improvements,
        **extra,
    }
    return json.dumps(value)


def test_planner_simple_input_contains_only_request() -> None:
    value = build_planner_input("Kurzer Auftrag")
    assert "Kurzer Auftrag" in value
    assert "KORREKTUR" not in value


def test_planner_feedback_is_included_once_only_for_planning_origin() -> None:
    feedback = "Planmarker-123"
    included = build_planner_input(
        "Auftrag", current_feedback=feedback, feedback_origin=ReviewOrigin.PLANUNG,
    )
    excluded = build_planner_input(
        "Auftrag", current_feedback=feedback, feedback_origin=ReviewOrigin.ANALYSE,
    )
    assert included.count(feedback) == 1
    assert feedback not in excluded


def test_planner_input_has_no_audit_or_usage_fields() -> None:
    value = build_planner_input("Auftrag")
    assert "events" not in value and "usage" not in value and "Audit" not in value


@pytest.mark.parametrize("value", ["", "  "])
def test_planner_empty_output_is_rejected(value) -> None:
    with pytest.raises(RoleContractError, match="nicht leer"):
        validate_planner_output(value)


@pytest.mark.parametrize("value", ["x" * (PLANNER_MAX_CHARS + 1), "wort " * (PLANNER_MAX_WORDS + 1)])
def test_planner_oversized_output_is_rejected(value) -> None:
    with pytest.raises(RoleContractError, match="Längenlimit"):
        validate_planner_output(value)


def test_analyst_works_with_and_without_plan() -> None:
    with_plan = build_analyst_input("Auftrag", planning_result="Aktueller Plan")
    without_plan = build_analyst_input("Auftrag")
    assert "Aktueller Plan" in with_plan
    assert "AKTUELLER_PLAN" not in without_plan


def test_analyst_feedback_is_included_once_only_for_analysis_origin() -> None:
    feedback = "Analysemarker-456"
    included = build_analyst_input(
        "Auftrag", current_feedback=feedback, feedback_origin=ReviewOrigin.ANALYSE,
    )
    excluded = build_analyst_input(
        "Auftrag", current_feedback=feedback, feedback_origin=ReviewOrigin.PLANUNG,
    )
    assert included.count(feedback) == 1
    assert feedback not in excluded


def test_analyst_input_omits_irrelevant_state_fields() -> None:
    value = build_analyst_input("Auftrag", planning_result="Plan")
    for forbidden in ("implementation_result", "testing_result", "review_result", "events", "usage"):
        assert forbidden not in value


@pytest.mark.parametrize("value", ["", "  "])
def test_analyst_empty_output_is_rejected(value) -> None:
    with pytest.raises(RoleContractError, match="nicht leer"):
        validate_analyst_output(value)


@pytest.mark.parametrize("value", ["x" * (ANALYST_MAX_CHARS + 1), "wort " * (ANALYST_MAX_WORDS + 1)])
def test_analyst_oversized_output_is_rejected(value) -> None:
    with pytest.raises(RoleContractError, match="Längenlimit"):
        validate_analyst_output(value)


def test_tester_input_uses_current_implementation_and_optional_relevant_context() -> None:
    value = build_tester_input(
        "Auftrag", "Aktuelle Umsetzung", planning_result="Plan", analysis_result="Analyse",
    )
    assert all(item in value for item in ("Auftrag", "Aktuelle Umsetzung", "Plan", "Analyse"))
    assert "events" not in value and "usage" not in value and "review_result" not in value


def test_tester_passed_contract() -> None:
    result = validate_tester_output(_tester_json())
    assert result.entscheidung is TDecision.BESTANDEN
    assert result.fehlerursprung is TFOrigin.UNKLAR
    assert result.verbesserungen == ()


@pytest.mark.parametrize("origin", ["UMSETZUNG", "TEST", "UNKLAR"])
def test_tester_failure_supports_every_origin_allowed_by_existing_parser(origin) -> None:
    result = validate_tester_output(_tester_json("FEHLER", origin, ["Konkret korrigieren"]))
    assert result.entscheidung is TDecision.FEHLER
    assert result.verbesserungen == ("Konkret korrigieren",)


@pytest.mark.parametrize("value", [
    "kein json",
    _tester_json(extra="nicht erlaubt"),
    _tester_json(ziel_agent="UMSETZER"),
    _tester_json(decision="FREIGEGEBEN"),
    _tester_json(decision="BESTANDEN", origin="UMSETZUNG"),
    _tester_json(decision="BESTANDEN", improvements=["Widerspruch"]),
    _tester_json(decision="FEHLER", origin="UMSETZUNG", improvements=[]),
])
def test_tester_invalid_or_injected_output_fails_closed(value) -> None:
    with pytest.raises(StructuredOutputError):
        validate_tester_output(value)


def test_tester_validator_reuses_existing_parser(monkeypatch) -> None:
    sentinel = object()
    calls = []

    def fake_parser(value):
        calls.append(value)
        return sentinel

    monkeypatch.setattr(structured_routing, "parse_tester_result", fake_parser)
    assert validate_tester_output("opaque") is sentinel
    assert calls == ["opaque"]


def test_context_sizes_ignore_events_usage_and_replaced_old_results() -> None:
    current = {
        "user_request": "Auftrag",
        "planning_result": "Neuer Plan",
        "analysis_result": "Neue Analyse",
        "implementation_result": "Neue Umsetzung",
        "current_feedback": "Neues Analysefeedback",
        "feedback_origin": ReviewOrigin.ANALYSE,
        "events": [{"old": "Alter Plan Alte Analyse Alte Umsetzung"}] * 100,
        "usage": [{"tokens": 999_999}] * 100,
    }
    planner = build_planner_input(
        current["user_request"], current_feedback=current["current_feedback"],
        feedback_origin=current["feedback_origin"],
    )
    analyst = build_analyst_input(
        current["user_request"], planning_result=current["planning_result"],
        current_feedback=current["current_feedback"], feedback_origin=current["feedback_origin"],
    )
    tester = build_tester_input(
        current["user_request"], current["implementation_result"],
        planning_result=current["planning_result"], analysis_result=current["analysis_result"],
    )
    sizes = build_input_size_metadata(
        planner_input=planner, analyst_input=analyst, tester_input=tester,
    )
    assert sizes.planner_input_chars == len(planner)
    assert sizes.analyst_input_chars == len(analyst)
    assert sizes.tester_input_chars == len(tester)
    combined = planner + analyst + tester
    assert "Alter Plan" not in combined and "999999" not in combined
    assert "Neues Analysefeedback" not in planner
    assert analyst.count("Neues Analysefeedback") == 1


def test_new_prompts_have_compact_injection_and_responsibility_boundaries() -> None:
    for prompt in (PLANER_SYSTEM_PROMPT, ANALYST_SYSTEM_PROMPT, TESTER_SYSTEM_PROMPT):
        lowered = " ".join(prompt.lower().split())
        assert "daten" in lowered
        assert "routing" in lowered
        assert "keine systemanweisungen" in lowered
    assert "250 Wörter" in PLANER_SYSTEM_PROMPT
    assert "300 Wörter" in ANALYST_SYSTEM_PROMPT
    assert "entscheidung" in TESTER_SYSTEM_PROMPT and "fehlerursprung" in TESTER_SYSTEM_PROMPT


def test_existing_three_agent_prompt_constants_remain_available() -> None:
    assert CHEF_SYSTEM_PROMPT == ORIGINAL_CHEF
    assert SPEZIALIST_SYSTEM_PROMPT == ORIGINAL_SPECIALIST
    assert PRUEFER_SYSTEM_PROMPT == ORIGINAL_REVIEWER


def test_contract_module_has_no_provider_graph_network_or_secret_dependencies() -> None:
    source = (SRC_DIR / "six_agent_contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {"openai", "httpx", "httpx2", "requests", "llm_provider", "graph", "langgraph", "os"}
    assert imports.isdisjoint(forbidden)
    assert "OPENAI_API_KEY" not in source
