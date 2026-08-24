from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class StructuredOutputError(ValueError):
    """Fail-closed error that never includes the rejected model output."""


class Complexity(str, Enum):
    EINFACH = "EINFACH"
    MITTEL = "MITTEL"
    KOMPLEX = "KOMPLEX"


class ChefReasonCode(str, Enum):
    DIREKTE_UMSETZUNG = "DIREKTE_UMSETZUNG"
    PLANUNG_ERFORDERLICH = "PLANUNG_ERFORDERLICH"
    ANALYSE_ERFORDERLICH = "ANALYSE_ERFORDERLICH"
    VOLLSTAENDIGE_BEARBEITUNG = "VOLLSTAENDIGE_BEARBEITUNG"


class TesterDecision(str, Enum):
    BESTANDEN = "BESTANDEN"
    FEHLER = "FEHLER"


class ReviewDecision(str, Enum):
    AKZEPTIERT = "AKZEPTIERT"
    ABGELEHNT = "ABGELEHNT"
    UNKLAR = "UNKLAR"


class TesterFailureOrigin(str, Enum):
    UMSETZUNG = "UMSETZUNG"
    TEST = "TEST"
    UNKLAR = "UNKLAR"


class ReviewFailureOrigin(str, Enum):
    PLANUNG = "PLANUNG"
    ANALYSE = "ANALYSE"
    UMSETZUNG = "UMSETZUNG"
    TEST = "TEST"
    UNKLAR = "UNKLAR"


class RoutingTarget(str, Enum):
    PLANER = "PLANER"
    ANALYST = "ANALYST"
    UMSETZER = "UMSETZER"
    TESTER = "TESTER"
    CONTROLLED_FAILURE = "CONTROLLED_FAILURE"


@dataclass(frozen=True)
class ChefRoute:
    schema_version: int
    planer: bool
    analyst: bool
    umsetzer: bool
    tester: bool
    pruefer: bool
    complexity: Complexity
    reason_code: ChefReasonCode


@dataclass(frozen=True)
class TesterResult:
    entscheidung: TesterDecision
    fehlerursprung: TesterFailureOrigin
    begruendung: str
    verbesserungen: tuple[str, ...]


@dataclass(frozen=True)
class ReviewResult:
    entscheidung: ReviewDecision
    fehlerursprung: ReviewFailureOrigin
    begruendung: str
    verbesserungen: tuple[str, ...]


def _strict_json_object(text: str, required_fields: set[str]) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StructuredOutputError("Die strukturierte Antwort war kein gültiges JSON-Objekt.") from exc
    if not isinstance(value, dict):
        raise StructuredOutputError("Die strukturierte Antwort muss ein JSON-Objekt sein.")
    fields = set(value)
    unknown = fields - required_fields
    missing = required_fields - fields
    if unknown:
        raise StructuredOutputError("Die strukturierte Antwort enthält unbekannte Felder.")
    if missing:
        raise StructuredOutputError("Der strukturierten Antwort fehlen erforderliche Felder.")
    return value


def _enum_value(enum_type: type[Enum], value: Any, field_name: str):
    if not isinstance(value, str):
        raise StructuredOutputError(f"Das Feld {field_name} muss ein gültiger Enum-Text sein.")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise StructuredOutputError(f"Das Feld {field_name} enthält einen unbekannten Enum-Wert.") from exc


def _nonempty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StructuredOutputError(f"Das Feld {field_name} muss ein nichtleerer Text sein.")
    return value.strip()


def _improvements(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise StructuredOutputError("Das Feld verbesserungen muss eine Liste nichtleerer Texte sein.")
    return tuple(item.strip() for item in value)


def validate_chef_route(text: str) -> ChefRoute:
    fields = {
        "schema_version", "planer", "analyst", "umsetzer", "tester", "pruefer",
        "complexity", "reason_code",
    }
    value = _strict_json_object(text, fields)
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise StructuredOutputError("schema_version muss exakt 1 sein.")
    for field in ("planer", "analyst", "umsetzer", "tester", "pruefer"):
        if type(value[field]) is not bool:
            raise StructuredOutputError(f"Das Feld {field} muss ein Wahrheitswert sein.")
    if not value["umsetzer"]:
        raise StructuredOutputError("UMSETZER ist eine Pflichtrolle.")
    if not value["pruefer"]:
        raise StructuredOutputError("PRÜFER ist eine Pflichtrolle.")
    return ChefRoute(
        schema_version=1,
        planer=value["planer"],
        analyst=value["analyst"],
        umsetzer=True,
        tester=value["tester"],
        pruefer=True,
        complexity=_enum_value(Complexity, value["complexity"], "complexity"),
        reason_code=_enum_value(ChefReasonCode, value["reason_code"], "reason_code"),
    )


def parse_tester_result(text: str) -> TesterResult:
    fields = {"entscheidung", "fehlerursprung", "begruendung", "verbesserungen"}
    value = _strict_json_object(text, fields)
    decision = _enum_value(TesterDecision, value["entscheidung"], "entscheidung")
    origin = _enum_value(TesterFailureOrigin, value["fehlerursprung"], "fehlerursprung")
    improvements = _improvements(value["verbesserungen"])
    if decision is TesterDecision.BESTANDEN and (origin is not TesterFailureOrigin.UNKLAR or improvements):
        raise StructuredOutputError("BESTANDEN darf keine Fehlerursache oder Verbesserungen enthalten.")
    if decision is TesterDecision.FEHLER and not improvements:
        raise StructuredOutputError("FEHLER benötigt mindestens einen Verbesserungshinweis.")
    return TesterResult(decision, origin, _nonempty_text(value["begruendung"], "begruendung"), improvements)


def parse_review_result(text: str) -> ReviewResult:
    fields = {"entscheidung", "fehlerursprung", "begruendung", "verbesserungen"}
    value = _strict_json_object(text, fields)
    decision = _enum_value(ReviewDecision, value["entscheidung"], "entscheidung")
    origin = _enum_value(ReviewFailureOrigin, value["fehlerursprung"], "fehlerursprung")
    improvements = _improvements(value["verbesserungen"])
    if decision is ReviewDecision.AKZEPTIERT and (origin is not ReviewFailureOrigin.UNKLAR or improvements):
        raise StructuredOutputError("AKZEPTIERT darf keine Fehlerursache oder Verbesserungen enthalten.")
    if decision is ReviewDecision.ABGELEHNT and (origin is ReviewFailureOrigin.UNKLAR or not improvements):
        raise StructuredOutputError("ABGELEHNT benötigt eine konkrete Fehlerursache und Verbesserung.")
    if decision is ReviewDecision.UNKLAR and origin is not ReviewFailureOrigin.UNKLAR:
        raise StructuredOutputError("UNKLAR muss die Fehlerursache UNKLAR verwenden.")
    return ReviewResult(decision, origin, _nonempty_text(value["begruendung"], "begruendung"), improvements)


def target_for_failure_origin(origin: ReviewFailureOrigin | TesterFailureOrigin) -> RoutingTarget:
    targets: dict[str, RoutingTarget] = {
        "PLANUNG": RoutingTarget.PLANER,
        "ANALYSE": RoutingTarget.ANALYST,
        "UMSETZUNG": RoutingTarget.UMSETZER,
        "TEST": RoutingTarget.TESTER,
        "UNKLAR": RoutingTarget.CONTROLLED_FAILURE,
    }
    if not isinstance(origin, (ReviewFailureOrigin, TesterFailureOrigin)):
        raise StructuredOutputError("Unbekannte Fehlerursprungsklasse.")
    return targets[origin.value]
