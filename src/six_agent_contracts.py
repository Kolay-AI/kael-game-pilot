from __future__ import annotations

import json
from dataclasses import dataclass
from math import ceil

import structured_routing
from structured_routing import (
    ChefRoute,
    ReviewDecision,
    ReviewFailureOrigin,
    ReviewResult,
    TesterFailureOrigin,
    TesterResult,
)


PLANNER_MAX_WORDS = 250
PLANNER_MAX_CHARS = 2_000
ANALYST_MAX_WORDS = 300
ANALYST_MAX_CHARS = 2_400
IMPLEMENTER_MAX_WORDS = 800
IMPLEMENTER_MAX_CHARS = 6_400
CHEF_FINAL_MAX_WORDS = IMPLEMENTER_MAX_WORDS
CHEF_FINAL_MAX_CHARS = IMPLEMENTER_MAX_CHARS
CHEF_FINAL_MAX_GROWTH_RATIO = 1.10
CHEF_FINAL_CHAR_FORMAT_ALLOWANCE = 80
CHEF_FINAL_WORD_FORMAT_ALLOWANCE = 15


class RoleContractError(ValueError):
    """Safe validation failure that does not echo rejected role output."""


@dataclass(frozen=True)
class InputSizeMetadata:
    planner_input_chars: int
    analyst_input_chars: int
    tester_input_chars: int
    implementer_input_chars: int = 0
    reviewer_input_chars: int = 0
    chef_router_input_chars: int = 0
    chef_final_input_chars: int = 0


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoleContractError(f"{field_name} darf nicht leer sein.")
    return value.strip()


def _optional_text(value: str) -> str:
    if not isinstance(value, str):
        raise RoleContractError("Optionale Rollenfelder müssen Text sein.")
    return value.strip()


def _section(label: str, value: str) -> str:
    return f"[{label}]\n{value}\n[/{label}]"


def build_chef_router_input(user_request: str) -> str:
    return _section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag"))


def validate_chef_router_output(output: str) -> ChefRoute:
    # Reuse the one existing strict route validator; no competing schema or routing.
    return structured_routing.validate_chef_route(output)


def build_chef_final_input(
    user_request: str,
    implementation_result: str,
    review_result: ReviewResult,
) -> str:
    if not isinstance(review_result, ReviewResult):
        raise RoleContractError("CHEF_FINAL benötigt ein gültiges ReviewResult.")
    if review_result.entscheidung is not ReviewDecision.AKZEPTIERT:
        raise RoleContractError("CHEF_FINAL darf nur ein akzeptiertes Ergebnis erhalten.")
    return "\n\n".join((
        _section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag")),
        _section("AKZEPTIERTE_UMSETZUNG", _required_text(
            implementation_result, "Akzeptierte Umsetzung",
        )),
        _section("PRUEFSTATUS", "AKZEPTIERT"),
    ))


def build_planner_input(
    user_request: str,
    *,
    current_feedback: str = "",
    feedback_origin: ReviewFailureOrigin | None = None,
) -> str:
    sections = [_section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag"))]
    feedback = _optional_text(current_feedback)
    if feedback and feedback_origin is ReviewFailureOrigin.PLANUNG:
        sections.append(_section("AKTUELLE_PLANUNGSKORREKTUR", feedback))
    return "\n\n".join(sections)


def build_analyst_input(
    user_request: str,
    *,
    planning_result: str = "",
    current_feedback: str = "",
    feedback_origin: ReviewFailureOrigin | None = None,
) -> str:
    sections = [_section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag"))]
    plan = _optional_text(planning_result)
    if plan:
        sections.append(_section("AKTUELLER_PLAN", plan))
    feedback = _optional_text(current_feedback)
    if feedback and feedback_origin is ReviewFailureOrigin.ANALYSE:
        sections.append(_section("AKTUELLE_ANALYSEKORREKTUR", feedback))
    return "\n\n".join(sections)


def build_tester_input(
    user_request: str,
    implementation_result: str,
    *,
    planning_result: str = "",
    analysis_result: str = "",
) -> str:
    sections = [
        _section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag")),
    ]
    plan = _optional_text(planning_result)
    analysis = _optional_text(analysis_result)
    if plan:
        sections.append(_section("RELEVANTER_PLAN", plan))
    if analysis:
        sections.append(_section("RELEVANTE_ANALYSE", analysis))
    sections.append(_section("AKTUELLE_UMSETZUNG", _required_text(implementation_result, "Umsetzung")))
    return "\n\n".join(sections)


def build_implementer_input(
    user_request: str,
    *,
    planning_result: str = "",
    analysis_result: str = "",
    current_feedback: str = "",
    feedback_origin: ReviewFailureOrigin | TesterFailureOrigin | None = None,
) -> str:
    sections = [_section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag"))]
    plan = _optional_text(planning_result)
    analysis = _optional_text(analysis_result)
    if plan:
        sections.append(_section("AKTUELLER_PLAN", plan))
    if analysis:
        sections.append(_section("AKTUELLE_ANALYSE", analysis))
    feedback = _optional_text(current_feedback)
    if feedback and feedback_origin in {
        ReviewFailureOrigin.UMSETZUNG,
        TesterFailureOrigin.UMSETZUNG,
    }:
        sections.append(_section("AKTUELLES_UMSETZUNGSFEEDBACK", feedback))
    return "\n\n".join(sections)


def _testing_result_text(result: TesterResult) -> str:
    if not isinstance(result, TesterResult):
        raise RoleContractError("Das aktuelle Testergebnis besitzt keinen gültigen Vertrag.")
    return json.dumps({
        "entscheidung": result.entscheidung.value,
        "fehlerursprung": result.fehlerursprung.value,
        "begruendung": result.begruendung,
        "verbesserungen": list(result.verbesserungen),
    }, ensure_ascii=False, separators=(",", ":"))


def build_reviewer_input(
    user_request: str,
    implementation_result: str,
    *,
    planning_result: str = "",
    analysis_result: str = "",
    testing_result: TesterResult | None = None,
) -> str:
    sections = [_section("BENUTZERAUFTRAG", _required_text(user_request, "Benutzerauftrag"))]
    plan = _optional_text(planning_result)
    analysis = _optional_text(analysis_result)
    if plan:
        sections.append(_section("AKTUELLER_PLAN", plan))
    if analysis:
        sections.append(_section("AKTUELLE_ANALYSE", analysis))
    sections.append(_section("AKTUELLE_UMSETZUNG", _required_text(implementation_result, "Umsetzung")))
    if testing_result is not None:
        sections.append(_section("AKTUELLES_TESTERGEBNIS", _testing_result_text(testing_result)))
    return "\n\n".join(sections)


def _validate_bounded_text(output: str, *, role: str, max_words: int, max_chars: int) -> str:
    if not isinstance(output, str) or not output.strip():
        raise RoleContractError(f"Die {role}-Ausgabe darf nicht leer sein.")
    value = output.strip()
    if len(value) > max_chars or len(value.split()) > max_words:
        raise RoleContractError(
            f"Die {role}-Ausgabe überschreitet das zulässige Längenlimit."
        )
    return value


def validate_planner_output(output: str) -> str:
    return _validate_bounded_text(
        output, role="PLANER", max_words=PLANNER_MAX_WORDS, max_chars=PLANNER_MAX_CHARS,
    )


def validate_analyst_output(output: str) -> str:
    return _validate_bounded_text(
        output, role="ANALYST", max_words=ANALYST_MAX_WORDS, max_chars=ANALYST_MAX_CHARS,
    )


def validate_implementer_output(output: str) -> str:
    return _validate_bounded_text(
        output, role="UMSETZER", max_words=IMPLEMENTER_MAX_WORDS,
        max_chars=IMPLEMENTER_MAX_CHARS,
    )


def validate_chef_final_output(output: str, implementation_result: str) -> str:
    source = _required_text(implementation_result, "Akzeptierte Umsetzung")
    value = _validate_bounded_text(
        output, role="CHEF_FINAL", max_words=CHEF_FINAL_MAX_WORDS,
        max_chars=CHEF_FINAL_MAX_CHARS,
    )
    max_chars = min(
        CHEF_FINAL_MAX_CHARS,
        ceil(len(source) * CHEF_FINAL_MAX_GROWTH_RATIO) + CHEF_FINAL_CHAR_FORMAT_ALLOWANCE,
    )
    source_words = len(source.split())
    max_words = min(
        CHEF_FINAL_MAX_WORDS,
        ceil(source_words * CHEF_FINAL_MAX_GROWTH_RATIO) + CHEF_FINAL_WORD_FORMAT_ALLOWANCE,
    )
    if len(value) > max_chars or len(value.split()) > max_words:
        raise RoleContractError(
            "Die CHEF_FINAL-Ausgabe wächst gegenüber der akzeptierten Umsetzung zu stark."
        )
    return value


def validate_tester_output(output: str) -> TesterResult:
    # Deliberately reuse the one existing strict parser; no competing schema.
    return structured_routing.parse_tester_result(output)


def validate_reviewer_output(output: str) -> ReviewResult:
    # Deliberately reuse the one existing strict review parser and routing vocabulary.
    return structured_routing.parse_review_result(output)


def build_input_size_metadata(
    *, planner_input: str, analyst_input: str, tester_input: str,
    implementer_input: str = "", reviewer_input: str = "",
    chef_router_input: str = "", chef_final_input: str = "",
) -> InputSizeMetadata:
    return InputSizeMetadata(
        planner_input_chars=len(planner_input),
        analyst_input_chars=len(analyst_input),
        tester_input_chars=len(tester_input),
        implementer_input_chars=len(implementer_input),
        reviewer_input_chars=len(reviewer_input),
        chef_router_input_chars=len(chef_router_input),
        chef_final_input_chars=len(chef_final_input),
    )
