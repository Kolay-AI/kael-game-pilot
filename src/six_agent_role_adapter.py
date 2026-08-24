from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable, Protocol, TypeVar

from prompts import (
    ANALYST_SYSTEM_PROMPT,
    PLANER_SYSTEM_PROMPT,
    SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT,
    SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
    TESTER_SYSTEM_PROMPT,
    UMSETZER_SYSTEM_PROMPT,
)
from route_budget import DEFAULT_ROLE_LIMITS, RoleLimits
from six_agent_contracts import (
    ANALYST_MAX_CHARS,
    ANALYST_MAX_WORDS,
    IMPLEMENTER_MAX_CHARS,
    IMPLEMENTER_MAX_WORDS,
    PLANNER_MAX_CHARS,
    PLANNER_MAX_WORDS,
    RoleContractError,
    build_chef_router_input,
    build_analyst_input,
    build_implementer_input,
    build_planner_input,
    build_reviewer_input,
    build_tester_input,
    validate_analyst_output,
    validate_chef_router_output,
    validate_implementer_output,
    validate_planner_output,
    validate_reviewer_output,
    validate_tester_output,
)
from six_agent_state import ModelRole, RoleIterationCounts, SixAgentStateError, SixAgentWorkflowState
from structured_routing import (
    ChefRoute, ReviewFailureOrigin, ReviewResult, StructuredOutputError,
    TesterDecision, TesterResult,
)


class RoleAdapterError(RuntimeError):
    """Safe adapter failure that never includes prompts, outputs or provider details."""


_DIAGNOSTIC_LAYERS = frozenset({"bridge", "adapter", "validator"})
_DIAGNOSTIC_STATUSES = frozenset({"completed", "incomplete", "failed", "unknown"})
_DIAGNOSTIC_REASONS = frozenset({
    "completed", "empty_output", "IncompleteResponse", "InvalidResponse",
    "Timeout", "Connection", "Authentication", "RateLimit", "APIStatus", "Unknown",
    "provider_error", "invalid_result_contract", "validator_error", "valid_output",
    "word_limit_exceeded", "char_limit_exceeded", "word_and_char_limit_exceeded",
})
_LIST_LINE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+)")


@dataclass(frozen=True)
class SafeRoleDiagnostic:
    role: ModelRole
    layer: str
    reason_code: str
    response_status: str
    output_empty: bool | None = None
    output_char_count: int | None = None
    output_word_count: int | None = None
    word_limit_exceeded: bool | None = None
    char_limit_exceeded: bool | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    markdown_codeblock_present: bool | None = None
    list_structure_present: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, ModelRole):
            raise ValueError("Unbekannte Diagnose-Rolle.")
        if self.layer not in _DIAGNOSTIC_LAYERS:
            raise ValueError("Unbekannter Diagnose-Layer.")
        if self.reason_code not in _DIAGNOSTIC_REASONS:
            raise ValueError("Unbekannter Diagnosegrund.")
        if self.response_status not in _DIAGNOSTIC_STATUSES:
            raise ValueError("Unbekannter Response-Status.")
        for value in (
            self.output_char_count, self.output_word_count, self.input_tokens,
            self.output_tokens, self.total_tokens,
        ):
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                raise ValueError("Diagnosezähler müssen nichtnegative ganze Zahlen sein.")
        for value in (
            self.output_empty, self.word_limit_exceeded, self.char_limit_exceeded,
            self.markdown_codeblock_present, self.list_structure_present,
        ):
            if value is not None and type(value) is not bool:
                raise ValueError("Diagnoseflags müssen Boolean sein.")

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "role": self.role.value,
            "layer": self.layer,
            "reason_code": self.reason_code,
            "response_status": self.response_status,
            "word_limit_exceeded": self.word_limit_exceeded,
            "char_limit_exceeded": self.char_limit_exceeded,
        }
        optional = {
            "output_empty": self.output_empty,
            "output_char_count": self.output_char_count,
            "output_word_count": self.output_word_count,
            "markdown_codeblock_present": self.markdown_codeblock_present,
            "list_structure_present": self.list_structure_present,
        }
        result.update({key: value for key, value in optional.items() if value is not None})
        if all(value is not None for value in (
            self.input_tokens, self.output_tokens, self.total_tokens,
        )):
            result["usage"] = {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
            }
        return result


def build_safe_role_diagnostic(
    *, role: ModelRole, layer: str, reason_code: str, response_status: str,
    text: str | None = None, usage: "AdapterUsageData | None" = None,
    word_limit: int | None = None, char_limit: int | None = None,
) -> SafeRoleDiagnostic:
    value = text.strip() if isinstance(text, str) else None
    words = len(value.split()) if value is not None else None
    chars = len(value) if value is not None else None
    return SafeRoleDiagnostic(
        role=role,
        layer=layer,
        reason_code=reason_code,
        response_status=response_status,
        output_empty=(not bool(value)) if value is not None else None,
        output_char_count=chars,
        output_word_count=words,
        word_limit_exceeded=(words > word_limit) if words is not None and word_limit is not None else None,
        char_limit_exceeded=(chars > char_limit) if chars is not None and char_limit is not None else None,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
        markdown_codeblock_present=("```" in value) if value is not None else None,
        list_structure_present=(
            any(_LIST_LINE.match(line.strip()) for line in value.splitlines())
            if value is not None else None
        ),
    )


@dataclass(frozen=True)
class AdapterUsageData:
    role: str
    provider: str = "fake-role-adapter"
    model: str = "fake-deterministic"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "agent": self.role,
            "provider": self.provider,
            "modell": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "gesamt_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class AdapterGenerationResult:
    text: str
    usage: AdapterUsageData
    diagnostic: SafeRoleDiagnostic | None = None


class SixAgentRoleProvider(Protocol):
    def generate(
        self, role: ModelRole, system_prompt: str, user_input: str,
    ) -> AdapterGenerationResult:
        """Perform exactly one offline logical role generation."""


@dataclass(frozen=True)
class ProviderCallMetadata:
    role: ModelRole
    system_prompt_chars: int
    user_input_chars: int


@dataclass
class DeterministicRoleProvider:
    responses: dict[ModelRole, list[str | AdapterGenerationResult | Exception]]
    call_history: list[ProviderCallMetadata] = field(default_factory=list)
    captured_requests: list[tuple[ModelRole, str, str]] = field(default_factory=list, repr=False)

    def generate(
        self, role: ModelRole, system_prompt: str, user_input: str,
    ) -> AdapterGenerationResult:
        self.call_history.append(ProviderCallMetadata(role, len(system_prompt), len(user_input)))
        self.captured_requests.append((role, system_prompt, user_input))
        configured = self.responses.get(role, [])
        if not configured:
            raise RoleAdapterError("Für die Fake-Rolle ist keine Antwort konfiguriert.")
        item = configured.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, AdapterGenerationResult):
            return item
        return AdapterGenerationResult(str(item), AdapterUsageData(role=role.value))


@dataclass(frozen=True)
class RoleAdapterConfig:
    role_limits: RoleLimits = DEFAULT_ROLE_LIMITS


Validated = TypeVar("Validated", str, ChefRoute, TesterResult, ReviewResult)


def _failure(reason: str, **count_updates: object) -> dict[str, object]:
    return {
        "status": "fehlgeschlagen",
        "failure_reason": reason,
        "next_agent": None,
        **count_updates,
    }


_ROLE_TEXT_LIMITS: dict[ModelRole, tuple[int, int]] = {
    ModelRole.PLANER: (PLANNER_MAX_WORDS, PLANNER_MAX_CHARS),
    ModelRole.ANALYST: (ANALYST_MAX_WORDS, ANALYST_MAX_CHARS),
    ModelRole.UMSETZER: (IMPLEMENTER_MAX_WORDS, IMPLEMENTER_MAX_CHARS),
}


def _validator_diagnostic(
    role: ModelRole, text: str, usage: AdapterUsageData, *, valid: bool = False,
    response_status: str = "completed",
) -> SafeRoleDiagnostic:
    limits = _ROLE_TEXT_LIMITS.get(role)
    word_limit, char_limit = limits if limits is not None else (None, None)
    stripped = text.strip() if isinstance(text, str) else ""
    word_exceeded = word_limit is not None and len(stripped.split()) > word_limit
    char_exceeded = char_limit is not None and len(stripped) > char_limit
    if word_exceeded and char_exceeded:
        reason = "word_and_char_limit_exceeded"
    elif word_exceeded:
        reason = "word_limit_exceeded"
    elif char_exceeded:
        reason = "char_limit_exceeded"
    elif not stripped:
        reason = "empty_output"
    elif valid:
        reason = "valid_output"
    else:
        reason = "validator_error"
    return build_safe_role_diagnostic(
        role=role, layer="validator", reason_code=reason,
        response_status=response_status, text=text, usage=usage,
        word_limit=word_limit, char_limit=char_limit,
    )


def _preflight(
    state: SixAgentWorkflowState, role: ModelRole, config: RoleAdapterConfig,
) -> tuple[RoleIterationCounts, int] | dict[str, object]:
    required = (
        "user_request", "actual_call_count", "required_call_budget",
        "hard_max_model_calls", "iteration_counts",
    )
    if any(key not in state for key in required):
        return _failure("Erforderlicher Adapter-State fehlt.")
    if not isinstance(state["user_request"], str) or not state["user_request"].strip():
        return _failure("Der Benutzerauftrag fehlt.")
    numeric = (state["actual_call_count"], state["required_call_budget"], state["hard_max_model_calls"])
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in numeric):
        return _failure("Die Adapter-Zählerkonfiguration ist ungültig.")
    if not isinstance(state["iteration_counts"], RoleIterationCounts):
        return _failure("Der Rolleniterationszähler fehlt oder ist ungültig.")
    current = state["actual_call_count"]
    if current + 1 > state["required_call_budget"]:
        return _failure("Das erforderliche Modellaufrufbudget ist erreicht.")
    if current + 1 > state["hard_max_model_calls"]:
        return _failure("Die harte Modellaufrufgrenze ist erreicht.")
    try:
        counts = state["iteration_counts"].increment(role, config.role_limits.limit_for(role))
    except (SixAgentStateError, ValueError):
        return _failure(f"Das Rollenlimit für {role.value} ist erreicht.")
    return counts, current + 1


def _chef_router_preflight(
    state: SixAgentWorkflowState, config: RoleAdapterConfig,
) -> tuple[RoleIterationCounts, int] | dict[str, object]:
    required = "user_request", "actual_call_count", "hard_max_model_calls", "iteration_counts"
    if any(key not in state for key in required):
        return _failure("Erforderlicher CHEF_ROUTER-State fehlt.")
    if not isinstance(state["user_request"], str) or not state["user_request"].strip():
        return _failure("Der Benutzerauftrag fehlt.")
    current = state["actual_call_count"]
    hard_limit = state["hard_max_model_calls"]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0
           for value in (current, hard_limit)):
        return _failure("Die CHEF_ROUTER-Zählerkonfiguration ist ungültig.")
    if not isinstance(state["iteration_counts"], RoleIterationCounts):
        return _failure("Der Rolleniterationszähler fehlt oder ist ungültig.")
    if current + 1 > hard_limit:
        return _failure("Die harte Modellaufrufgrenze lässt keinen CHEF_ROUTER-Aufruf zu.")
    try:
        counts = state["iteration_counts"].increment(
            ModelRole.CHEF_ROUTER,
            config.role_limits.limit_for(ModelRole.CHEF_ROUTER),
        )
    except (SixAgentStateError, ValueError):
        return _failure("Das Rollenlimit für CHEF_ROUTER ist erreicht.")
    return counts, current + 1


def run_chef_router(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    prepared = _chef_router_preflight(state, config)
    if isinstance(prepared, dict):
        return prepared
    counts, call_number = prepared
    try:
        user_input = build_chef_router_input(state["user_request"])
    except (RoleContractError, KeyError, TypeError):
        return _failure("Erforderlicher CHEF_ROUTER-Input fehlt oder ist ungültig.")
    try:
        generated = provider.generate(
            ModelRole.CHEF_ROUTER,
            SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT,
            user_input,
        )
    except Exception as exc:
        diagnostic = getattr(exc, "safe_diagnostic", None)
        if not isinstance(diagnostic, SafeRoleDiagnostic):
            diagnostic = SafeRoleDiagnostic(
                ModelRole.CHEF_ROUTER, "adapter", "provider_error", "unknown",
            )
        return _failure(
            "Kontrollierter Providerfehler bei CHEF_ROUTER.",
            iteration_counts=counts,
            actual_call_count=call_number,
            failure_diagnostic=diagnostic.as_dict(),
        )
    count_updates = {"iteration_counts": counts, "actual_call_count": call_number}
    if not isinstance(generated, AdapterGenerationResult) or not isinstance(
        generated.usage, AdapterUsageData,
    ):
        count_updates["failure_diagnostic"] = SafeRoleDiagnostic(
            ModelRole.CHEF_ROUTER, "adapter", "invalid_result_contract", "unknown",
        ).as_dict()
        return _failure("Der Provider lieferte keinen gültigen Ergebnisvertrag.", **count_updates)
    try:
        route = validate_chef_router_output(generated.text)
    except (RoleContractError, StructuredOutputError, TypeError):
        response_status = (
            generated.diagnostic.response_status
            if isinstance(generated.diagnostic, SafeRoleDiagnostic) else "completed"
        )
        count_updates["failure_diagnostic"] = _validator_diagnostic(
            ModelRole.CHEF_ROUTER, generated.text, generated.usage,
            response_status=response_status,
        ).as_dict()
        return _failure("Die Ausgabe von CHEF_ROUTER war ungültig.", **count_updates)
    return {
        "chef_route": route,
        "current_agent": ModelRole.CHEF_ROUTER,
        "iteration_counts": counts,
        "actual_call_count": call_number,
        "status": "laeuft",
        "failure_reason": "",
        "events": [{"node": ModelRole.CHEF_ROUTER.value, "call": call_number,
                    "status": "erfolgreich"}],
        "usage": [generated.usage.as_dict()],
        "role_diagnostic": _validator_diagnostic(
            ModelRole.CHEF_ROUTER, generated.text, generated.usage, valid=True,
        ).as_dict(),
    }


def _run(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig,
    *,
    role: ModelRole,
    system_prompt: str,
    user_input_factory: Callable[[], str],
    validator: Callable[[str], Validated],
    result_field: str,
    extra_update: Callable[[Validated], dict[str, object]] | None = None,
) -> dict[str, object]:
    prepared = _preflight(state, role, config)
    if isinstance(prepared, dict):
        return prepared
    counts, call_number = prepared
    try:
        user_input = user_input_factory()
    except (RoleContractError, KeyError, TypeError):
        return _failure("Erforderlicher Rolleninput fehlt oder ist ungültig.")
    try:
        generated = provider.generate(role, system_prompt, user_input)
    except Exception as exc:
        updates: dict[str, object] = {
            "iteration_counts": counts, "actual_call_count": call_number,
        }
        diagnostic = getattr(exc, "safe_diagnostic", None)
        if not isinstance(diagnostic, SafeRoleDiagnostic):
            diagnostic = SafeRoleDiagnostic(role, "adapter", "provider_error", "unknown")
        updates["failure_diagnostic"] = diagnostic.as_dict()
        return _failure(
            f"Kontrollierter Providerfehler bei {role.value}.",
            **updates,
        )
    count_updates = {"iteration_counts": counts, "actual_call_count": call_number}
    if not isinstance(generated, AdapterGenerationResult) or not isinstance(generated.usage, AdapterUsageData):
        count_updates["failure_diagnostic"] = SafeRoleDiagnostic(
            role, "adapter", "invalid_result_contract", "unknown",
        ).as_dict()
        return _failure("Der Provider lieferte keinen gültigen Ergebnisvertrag.", **count_updates)
    try:
        validated = validator(generated.text)
    except (RoleContractError, StructuredOutputError, TypeError):
        response_status = (
            generated.diagnostic.response_status
            if isinstance(generated.diagnostic, SafeRoleDiagnostic) else "completed"
        )
        count_updates["failure_diagnostic"] = _validator_diagnostic(
            role, generated.text, generated.usage,
            response_status=response_status,
        ).as_dict()
        return _failure(f"Die Ausgabe von {role.value} war ungültig.", **count_updates)
    update: dict[str, object] = {
        result_field: validated,
        "current_agent": role,
        "iteration_counts": counts,
        "actual_call_count": call_number,
        "status": "laeuft",
        "failure_reason": "",
        "events": [{"node": role.value, "call": call_number, "status": "erfolgreich"}],
        "usage": [generated.usage.as_dict()],
    }
    response_status = (
        generated.diagnostic.response_status
        if isinstance(generated.diagnostic, SafeRoleDiagnostic) else "completed"
    )
    update["role_diagnostic"] = _validator_diagnostic(
        role, generated.text, generated.usage, valid=True,
        response_status=response_status,
    ).as_dict()
    if extra_update is not None:
        update.update(extra_update(validated))
    return update


def run_planner(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    return _run(
        state, provider, config,
        role=ModelRole.PLANER,
        system_prompt=PLANER_SYSTEM_PROMPT,
        user_input_factory=lambda: build_planner_input(
            state["user_request"],
            current_feedback=state.get("current_feedback", ""),
            feedback_origin=(
                state.get("feedback_origin")
                if isinstance(state.get("feedback_origin"), ReviewFailureOrigin) else None
            ),
        ),
        validator=validate_planner_output,
        result_field="planning_result",
    )


def run_analyst(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    return _run(
        state, provider, config,
        role=ModelRole.ANALYST,
        system_prompt=ANALYST_SYSTEM_PROMPT,
        user_input_factory=lambda: build_analyst_input(
            state["user_request"],
            planning_result=state.get("planning_result", ""),
            current_feedback=state.get("current_feedback", ""),
            feedback_origin=(
                state.get("feedback_origin")
                if isinstance(state.get("feedback_origin"), ReviewFailureOrigin) else None
            ),
        ),
        validator=validate_analyst_output,
        result_field="analysis_result",
    )


def _tester_updates(result: TesterResult) -> dict[str, object]:
    if result.entscheidung is TesterDecision.BESTANDEN:
        return {"current_feedback": "", "feedback_origin": None}
    return {
        "current_feedback": " ".join(result.verbesserungen),
        "feedback_origin": result.fehlerursprung,
    }


def run_tester(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    return _run(
        state, provider, config,
        role=ModelRole.TESTER,
        system_prompt=TESTER_SYSTEM_PROMPT,
        user_input_factory=lambda: build_tester_input(
            state["user_request"], state["implementation_result"],
            planning_result=state.get("planning_result", ""),
            analysis_result=state.get("analysis_result", ""),
        ),
        validator=validate_tester_output,
        result_field="testing_result",
        extra_update=_tester_updates,
    )


def run_implementer(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    return _run(
        state, provider, config,
        role=ModelRole.UMSETZER,
        system_prompt=UMSETZER_SYSTEM_PROMPT,
        user_input_factory=lambda: build_implementer_input(
            state["user_request"],
            planning_result=state.get("planning_result", ""),
            analysis_result=state.get("analysis_result", ""),
            current_feedback=state.get("current_feedback", ""),
            feedback_origin=state.get("feedback_origin"),
        ),
        validator=validate_implementer_output,
        result_field="implementation_result",
    )


def run_reviewer(
    state: SixAgentWorkflowState,
    provider: SixAgentRoleProvider,
    config: RoleAdapterConfig = RoleAdapterConfig(),
) -> dict[str, object]:
    return _run(
        state, provider, config,
        role=ModelRole.PRUEFER,
        system_prompt=SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
        user_input_factory=lambda: build_reviewer_input(
            state["user_request"], state["implementation_result"],
            planning_result=state.get("planning_result", ""),
            analysis_result=state.get("analysis_result", ""),
            testing_result=state.get("testing_result"),
        ),
        validator=validate_reviewer_output,
        result_field="review_result",
    )
