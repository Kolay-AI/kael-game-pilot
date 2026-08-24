from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from langgraph.graph import END, START, StateGraph

from route_budget import (
    DEFAULT_GLOBAL_CORRECTION_LIMIT,
    DEFAULT_ROLE_LIMITS,
    CorrectionPathName,
    RoleLimits,
    RouteBudgetError,
    calculate_route_budget,
    require_valid_route_budget,
)
from six_agent_state import (
    ModelRole,
    RoleIterationCounts,
    SixAgentStateError,
    SixAgentWorkflowState,
    create_initial_six_agent_state,
)
from structured_routing import (
    ChefRoute,
    ReviewDecision,
    ReviewFailureOrigin,
    ReviewResult,
    RoutingTarget,
    StructuredOutputError,
    TesterDecision,
    TesterFailureOrigin,
    TesterResult,
    target_for_failure_origin,
    validate_chef_route,
)


CONTROLLED_FAILURE = "CONTROLLED_FAILURE"


def minimal_route_json() -> str:
    return json.dumps({
        "schema_version": 1,
        "planer": False,
        "analyst": False,
        "umsetzer": True,
        "tester": False,
        "pruefer": True,
        "complexity": "EINFACH",
        "reason_code": "DIREKTE_UMSETZUNG",
    })


def full_route_json() -> str:
    return json.dumps({
        "schema_version": 1,
        "planer": True,
        "analyst": True,
        "umsetzer": True,
        "tester": True,
        "pruefer": True,
        "complexity": "KOMPLEX",
        "reason_code": "VOLLSTAENDIGE_BEARBEITUNG",
    })


def tester_passed(reason: str = "Fake-Test bestanden") -> TesterResult:
    return TesterResult(TesterDecision.BESTANDEN, TesterFailureOrigin.UNKLAR, reason, ())


def tester_failed(origin: TesterFailureOrigin, feedback: str = "Fake-Korrektur erforderlich") -> TesterResult:
    return TesterResult(TesterDecision.FEHLER, origin, "Fake-Testfehler", (feedback,))


def review_accepted(reason: str = "Fake-Prüfung akzeptiert") -> ReviewResult:
    return ReviewResult(ReviewDecision.AKZEPTIERT, ReviewFailureOrigin.UNKLAR, reason, ())


def review_rejected(origin: ReviewFailureOrigin, feedback: str = "Fake-Korrektur erforderlich") -> ReviewResult:
    return ReviewResult(ReviewDecision.ABGELEHNT, origin, "Fake-Prüfung abgelehnt", (feedback,))


def review_unclear() -> ReviewResult:
    return ReviewResult(ReviewDecision.UNKLAR, ReviewFailureOrigin.UNKLAR, "Fake-Ergebnis unklar", ())


@dataclass
class FakeSixAgentProvider:
    """Deterministic local provider. It has no network or OpenAI dependency."""

    route_text: str
    tester_results: tuple[TesterResult, ...] = ()
    review_results: tuple[ReviewResult, ...] = ()
    calls: list[ModelRole] = field(default_factory=list)

    def generate(self, role: ModelRole) -> object:
        self.calls.append(role)
        occurrence = self.calls.count(role)
        if role is ModelRole.CHEF_ROUTER:
            return self.route_text
        if role is ModelRole.PLANER:
            return f"Fake-Plan-v{occurrence}"
        if role is ModelRole.ANALYST:
            return f"Fake-Analyse-v{occurrence}"
        if role is ModelRole.UMSETZER:
            return f"Fake-Umsetzung-v{occurrence}"
        if role is ModelRole.TESTER:
            index = occurrence - 1
            return self.tester_results[index] if index < len(self.tester_results) else tester_passed()
        if role is ModelRole.PRUEFER:
            index = occurrence - 1
            return self.review_results[index] if index < len(self.review_results) else review_accepted()
        if role is ModelRole.CHEF_FINAL:
            return "Fake-Endergebnis"
        raise ValueError("Unbekannte Fake-Rolle.")


@dataclass(frozen=True)
class SixAgentGraphConfig:
    hard_max_model_calls: int
    role_limits: RoleLimits = DEFAULT_ROLE_LIMITS
    global_correction_limit: int = DEFAULT_GLOBAL_CORRECTION_LIMIT
    allowed_correction_paths: frozenset[CorrectionPathName] | None = None


def _event(node: str, state: SixAgentWorkflowState, **details: object) -> dict[str, object]:
    return {
        "node": node,
        "call": state["actual_call_count"],
        "corrections": state["global_correction_count"],
        **details,
    }


def _usage(role: ModelRole, call_number: int) -> dict[str, object]:
    return {"provider": "fake-six-agent", "role": role.value, "call": call_number, "tokens": 0}


def _failure(state: SixAgentWorkflowState, error_class: str, reason: str) -> dict[str, object]:
    return {
        "status": "fehlgeschlagen",
        "failure_reason": reason,
        "next_agent": None,
    }


def _role_available(state: SixAgentWorkflowState, role: ModelRole, config: SixAgentGraphConfig) -> tuple[bool, str]:
    if state["actual_call_count"] + 1 > state["required_call_budget"]:
        return False, "Das berechnete Modellaufrufbudget würde überschritten."
    if state["actual_call_count"] + 1 > state["hard_max_model_calls"]:
        return False, "Die harte Modellaufrufgrenze würde überschritten."
    if state["iteration_counts"].count(role) >= config.role_limits.limit_for(role):
        return False, f"Das Rollenlimit für {role.value} ist erreicht."
    return True, ""


def _begin_role(
    state: SixAgentWorkflowState,
    role: ModelRole,
    provider: FakeSixAgentProvider,
    config: SixAgentGraphConfig,
) -> tuple[object | None, dict[str, object] | None, RoleIterationCounts | None, int]:
    available, reason = _role_available(state, role, config)
    if not available:
        return None, _failure(state, "AUFRUFGRENZE", reason), None, state["actual_call_count"]
    try:
        counts = state["iteration_counts"].increment(role, config.role_limits.limit_for(role))
    except (SixAgentStateError, RouteBudgetError) as exc:
        return None, _failure(state, "ROLLENLIMIT", str(exc)), None, state["actual_call_count"]
    call_number = state["actual_call_count"] + 1
    print(f"[6AGENT] {role.value}", flush=True)
    return provider.generate(role), None, counts, call_number


def _role_update(
    state: SixAgentWorkflowState,
    role: ModelRole,
    counts: RoleIterationCounts,
    call_number: int,
    **values: object,
) -> dict[str, object]:
    return {
        "current_agent": role,
        "iteration_counts": counts,
        "actual_call_count": call_number,
        "status": "laeuft",
        "events": [_event(role.value, state, call=call_number)],
        "usage": [_usage(role, call_number)],
        **values,
    }


def _feedback(result: TesterResult | ReviewResult) -> str:
    return " ".join(result.verbesserungen).strip()


def _selected(route: ChefRoute, role: ModelRole) -> bool:
    return {
        ModelRole.PLANER: route.planer,
        ModelRole.ANALYST: route.analyst,
        ModelRole.UMSETZER: route.umsetzer,
        ModelRole.TESTER: route.tester,
        ModelRole.PRUEFER: route.pruefer,
    }.get(role, True)


def build_six_agent_graph(provider: FakeSixAgentProvider, config: SixAgentGraphConfig):
    def chef_router(state: SixAgentWorkflowState) -> dict[str, object]:
        # CHEF_ROUTER must run before a route-specific budget exists, so only its
        # hard/role limits can be checked here.
        if state["actual_call_count"] + 1 > state["hard_max_model_calls"]:
            return _failure(state, "HARD_LIMIT", "Die harte Grenze lässt keinen CHEF_ROUTER-Aufruf zu.")
        if state["iteration_counts"].count(ModelRole.CHEF_ROUTER) >= config.role_limits.chef_router:
            return _failure(state, "ROLLENLIMIT", "Das Rollenlimit für CHEF_ROUTER ist erreicht.")
        print("[6AGENT] CHEF_ROUTER", flush=True)
        raw_route = provider.generate(ModelRole.CHEF_ROUTER)
        call_number = state["actual_call_count"] + 1
        counts = state["iteration_counts"].increment(ModelRole.CHEF_ROUTER, config.role_limits.chef_router)
        try:
            route = validate_chef_route(raw_route)  # type: ignore[arg-type]
            budget = calculate_route_budget(
                route,
                limits=config.role_limits,
                global_correction_limit=config.global_correction_limit,
                hard_max_model_calls=config.hard_max_model_calls,
                http_attempts_per_call=1,
                allowed_correction_paths=config.allowed_correction_paths,
            )
            require_valid_route_budget(budget)
        except (StructuredOutputError, RouteBudgetError, TypeError) as exc:
            return {
                "current_agent": ModelRole.CHEF_ROUTER,
                "iteration_counts": counts,
                "actual_call_count": call_number,
                "status": "fehlgeschlagen",
                "failure_reason": str(exc),
                "next_agent": None,
                "events": [_event(ModelRole.CHEF_ROUTER.value, state, call=call_number)],
                "usage": [_usage(ModelRole.CHEF_ROUTER, call_number)],
            }
        first = ModelRole.PLANER if route.planer else ModelRole.ANALYST if route.analyst else ModelRole.UMSETZER
        return _role_update(
            state, ModelRole.CHEF_ROUTER, counts, call_number,
            chef_route=route, required_call_budget=budget.required_calls,
            next_agent=first,
        )

    def simple_node(role: ModelRole, field_name: str, next_role: Callable[[ChefRoute], ModelRole]):
        def node(state: SixAgentWorkflowState) -> dict[str, object]:
            value, failed, counts, call_number = _begin_role(state, role, provider, config)
            if failed:
                return failed
            assert counts is not None and state["chef_route"] is not None
            return _role_update(
                state, role, counts, call_number,
                **{field_name: value, "next_agent": next_role(state["chef_route"])},
            )
        return node

    def tester(state: SixAgentWorkflowState) -> dict[str, object]:
        value, failed, counts, call_number = _begin_role(state, ModelRole.TESTER, provider, config)
        if failed:
            return failed
        assert counts is not None and isinstance(value, TesterResult)
        if value.entscheidung is TesterDecision.BESTANDEN:
            return _role_update(
                state, ModelRole.TESTER, counts, call_number,
                testing_result=value, current_feedback="", feedback_origin=None,
                next_agent=ModelRole.PRUEFER,
            )
        if value.fehlerursprung is TesterFailureOrigin.TEST:
            # The static budget model intentionally has no TESTER->TESTER
            # correction path. Retrying it here would bypass its proof.
            return _role_update(
                state, ModelRole.TESTER, counts, call_number,
                testing_result=value, current_feedback=_feedback(value),
                feedback_origin=value.fehlerursprung, status="fehlgeschlagen",
                failure_reason="TESTER-Selbstkorrektur ist im RouteBudget nicht definiert.",
                next_agent=None,
            )
        target = target_for_failure_origin(value.fehlerursprung)
        return _correction_update(state, ModelRole.TESTER, counts, call_number, value, target)

    def reviewer(state: SixAgentWorkflowState) -> dict[str, object]:
        value, failed, counts, call_number = _begin_role(state, ModelRole.PRUEFER, provider, config)
        if failed:
            return failed
        assert counts is not None and isinstance(value, ReviewResult)
        if value.entscheidung is ReviewDecision.AKZEPTIERT:
            return _role_update(
                state, ModelRole.PRUEFER, counts, call_number,
                review_result=value, current_feedback="", feedback_origin=None,
                next_agent=ModelRole.CHEF_FINAL,
            )
        if value.entscheidung is ReviewDecision.UNKLAR:
            target = RoutingTarget.CONTROLLED_FAILURE
        else:
            target = target_for_failure_origin(value.fehlerursprung)
        return _correction_update(state, ModelRole.PRUEFER, counts, call_number, value, target)

    def _correction_update(
        state: SixAgentWorkflowState,
        source: ModelRole,
        counts: RoleIterationCounts,
        call_number: int,
        result: TesterResult | ReviewResult,
        target: RoutingTarget,
    ) -> dict[str, object]:
        result_field = "testing_result" if source is ModelRole.TESTER else "review_result"
        base = _role_update(
            state, source, counts, call_number,
            **{result_field: result, "current_feedback": _feedback(result), "feedback_origin": result.fehlerursprung},
        )
        if target is RoutingTarget.CONTROLLED_FAILURE:
            base.update(status="fehlgeschlagen", failure_reason="Fehlerursprung ist unklar.", next_agent=None)
            return base
        role = ModelRole(target.value)
        route = state["chef_route"]
        if route is None or not _selected(route, role):
            base.update(status="fehlgeschlagen", failure_reason="Korrekturziel ist in der gewählten Route nicht verfügbar.", next_agent=None)
            return base
        if state["global_correction_count"] + 1 > config.global_correction_limit:
            base.update(status="fehlgeschlagen", failure_reason="Das globale Korrekturlimit ist erreicht.", next_agent=None)
            return base
        print(f"[ROUTE] {source.value} -> {role.value}; ursache={result.fehlerursprung.value}", flush=True)
        base.update(
            global_correction_count=state["global_correction_count"] + 1,
            next_agent=role,
        )
        return base

    def chef_final(state: SixAgentWorkflowState) -> dict[str, object]:
        value, failed, counts, call_number = _begin_role(state, ModelRole.CHEF_FINAL, provider, config)
        if failed:
            return failed
        assert counts is not None
        return _role_update(
            state, ModelRole.CHEF_FINAL, counts, call_number,
            final_answer=str(value), status="erfolgreich", next_agent=None,
        )

    def controlled_failure(state: SixAgentWorkflowState) -> dict[str, object]:
        print(f"[CONTROLLED_FAILURE] klasse={_failure_class(state)}", flush=True)
        return {
            "status": "fehlgeschlagen",
            "current_agent": None,
            "next_agent": None,
            "events": [_event(CONTROLLED_FAILURE, state, error_class=_failure_class(state))],
        }

    def _next_or_failure(state: SixAgentWorkflowState) -> str:
        if state["status"] == "fehlgeschlagen" or state["next_agent"] is None:
            return CONTROLLED_FAILURE
        return state["next_agent"].value

    builder = StateGraph(SixAgentWorkflowState)
    builder.add_node(ModelRole.CHEF_ROUTER.value, chef_router)
    builder.add_node(ModelRole.PLANER.value, simple_node(
        ModelRole.PLANER, "planning_result",
        lambda route: ModelRole.ANALYST if route.analyst else ModelRole.UMSETZER,
    ))
    builder.add_node(ModelRole.ANALYST.value, simple_node(
        ModelRole.ANALYST, "analysis_result", lambda route: ModelRole.UMSETZER,
    ))
    builder.add_node(ModelRole.UMSETZER.value, simple_node(
        ModelRole.UMSETZER, "implementation_result",
        lambda route: ModelRole.TESTER if route.tester else ModelRole.PRUEFER,
    ))
    builder.add_node(ModelRole.TESTER.value, tester)
    builder.add_node(ModelRole.PRUEFER.value, reviewer)
    builder.add_node(ModelRole.CHEF_FINAL.value, chef_final)
    builder.add_node(CONTROLLED_FAILURE, controlled_failure)
    builder.add_edge(START, ModelRole.CHEF_ROUTER.value)
    destinations = {role.value: role.value for role in ModelRole if role is not ModelRole.CHEF_ROUTER}
    destinations[CONTROLLED_FAILURE] = CONTROLLED_FAILURE
    for role in (
        ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST,
        ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER,
    ):
        builder.add_conditional_edges(role.value, _next_or_failure, destinations)
    builder.add_edge(ModelRole.CHEF_FINAL.value, END)
    builder.add_edge(CONTROLLED_FAILURE, END)
    return builder.compile()


def _failure_class(state: SixAgentWorkflowState) -> str:
    reason = state.get("failure_reason", "")
    if "Budget" in reason or "budget" in reason or "Grenze" in reason:
        return "BUDGET"
    if "Rollenlimit" in reason:
        return "ROLLENLIMIT"
    if "Korrekturlimit" in reason:
        return "KORREKTURLIMIT"
    if "unklar" in reason.lower():
        return "UNKLAR"
    return "VALIDIERUNG"


def run_fake_six_agent_workflow(
    user_request: str,
    provider: FakeSixAgentProvider,
    config: SixAgentGraphConfig,
    *,
    workflow_id: str = "fake-six-agent",
) -> SixAgentWorkflowState:
    initial = create_initial_six_agent_state(
        workflow_id, user_request, hard_max_model_calls=config.hard_max_model_calls,
    )
    return build_six_agent_graph(provider, config).invoke(initial)
