from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from structured_routing import (  # noqa: E402
    ChefReasonCode,
    Complexity,
    ReviewDecision,
    ReviewFailureOrigin,
    RoutingTarget,
    StructuredOutputError,
    TesterDecision as DecisionForTester,
    parse_review_result,
    parse_tester_result,
    target_for_failure_origin,
    validate_chef_route,
)


def _chef(**updates):
    value = {
        "schema_version": 1,
        "planer": False,
        "analyst": False,
        "umsetzer": True,
        "tester": False,
        "pruefer": True,
        "complexity": "EINFACH",
        "reason_code": "DIREKTE_UMSETZUNG",
    }
    value.update(updates)
    return json.dumps(value)


def _tester(decision="BESTANDEN", origin="UNKLAR", improvements=None, **updates):
    value = {
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Strukturierte Testbegründung.",
        "verbesserungen": [] if improvements is None else improvements,
    }
    value.update(updates)
    return json.dumps(value)


def _review(decision="AKZEPTIERT", origin="UNKLAR", improvements=None, **updates):
    value = {
        "entscheidung": decision,
        "fehlerursprung": origin,
        "begruendung": "Strukturierte Prüfbegründung.",
        "verbesserungen": [] if improvements is None else improvements,
    }
    value.update(updates)
    return json.dumps(value)


def test_valid_minimal_chef_route() -> None:
    route = validate_chef_route(_chef())
    assert route.complexity is Complexity.EINFACH
    assert route.reason_code is ChefReasonCode.DIREKTE_UMSETZUNG
    assert not route.planer and not route.analyst and not route.tester
    assert route.umsetzer and route.pruefer


def test_valid_full_chef_route() -> None:
    route = validate_chef_route(_chef(
        planer=True, analyst=True, tester=True, complexity="KOMPLEX",
        reason_code="VOLLSTAENDIGE_BEARBEITUNG",
    ))
    assert route.planer and route.analyst and route.tester


@pytest.mark.parametrize(("reason_code", "planer", "analyst"), [
    ("DIREKTE_UMSETZUNG", False, False),
    ("PLANUNG_ERFORDERLICH", True, False),
    ("ANALYSE_ERFORDERLICH", False, True),
    ("VOLLSTAENDIGE_BEARBEITUNG", True, True),
])
@pytest.mark.parametrize("tester", [False, True])
def test_reason_code_has_exact_role_flags_while_tester_remains_optional(
    reason_code: str, planer: bool, analyst: bool, tester: bool,
) -> None:
    route = validate_chef_route(_chef(
        reason_code=reason_code, planer=planer, analyst=analyst, tester=tester,
    ))
    assert (route.planer, route.analyst, route.tester) == (planer, analyst, tester)


@pytest.mark.parametrize(("reason_code", "planer", "analyst"), [
    ("DIREKTE_UMSETZUNG", True, False),
    ("DIREKTE_UMSETZUNG", False, True),
    ("PLANUNG_ERFORDERLICH", False, False),
    ("PLANUNG_ERFORDERLICH", True, True),
    ("ANALYSE_ERFORDERLICH", False, False),
    ("ANALYSE_ERFORDERLICH", True, True),
    ("VOLLSTAENDIGE_BEARBEITUNG", False, True),
    ("VOLLSTAENDIGE_BEARBEITUNG", True, False),
])
def test_contradictory_reason_code_and_role_flags_fail_closed(
    reason_code: str, planer: bool, analyst: bool,
) -> None:
    with pytest.raises(StructuredOutputError, match="widersprüchlich"):
        validate_chef_route(_chef(
            reason_code=reason_code, planer=planer, analyst=analyst,
        ))


def test_router_enum_vocabulary_is_unchanged() -> None:
    assert [item.value for item in Complexity] == ["EINFACH", "MITTEL", "KOMPLEX"]
    assert [item.value for item in ChefReasonCode] == [
        "DIREKTE_UMSETZUNG", "PLANUNG_ERFORDERLICH",
        "ANALYSE_ERFORDERLICH", "VOLLSTAENDIGE_BEARBEITUNG",
    ]


@pytest.mark.parametrize("field", ["umsetzer", "pruefer"])
def test_required_chef_roles_cannot_be_disabled(field: str) -> None:
    with pytest.raises(StructuredOutputError, match="Pflichtrolle"):
        validate_chef_route(_chef(**{field: False}))


def test_unknown_chef_field_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="unbekannte Felder"):
        validate_chef_route(_chef(next_agent="FREMDAGENT"))


def test_wrong_schema_version_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="exakt 1"):
        validate_chef_route(_chef(schema_version=2))


@pytest.mark.parametrize(("field", "value"), [("complexity", "RIESIG"), ("reason_code", "FREITEXT")])
def test_unknown_chef_enums_are_rejected(field: str, value: str) -> None:
    with pytest.raises(StructuredOutputError, match="unbekannten Enum-Wert"):
        validate_chef_route(_chef(**{field: value}))


def test_broken_chef_json_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="kein gültiges JSON"):
        validate_chef_route("{")


def test_tester_passed_is_valid() -> None:
    result = parse_tester_result(_tester())
    assert result.entscheidung is DecisionForTester.BESTANDEN


@pytest.mark.parametrize(("origin", "target"), [
    ("UMSETZUNG", RoutingTarget.UMSETZER),
    ("TEST", RoutingTarget.TESTER),
])
def test_tester_failure_origins_are_valid(origin: str, target: RoutingTarget) -> None:
    result = parse_tester_result(_tester("FEHLER", origin, ["Korrigieren"]))
    assert result.entscheidung is DecisionForTester.FEHLER
    assert target_for_failure_origin(result.fehlerursprung) is target


@pytest.mark.parametrize(("field", "value"), [("entscheidung", "NEIN"), ("fehlerursprung", "PLANUNG")])
def test_unknown_tester_enums_are_rejected(field: str, value: str) -> None:
    with pytest.raises(StructuredOutputError):
        parse_tester_result(_tester(**{field: value}))


def test_broken_tester_json_is_rejected() -> None:
    with pytest.raises(StructuredOutputError):
        parse_tester_result("kein JSON")


def test_review_accepted_is_valid() -> None:
    result = parse_review_result(_review())
    assert result.entscheidung is ReviewDecision.AKZEPTIERT


@pytest.mark.parametrize(("origin", "target"), [
    ("PLANUNG", RoutingTarget.PLANER),
    ("ANALYSE", RoutingTarget.ANALYST),
    ("UMSETZUNG", RoutingTarget.UMSETZER),
    ("TEST", RoutingTarget.TESTER),
])
def test_rejected_review_routes_deterministically(origin: str, target: RoutingTarget) -> None:
    result = parse_review_result(_review("ABGELEHNT", origin, ["Korrigieren"]))
    assert target_for_failure_origin(result.fehlerursprung) is target


def test_unclear_review_routes_to_controlled_failure() -> None:
    result = parse_review_result(_review("UNKLAR", "UNKLAR"))
    assert target_for_failure_origin(result.fehlerursprung) is RoutingTarget.CONTROLLED_FAILURE


@pytest.mark.parametrize("text", [
    _review("AKZEPTIERT", "PLANUNG"),
    _review("ABGELEHNT", "UNKLAR", ["Unklar"]),
    _review("ABGELEHNT", "PLANUNG", []),
    _review("UNKLAR", "TEST"),
])
def test_contradictory_review_combinations_are_rejected(text: str) -> None:
    with pytest.raises(StructuredOutputError):
        parse_review_result(text)


def test_unknown_agent_cannot_be_injected_into_review() -> None:
    with pytest.raises(StructuredOutputError, match="unbekannte Felder"):
        parse_review_result(_review(ziel_agent="ANGREIFER"))


def test_unknown_review_field_is_rejected() -> None:
    with pytest.raises(StructuredOutputError, match="unbekannte Felder"):
        parse_review_result(_review(extra="nicht erlaubt"))


def test_invalid_origin_type_cannot_be_routed() -> None:
    with pytest.raises(StructuredOutputError):
        target_for_failure_origin("UMSETZUNG")  # type: ignore[arg-type]


def test_structured_module_has_no_provider_network_or_secret_dependencies() -> None:
    import ast

    source_path = PROJECT_DIR / "src" / "structured_routing.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden = {"openai", "httpx", "httpx2", "requests", "graph", "langgraph", "llm_provider", "os"}
    assert imports.isdisjoint(forbidden)
    source = source_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in source
