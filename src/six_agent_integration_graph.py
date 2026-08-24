from __future__ import annotations

from dataclasses import dataclass, field

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
from six_agent_role_adapter import (
    DeterministicRoleProvider,
    RoleAdapterConfig,
    run_analyst,
    run_chef_router,
    run_implementer,
    run_planner,
    run_reviewer,
    run_tester,
)
from six_agent_state import (
    ModelRole,
    SixAgentWorkflowState,
    create_initial_six_agent_state,
)
from structured_routing import (
    ChefRoute,
    ReviewDecision,
    RoutingTarget,
    TesterDecision,
    TesterFailureOrigin,
    target_for_failure_origin,
)


CONTROLLED_FAILURE = "CONTROLLED_FAILURE"
TESTER_ROUTE = "TESTER_ROUTE"
REVIEWER_ROUTE = "REVIEWER_ROUTE"


@dataclass
class DeterministicIntegrationRoles:
    route: ChefRoute | None = None  # Legacy fixture compatibility; the graph never reads it.
    calls: list[ModelRole] = field(default_factory=list)

    def record(self, role: ModelRole) -> int:
        self.calls.append(role)
        return self.calls.count(role)

@dataclass(frozen=True)
class IntegrationGraphConfig:
    hard_max_model_calls: int
    role_limits: RoleLimits = DEFAULT_ROLE_LIMITS
    global_correction_limit: int = DEFAULT_GLOBAL_CORRECTION_LIMIT
    allowed_correction_paths: frozenset[CorrectionPathName] | None = None


def _failure(reason: str) -> dict[str, object]:
    return {"status": "fehlgeschlagen", "failure_reason": reason, "next_agent": None}


def _selected(route: ChefRoute, role: ModelRole) -> bool:
    return {
        ModelRole.PLANER: route.planer,
        ModelRole.ANALYST: route.analyst,
        ModelRole.UMSETZER: route.umsetzer,
        ModelRole.TESTER: route.tester,
        ModelRole.PRUEFER: route.pruefer,
    }.get(role, True)


def build_six_agent_integration_graph(
    provider: DeterministicRoleProvider,
    roles: DeterministicIntegrationRoles,
    config: IntegrationGraphConfig,
):
    adapter_config = RoleAdapterConfig(config.role_limits)

    def chef_router(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] CHEF_ROUTER adapter", flush=True)
        router_update = run_chef_router(state, provider, adapter_config)
        if router_update.get("status") == "fehlgeschlagen":
            return router_update
        route = router_update.get("chef_route")
        if not isinstance(route, ChefRoute):
            return {**router_update, **_failure("Die validierte ChefRoute fehlt.")}
        budget = None
        try:
            budget = calculate_route_budget(
                route,
                limits=config.role_limits,
                global_correction_limit=config.global_correction_limit,
                hard_max_model_calls=config.hard_max_model_calls,
                http_attempts_per_call=1,
                allowed_correction_paths=config.allowed_correction_paths,
                finalizer_is_model=False,
            )
            require_valid_route_budget(budget)
        except RouteBudgetError as exc:
            return {
                **router_update,
                **_failure(str(exc)),
                "required_call_budget": budget.required_calls if budget is not None else 0,
            }
        first = ModelRole.PLANER if route.planer else ModelRole.ANALYST if route.analyst else ModelRole.UMSETZER
        return {
            **router_update,
            "required_call_budget": budget.required_calls,
            "next_agent": first,
        }

    def planner(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] PLANER adapter", flush=True)
        return run_planner(state, provider, adapter_config)

    def analyst(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] ANALYST adapter", flush=True)
        return run_analyst(state, provider, adapter_config)

    def implementer(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] UMSETZER adapter", flush=True)
        return run_implementer(state, provider, adapter_config)

    def tester(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] TESTER adapter", flush=True)
        return run_tester(state, provider, adapter_config)

    def tester_route(state: SixAgentWorkflowState) -> dict[str, object]:
        result = state["testing_result"]
        if result is None:
            return _failure("Das strukturierte Testergebnis fehlt.")
        if result.entscheidung is TesterDecision.BESTANDEN:
            return {"next_agent": ModelRole.PRUEFER}
        target = target_for_failure_origin(result.fehlerursprung)
        if target is not RoutingTarget.UMSETZER:
            return _failure("Der Tester-Korrekturpfad ist nicht statisch budgetiert.")
        return _correction(state, ModelRole.TESTER, ModelRole.UMSETZER, result.fehlerursprung.value)

    def reviewer(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT] PRÜFER adapter", flush=True)
        return run_reviewer(state, provider, adapter_config)

    def reviewer_route(state: SixAgentWorkflowState) -> dict[str, object]:
        result = state["review_result"]
        if result is None:
            return _failure("Das strukturierte ReviewResult fehlt.")
        if result.entscheidung is ReviewDecision.AKZEPTIERT:
            return {"current_feedback": "", "feedback_origin": None, "next_agent": ModelRole.CHEF_FINAL}
        target = target_for_failure_origin(result.fehlerursprung)
        if result.entscheidung is ReviewDecision.UNKLAR or target is RoutingTarget.CONTROLLED_FAILURE:
            return _failure("Der Prüfer-Fehlerursprung ist unklar.")
        target_role = ModelRole(target.value)
        route = state["chef_route"]
        if route is None or not _selected(route, target_role):
            return _failure("Das Prüfer-Korrekturziel ist in der Route nicht verfügbar.")
        correction = _correction(state, ModelRole.PRUEFER, target_role, result.fehlerursprung.value)
        correction.update(
            current_feedback=" ".join(result.verbesserungen),
            feedback_origin=result.fehlerursprung,
        )
        return correction

    def _correction(
        state: SixAgentWorkflowState, source: ModelRole, target: ModelRole, origin: str,
    ) -> dict[str, object]:
        if state["global_correction_count"] + 1 > config.global_correction_limit:
            return _failure("Das globale Korrekturlimit ist erreicht.")
        print(f"[6INT-ROUTE] {source.value} -> {target.value}; ursache={origin}", flush=True)
        return {
            "global_correction_count": state["global_correction_count"] + 1,
            "next_agent": target,
        }

    def chef_final(state: SixAgentWorkflowState) -> dict[str, object]:
        if state["review_result"] is None or state["review_result"].entscheidung is not ReviewDecision.AKZEPTIERT:
            return _failure("CHEF_FINAL benötigt ein akzeptiertes ReviewResult.")
        if not isinstance(state["implementation_result"], str) or not state["implementation_result"].strip():
            return _failure("CHEF_FINAL benötigt eine akzeptierte Umsetzung.")
        print("[6INT] CHEF_FINAL direkte Ausgabe", flush=True)
        return {
            "current_agent": ModelRole.CHEF_FINAL,
            "final_answer": state["implementation_result"],
            "status": "erfolgreich",
            "failure_reason": "",
            "next_agent": None,
            "events": [{
                "node": "FINALIZATION",
                "call": state["actual_call_count"],
                "status": "erfolgreich",
                "model_call": False,
            }],
        }

    def controlled_failure(state: SixAgentWorkflowState) -> dict[str, object]:
        print("[6INT-FAIL] klasse=KONTROLLIERT", flush=True)
        return {
            "status": "fehlgeschlagen",
            "next_agent": None,
            "events": [{"node": CONTROLLED_FAILURE, "call": state["actual_call_count"]}],
        }

    def next_or_failure(state: SixAgentWorkflowState) -> str:
        if state["status"] == "fehlgeschlagen" or state["next_agent"] is None:
            return CONTROLLED_FAILURE
        return state["next_agent"].value

    def after_planner(state: SixAgentWorkflowState) -> str:
        if state["status"] == "fehlgeschlagen":
            return CONTROLLED_FAILURE
        route = state["chef_route"]
        assert route is not None
        return ModelRole.ANALYST.value if route.analyst else ModelRole.UMSETZER.value

    def after_analyst(state: SixAgentWorkflowState) -> str:
        return CONTROLLED_FAILURE if state["status"] == "fehlgeschlagen" else ModelRole.UMSETZER.value

    def after_tester(state: SixAgentWorkflowState) -> str:
        return CONTROLLED_FAILURE if state["status"] == "fehlgeschlagen" else TESTER_ROUTE

    def after_reviewer(state: SixAgentWorkflowState) -> str:
        return CONTROLLED_FAILURE if state["status"] == "fehlgeschlagen" else REVIEWER_ROUTE

    def after_implementer(state: SixAgentWorkflowState) -> str:
        if state["status"] == "fehlgeschlagen":
            return CONTROLLED_FAILURE
        route = state["chef_route"]
        assert route is not None
        return ModelRole.TESTER.value if route.tester else ModelRole.PRUEFER.value

    destinations = {role.value: role.value for role in ModelRole if role is not ModelRole.CHEF_ROUTER}
    destinations[CONTROLLED_FAILURE] = CONTROLLED_FAILURE
    builder = StateGraph(SixAgentWorkflowState)
    builder.add_node(ModelRole.CHEF_ROUTER.value, chef_router)
    builder.add_node(ModelRole.PLANER.value, planner)
    builder.add_node(ModelRole.ANALYST.value, analyst)
    builder.add_node(ModelRole.UMSETZER.value, implementer)
    builder.add_node(ModelRole.TESTER.value, tester)
    builder.add_node(TESTER_ROUTE, tester_route)
    builder.add_node(ModelRole.PRUEFER.value, reviewer)
    builder.add_node(REVIEWER_ROUTE, reviewer_route)
    builder.add_node(ModelRole.CHEF_FINAL.value, chef_final)
    builder.add_node(CONTROLLED_FAILURE, controlled_failure)
    builder.add_edge(START, ModelRole.CHEF_ROUTER.value)
    builder.add_conditional_edges(ModelRole.CHEF_ROUTER.value, next_or_failure, destinations)
    builder.add_conditional_edges(ModelRole.PLANER.value, after_planner, {
        ModelRole.ANALYST.value: ModelRole.ANALYST.value,
        ModelRole.UMSETZER.value: ModelRole.UMSETZER.value,
        CONTROLLED_FAILURE: CONTROLLED_FAILURE,
    })
    builder.add_conditional_edges(ModelRole.ANALYST.value, after_analyst, {
        ModelRole.UMSETZER.value: ModelRole.UMSETZER.value,
        CONTROLLED_FAILURE: CONTROLLED_FAILURE,
    })
    builder.add_conditional_edges(ModelRole.UMSETZER.value, after_implementer, {
        ModelRole.TESTER.value: ModelRole.TESTER.value,
        ModelRole.PRUEFER.value: ModelRole.PRUEFER.value,
        CONTROLLED_FAILURE: CONTROLLED_FAILURE,
    })
    builder.add_conditional_edges(ModelRole.TESTER.value, after_tester, {
        TESTER_ROUTE: TESTER_ROUTE, CONTROLLED_FAILURE: CONTROLLED_FAILURE,
    })
    builder.add_conditional_edges(TESTER_ROUTE, next_or_failure, destinations)
    builder.add_conditional_edges(ModelRole.PRUEFER.value, after_reviewer, {
        REVIEWER_ROUTE: REVIEWER_ROUTE, CONTROLLED_FAILURE: CONTROLLED_FAILURE,
    })
    builder.add_conditional_edges(REVIEWER_ROUTE, next_or_failure, destinations)
    builder.add_edge(ModelRole.CHEF_FINAL.value, END)
    builder.add_edge(CONTROLLED_FAILURE, END)
    return builder.compile()


def run_six_agent_integration_workflow(
    user_request: str,
    provider: DeterministicRoleProvider,
    roles: DeterministicIntegrationRoles,
    config: IntegrationGraphConfig,
    *,
    workflow_id: str = "six-agent-integration",
    initial_events: list[dict[str, object]] | None = None,
    initial_usage: list[dict[str, object]] | None = None,
) -> SixAgentWorkflowState:
    state = create_initial_six_agent_state(
        workflow_id, user_request, hard_max_model_calls=config.hard_max_model_calls,
    )
    state["events"] = list(initial_events or ())
    state["usage"] = list(initial_usage or ())
    return build_six_agent_integration_graph(provider, roles, config).invoke(state)
