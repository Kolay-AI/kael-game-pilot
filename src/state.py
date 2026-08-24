from __future__ import annotations

from operator import add
from typing import Annotated, Literal, TypedDict


Decision = Literal["", "AKZEPTIERT", "ABGELEHNT"]
Status = Literal["laeuft", "erfolgreich", "fehlgeschlagen"]


class WorkflowState(TypedDict):
    workflow_id: str
    user_request: str
    work_order: str
    specialist_answer: str
    feedback: str
    decision: Decision
    review_round: int
    max_rounds: int
    status: Status
    final_answer: str
    events: Annotated[list[dict[str, object]], add]
    usage: Annotated[list[dict[str, object]], add]
    usage_summary: dict[str, int]
