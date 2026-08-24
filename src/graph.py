from __future__ import annotations

from pathlib import Path
from threading import Lock
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agents import make_chef, make_failure, make_reviewer, make_specialist
from audit_log import AuditLogger
from config import AppConfig, validate_model_call_budget
from llm_provider import LLMProvider, LogicalCallLimitProvider, create_provider
from state import WorkflowState


_WORKFLOW_LOCK = Lock()


class WorkflowBusyError(RuntimeError):
    pass


def summarize_usage(items: list[dict[str, object]]) -> dict[str, int]:
    return {
        "api_aufrufe": sum(1 for item in items if item.get("provider") == "openai"),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in items),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in items),
        "gesamt_tokens": sum(int(item.get("gesamt_tokens", 0)) for item in items),
    }


def _after_chef(state: WorkflowState) -> str:
    return "ende" if state["status"] == "erfolgreich" else "spezialist"


def _after_review(state: WorkflowState) -> str:
    if state["decision"] == "AKZEPTIERT":
        return "chef"
    if state["review_round"] >= state["max_rounds"]:
        return "abbruch"
    return "spezialist"


def build_graph(logger: AuditLogger, provider: LLMProvider, config: AppConfig):
    builder = StateGraph(WorkflowState)
    builder.add_node("chef", make_chef(logger, provider, config))
    builder.add_node("spezialist", make_specialist(logger, provider, config))
    builder.add_node("pruefer", make_reviewer(logger, provider, config))
    builder.add_node("abbruch", make_failure(logger))
    builder.add_edge(START, "chef")
    builder.add_conditional_edges("chef", _after_chef, {"spezialist": "spezialist", "ende": END})
    builder.add_edge("spezialist", "pruefer")
    builder.add_conditional_edges(
        "pruefer",
        _after_review,
        {"chef": "chef", "spezialist": "spezialist", "abbruch": "abbruch"},
    )
    builder.add_edge("abbruch", END)
    return builder.compile()


def run_workflow(
    user_request: str,
    log_dir: Path,
    max_rounds: int | None = None,
    provider: LLMProvider | None = None,
    config: AppConfig | None = None,
) -> tuple[WorkflowState, Path | None]:
    if not _WORKFLOW_LOCK.acquire(blocking=False):
        raise WorkflowBusyError("Es läuft bereits ein Workflow; Parallelstarts sind gesperrt.")
    try:
        config = config or AppConfig()
        effective_rounds = max_rounds if max_rounds is not None else config.max_review_cycles
        required_calls = validate_model_call_budget(effective_rounds, config.hard_max_model_calls)
        provider = provider or create_provider(config)
        workflow_id = uuid4().hex
        logger = AuditLogger(log_dir, workflow_id=workflow_id, enabled=config.logging_enabled)
        bounded_provider = LogicalCallLimitProvider(provider, maximum=required_calls)
        graph = build_graph(logger, bounded_provider, config)
        initial_state: WorkflowState = {
            "workflow_id": workflow_id,
            "user_request": user_request,
            "work_order": "",
            "specialist_answer": "",
            "feedback": "",
            "decision": "",
            "review_round": 0,
            "max_rounds": effective_rounds,
            "status": "laeuft",
            "final_answer": "",
            "events": [],
            "usage": [],
            "usage_summary": {},
        }
        print("[START] Workflow wird gestartet", flush=True)
        result = graph.invoke(initial_state)
        result["usage_summary"] = summarize_usage(result["usage"])
        return result, logger.path
    finally:
        _WORKFLOW_LOCK.release()
