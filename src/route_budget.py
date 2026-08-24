from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations

from six_agent_state import ModelRole, RoleIterationCounts
from structured_routing import ChefRoute


class RouteBudgetError(ValueError):
    pass


@dataclass(frozen=True)
class RoleLimits:
    chef_router: int = 1
    chef_final: int = 1
    planer: int = 2
    analyst: int = 2
    umsetzer: int = 3
    tester: int = 3
    pruefer: int = 3

    def limit_for(self, role: ModelRole) -> int:
        fields = {
            ModelRole.CHEF_ROUTER: self.chef_router,
            ModelRole.CHEF_FINAL: self.chef_final,
            ModelRole.PLANER: self.planer,
            ModelRole.ANALYST: self.analyst,
            ModelRole.UMSETZER: self.umsetzer,
            ModelRole.TESTER: self.tester,
            ModelRole.PRUEFER: self.pruefer,
        }
        if not isinstance(role, ModelRole):
            raise RouteBudgetError("Unbekannte Modellrolle.")
        limit = fields[role]
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise RouteBudgetError(f"Das Rollenlimit für {role.value} muss mindestens 1 sein.")
        return limit


DEFAULT_ROLE_LIMITS = RoleLimits()
DEFAULT_GLOBAL_CORRECTION_LIMIT = 2


class CorrectionPathName(str, Enum):
    TESTER_UMSETZUNG = "TESTER_UMSETZUNG"
    PRUEFER_UMSETZUNG = "PRÜFER_UMSETZUNG"
    PRUEFER_TEST = "PRÜFER_TEST"
    PRUEFER_ANALYSE = "PRÜFER_ANALYSE"
    PRUEFER_PLANUNG = "PRÜFER_PLANUNG"


@dataclass(frozen=True)
class CorrectionPath:
    name: CorrectionPathName
    roles: tuple[ModelRole, ...]


@dataclass(frozen=True)
class RouteBudget:
    base_calls: int
    correction_calls: int
    required_calls: int
    hard_limit: int
    valid: bool
    selected_base_roles: tuple[ModelRole, ...]
    selected_correction_paths: tuple[CorrectionPathName, ...]
    max_corrections: int
    max_http_attempts: int


def base_roles_for_route(
    route: ChefRoute, *, finalizer_is_model: bool = True,
) -> tuple[ModelRole, ...]:
    if not isinstance(finalizer_is_model, bool):
        raise RouteBudgetError("finalizer_is_model muss ein Boolean sein.")
    roles = [ModelRole.CHEF_ROUTER]
    if route.planer:
        roles.append(ModelRole.PLANER)
    if route.analyst:
        roles.append(ModelRole.ANALYST)
    roles.append(ModelRole.UMSETZER)
    if route.tester:
        roles.append(ModelRole.TESTER)
    roles.append(ModelRole.PRUEFER)
    if finalizer_is_model:
        roles.append(ModelRole.CHEF_FINAL)
    return tuple(roles)


def correction_paths_for_route(route: ChefRoute) -> tuple[CorrectionPath, ...]:
    paths: list[CorrectionPath] = []
    if route.tester:
        paths.append(CorrectionPath(
            CorrectionPathName.TESTER_UMSETZUNG,
            (ModelRole.UMSETZER, ModelRole.TESTER),
        ))
    paths.append(CorrectionPath(
        CorrectionPathName.PRUEFER_UMSETZUNG,
        (ModelRole.UMSETZER,) + ((ModelRole.TESTER,) if route.tester else ()) + (ModelRole.PRUEFER,),
    ))
    if route.tester:
        paths.append(CorrectionPath(
            CorrectionPathName.PRUEFER_TEST,
            (ModelRole.TESTER, ModelRole.PRUEFER),
        ))
    if route.analyst:
        paths.append(CorrectionPath(
            CorrectionPathName.PRUEFER_ANALYSE,
            (ModelRole.ANALYST, ModelRole.UMSETZER)
            + ((ModelRole.TESTER,) if route.tester else ())
            + (ModelRole.PRUEFER,),
        ))
    if route.planer:
        paths.append(CorrectionPath(
            CorrectionPathName.PRUEFER_PLANUNG,
            (ModelRole.PLANER,)
            + ((ModelRole.ANALYST,) if route.analyst else ())
            + (ModelRole.UMSETZER,)
            + ((ModelRole.TESTER,) if route.tester else ())
            + (ModelRole.PRUEFER,),
        ))
    return tuple(paths)


def _counts_for_roles(roles: tuple[ModelRole, ...]) -> dict[ModelRole, int]:
    return {role: roles.count(role) for role in ModelRole}


def _within_role_limits(roles: tuple[ModelRole, ...], limits: RoleLimits) -> bool:
    counts = _counts_for_roles(roles)
    return all(counts[role] <= limits.limit_for(role) for role in ModelRole)


def calculate_route_budget(
    route: ChefRoute,
    *,
    limits: RoleLimits = DEFAULT_ROLE_LIMITS,
    global_correction_limit: int = DEFAULT_GLOBAL_CORRECTION_LIMIT,
    hard_max_model_calls: int,
    http_attempts_per_call: int = 2,
    allowed_correction_paths: frozenset[CorrectionPathName] | None = None,
    finalizer_is_model: bool = True,
) -> RouteBudget:
    if not isinstance(route, ChefRoute):
        raise RouteBudgetError("Die Route muss bereits als ChefRoute validiert sein.")
    if not isinstance(global_correction_limit, int) or isinstance(global_correction_limit, bool) or global_correction_limit < 0:
        raise RouteBudgetError("Das globale Korrekturlimit darf nicht negativ sein.")
    if not isinstance(hard_max_model_calls, int) or isinstance(hard_max_model_calls, bool) or hard_max_model_calls < 1:
        raise RouteBudgetError("Die harte Modellaufrufgrenze muss mindestens 1 sein.")
    if not isinstance(http_attempts_per_call, int) or http_attempts_per_call < 1:
        raise RouteBudgetError("HTTP-Versuche pro Modellaufruf müssen mindestens 1 sein.")

    base_roles = base_roles_for_route(route, finalizer_is_model=finalizer_is_model)
    if not _within_role_limits(base_roles, limits):
        raise RouteBudgetError("Bereits der Basispfad überschreitet ein Rollenlimit.")
    candidates = correction_paths_for_route(route)
    if allowed_correction_paths is not None:
        if any(not isinstance(name, CorrectionPathName) for name in allowed_correction_paths):
            raise RouteBudgetError("Unbekannter statischer Korrekturpfad.")
        candidates = tuple(path for path in candidates if path.name in allowed_correction_paths)

    best: tuple[CorrectionPath, ...] = ()
    max_selected = min(global_correction_limit, len(candidates))
    for count in range(max_selected + 1):
        for selected in combinations(candidates, count):
            correction_roles = tuple(role for path in selected for role in path.roles)
            if not _within_role_limits(base_roles + correction_roles, limits):
                continue
            if sum(len(path.roles) for path in selected) > sum(len(path.roles) for path in best):
                best = selected

    correction_calls = sum(len(path.roles) for path in best)
    required_calls = len(base_roles) + correction_calls
    return RouteBudget(
        base_calls=len(base_roles),
        correction_calls=correction_calls,
        required_calls=required_calls,
        hard_limit=hard_max_model_calls,
        valid=required_calls <= hard_max_model_calls,
        selected_base_roles=base_roles,
        selected_correction_paths=tuple(path.name for path in best),
        max_corrections=len(best),
        max_http_attempts=required_calls * http_attempts_per_call,
    )


def require_valid_route_budget(budget: RouteBudget) -> RouteBudget:
    if not budget.valid:
        raise RouteBudgetError(
            f"Die Route benötigt bis zu {budget.required_calls} Modellaufrufe, "
            f"die harte Sicherheitsgrenze erlaubt jedoch nur {budget.hard_limit}."
        )
    return budget
