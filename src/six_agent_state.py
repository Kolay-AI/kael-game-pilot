from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from operator import add
from typing import Annotated, Literal, TypedDict

from structured_routing import (
    ChefRoute,
    ReviewFailureOrigin,
    ReviewResult,
    TesterFailureOrigin,
    TesterResult,
)


class SixAgentStateError(ValueError):
    pass


class ModelRole(str, Enum):
    CHEF_ROUTER = "CHEF_ROUTER"
    CHEF_FINAL = "CHEF_FINAL"
    PLANER = "PLANER"
    ANALYST = "ANALYST"
    UMSETZER = "UMSETZER"
    TESTER = "TESTER"
    PRUEFER = "PRÜFER"


@dataclass(frozen=True)
class RoleIterationCounts:
    chef_router: int = 0
    chef_final: int = 0
    planer: int = 0
    analyst: int = 0
    umsetzer: int = 0
    tester: int = 0
    pruefer: int = 0

    def count(self, role: ModelRole) -> int:
        return getattr(self, _ROLE_FIELDS[_validated_role(role)])

    def increment(self, role: ModelRole, maximum: int) -> "RoleIterationCounts":
        role = _validated_role(role)
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise SixAgentStateError("Das Rollenlimit muss mindestens 1 sein.")
        field = _ROLE_FIELDS[role]
        current = getattr(self, field)
        if current >= maximum:
            raise SixAgentStateError(f"Das Rollenlimit für {role.value} ist erreicht.")
        return replace(self, **{field: current + 1})


def _validated_role(role: ModelRole) -> ModelRole:
    if not isinstance(role, ModelRole):
        raise SixAgentStateError("Unbekannte Modellrolle.")
    return role


_ROLE_FIELDS = {
    ModelRole.CHEF_ROUTER: "chef_router",
    ModelRole.CHEF_FINAL: "chef_final",
    ModelRole.PLANER: "planer",
    ModelRole.ANALYST: "analyst",
    ModelRole.UMSETZER: "umsetzer",
    ModelRole.TESTER: "tester",
    ModelRole.PRUEFER: "pruefer",
}


SixAgentStatus = Literal["vorbereitet", "laeuft", "erfolgreich", "fehlgeschlagen"]


class SixAgentWorkflowState(TypedDict):
    workflow_id: str
    user_request: str

    chef_route: ChefRoute | None
    current_agent: ModelRole | None
    next_agent: ModelRole | None

    planning_result: str
    analysis_result: str
    implementation_result: str
    testing_result: TesterResult | None
    review_result: ReviewResult | None

    current_feedback: str
    feedback_origin: ReviewFailureOrigin | TesterFailureOrigin | None

    iteration_counts: RoleIterationCounts
    global_correction_count: int

    required_call_budget: int
    actual_call_count: int
    hard_max_model_calls: int

    status: SixAgentStatus
    final_answer: str
    failure_reason: str

    events: Annotated[list[dict[str, object]], add]
    usage: Annotated[list[dict[str, object]], add]
    usage_summary: dict[str, int]


def create_initial_six_agent_state(
    workflow_id: str,
    user_request: str,
    *,
    hard_max_model_calls: int,
) -> SixAgentWorkflowState:
    if not workflow_id or not user_request.strip():
        raise SixAgentStateError("Workflow-ID und Benutzerauftrag dürfen nicht leer sein.")
    if hard_max_model_calls < 1:
        raise SixAgentStateError("Die harte Modellaufrufgrenze muss mindestens 1 sein.")
    return {
        "workflow_id": workflow_id,
        "user_request": user_request,
        "chef_route": None,
        "current_agent": None,
        "next_agent": None,
        "planning_result": "",
        "analysis_result": "",
        "implementation_result": "",
        "testing_result": None,
        "review_result": None,
        "current_feedback": "",
        "feedback_origin": None,
        "iteration_counts": RoleIterationCounts(),
        "global_correction_count": 0,
        "required_call_budget": 0,
        "actual_call_count": 0,
        "hard_max_model_calls": hard_max_model_calls,
        "status": "vorbereitet",
        "final_answer": "",
        "failure_reason": "",
        "events": [],
        "usage": [],
        "usage_summary": {},
    }
