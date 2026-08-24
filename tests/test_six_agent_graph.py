from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from route_budget import CorrectionPathName, RoleLimits  # noqa: E402
from six_agent_graph import (  # noqa: E402
    CONTROLLED_FAILURE,
    FakeSixAgentProvider,
    SixAgentGraphConfig,
    full_route_json,
    minimal_route_json,
    review_accepted,
    review_rejected,
    review_unclear,
    run_fake_six_agent_workflow,
    tester_failed as make_tester_failed,
    tester_passed as make_tester_passed,
)
from six_agent_state import ModelRole  # noqa: E402
from structured_routing import (  # noqa: E402
    ReviewFailureOrigin as ReviewOrigin,
    TesterFailureOrigin as TFOrigin,
)


FULL_BASE = [
    ModelRole.CHEF_ROUTER, ModelRole.PLANER, ModelRole.ANALYST,
    ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER,
]


def _run(
    provider: FakeSixAgentProvider,
    *,
    hard: int,
    corrections: int = 0,
    allowed: frozenset[CorrectionPathName] = frozenset(),
    limits: RoleLimits = RoleLimits(),
):
    config = SixAgentGraphConfig(
        hard_max_model_calls=hard,
        role_limits=limits,
        global_correction_limit=corrections,
        allowed_correction_paths=allowed,
    )
    return run_fake_six_agent_workflow("Offline-Testauftrag", provider, config)


def _event_nodes(result) -> list[str]:
    return [str(event["node"]) for event in result["events"]]


def _assert_success(result, provider, expected: list[ModelRole], budget: int, corrections: int) -> None:
    assert provider.calls == expected
    assert result["status"] == "erfolgreich"
    assert result["actual_call_count"] == len(expected)
    assert result["required_call_budget"] == budget
    assert result["global_correction_count"] == corrections
    assert len(result["usage"]) == len(expected)
    assert _event_nodes(result) == [role.value for role in expected]


def test_scenario_a_minimal_route_is_exact() -> None:
    provider = FakeSixAgentProvider(minimal_route_json(), review_results=(review_accepted(),))
    result = _run(provider, hard=4)
    expected = [ModelRole.CHEF_ROUTER, ModelRole.UMSETZER, ModelRole.PRUEFER, ModelRole.CHEF_FINAL]
    _assert_success(result, provider, expected, 4, 0)
    assert ModelRole.PLANER not in provider.calls
    assert ModelRole.ANALYST not in provider.calls
    assert ModelRole.TESTER not in provider.calls


def test_scenario_b_full_route_is_exact() -> None:
    provider = FakeSixAgentProvider(full_route_json(), tester_results=(make_tester_passed(),), review_results=(review_accepted(),))
    result = _run(provider, hard=7)
    _assert_success(result, provider, FULL_BASE + [ModelRole.CHEF_FINAL], 7, 0)


def test_scenario_c_tester_implementation_correction_is_exact_and_replaces_state() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(),
        tester_results=(make_tester_failed(TFOrigin.UMSETZUNG, "alt"), make_tester_passed("neu")),
        review_results=(review_accepted(),),
    )
    result = _run(
        provider, hard=9, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG}),
    )
    expected = FULL_BASE[:-1] + [
        ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER, ModelRole.CHEF_FINAL,
    ]
    _assert_success(result, provider, expected, 9, 1)
    assert result["implementation_result"] == "Fake-Umsetzung-v2"
    assert result["testing_result"] == make_tester_passed("neu")
    assert result["current_feedback"] == ""
    assert "alt" not in result["implementation_result"]


@pytest.mark.parametrize(("origin", "path", "downstream", "budget"), [
    (
        ReviewOrigin.PLANUNG, CorrectionPathName.PRUEFER_PLANUNG,
        [ModelRole.PLANER, ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER], 12,
    ),
    (
        ReviewOrigin.ANALYSE, CorrectionPathName.PRUEFER_ANALYSE,
        [ModelRole.ANALYST, ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER], 11,
    ),
    (
        ReviewOrigin.UMSETZUNG, CorrectionPathName.PRUEFER_UMSETZUNG,
        [ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER], 10,
    ),
    (
        ReviewOrigin.TEST, CorrectionPathName.PRUEFER_TEST,
        [ModelRole.TESTER, ModelRole.PRUEFER], 9,
    ),
])
def test_reviewer_correction_reruns_only_required_downstream(origin, path, downstream, budget) -> None:
    provider = FakeSixAgentProvider(
        full_route_json(),
        tester_results=(make_tester_passed(), make_tester_passed()),
        review_results=(review_rejected(origin, "neues Feedback"), review_accepted()),
    )
    result = _run(provider, hard=budget, corrections=1, allowed=frozenset({path}))
    _assert_success(result, provider, FULL_BASE + downstream + [ModelRole.CHEF_FINAL], budget, 1)
    expected_counts = {role: provider.calls.count(role) for role in ModelRole}
    for role in ModelRole:
        assert result["iteration_counts"].count(role) == expected_counts[role]


def test_unclear_review_fails_closed_without_final_call() -> None:
    provider = FakeSixAgentProvider(full_route_json(), review_results=(review_unclear(),))
    result = _run(provider, hard=7)
    assert provider.calls == FULL_BASE
    assert result["actual_call_count"] == 6
    assert result["status"] == "fehlgeschlagen"
    assert _event_nodes(result)[-1] == CONTROLLED_FAILURE


def test_tester_test_self_retry_fails_closed_because_budget_has_no_such_path() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(), tester_results=(make_tester_failed(TFOrigin.TEST),),
    )
    result = _run(provider, hard=7)
    assert provider.calls == FULL_BASE[:-1]
    assert result["actual_call_count"] == 5
    assert result["status"] == "fehlgeschlagen"
    assert "nicht definiert" in result["failure_reason"]


def test_hard_limit_blocks_before_first_work_agent() -> None:
    provider = FakeSixAgentProvider(full_route_json())
    result = _run(provider, hard=6)
    assert provider.calls == [ModelRole.CHEF_ROUTER]
    assert result["actual_call_count"] == 1
    assert result["status"] == "fehlgeschlagen"
    assert _event_nodes(result) == [ModelRole.CHEF_ROUTER.value, CONTROLLED_FAILURE]


def test_runtime_budget_overrun_is_blocked_without_extra_provider_call() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(),
        tester_results=(make_tester_failed(TFOrigin.UMSETZUNG), make_tester_passed()),
        review_results=(review_accepted(),),
    )
    result = _run(provider, hard=7, corrections=1, allowed=frozenset())
    assert result["required_call_budget"] == 7
    assert result["actual_call_count"] == 7
    assert provider.calls == FULL_BASE[:-1] + [ModelRole.UMSETZER, ModelRole.TESTER]
    assert result["status"] == "fehlgeschlagen"
    assert "Modellaufrufbudget" in result["failure_reason"]


def test_role_limit_is_enforced_before_provider_call() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(), tester_results=(make_tester_failed(TFOrigin.UMSETZUNG),),
    )
    limits = RoleLimits(umsetzer=1)
    result = _run(
        provider, hard=7, corrections=1, limits=limits,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG}),
    )
    assert provider.calls == FULL_BASE[:-1]
    assert result["actual_call_count"] == 5
    assert result["iteration_counts"].umsetzer == 1
    assert result["status"] == "fehlgeschlagen"
    assert "Rollenlimit" in result["failure_reason"]


def test_global_correction_limit_blocks_second_loop_without_target_call() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(),
        tester_results=(make_tester_failed(TFOrigin.UMSETZUNG), make_tester_passed()),
        review_results=(review_rejected(ReviewOrigin.PLANUNG),),
    )
    result = _run(
        provider, hard=12, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG, CorrectionPathName.PRUEFER_PLANUNG}),
    )
    assert provider.calls == FULL_BASE[:-1] + [ModelRole.UMSETZER, ModelRole.TESTER, ModelRole.PRUEFER]
    assert result["actual_call_count"] == 8
    assert result["global_correction_count"] == 1
    assert result["status"] == "fehlgeschlagen"
    assert "Korrekturlimit" in result["failure_reason"]


def test_invalid_chef_route_fails_before_work_agent() -> None:
    invalid = json.dumps({"schema_version": 1, "planer": False})
    provider = FakeSixAgentProvider(invalid)
    result = _run(provider, hard=10)
    assert provider.calls == [ModelRole.CHEF_ROUTER]
    assert result["actual_call_count"] == 1
    assert result["status"] == "fehlgeschlagen"


def test_feedback_and_domain_results_replace_instead_of_accumulating() -> None:
    provider = FakeSixAgentProvider(
        full_route_json(),
        tester_results=(make_tester_failed(TFOrigin.UMSETZUNG, "altes Feedback"), make_tester_passed()),
        review_results=(review_rejected(ReviewOrigin.UMSETZUNG, "neues Feedback"),),
    )
    result = _run(
        provider, hard=12, corrections=1,
        allowed=frozenset({CorrectionPathName.TESTER_UMSETZUNG, CorrectionPathName.PRUEFER_UMSETZUNG}),
    )
    assert result["status"] == "fehlgeschlagen"
    assert result["current_feedback"] == "neues Feedback"
    assert result["feedback_origin"] is ReviewOrigin.UMSETZUNG
    assert result["planning_result"] == "Fake-Plan-v1"
    assert result["analysis_result"] == "Fake-Analyse-v1"
    assert result["implementation_result"] == "Fake-Umsetzung-v2"
    assert not isinstance(result["planning_result"], list)
    assert not isinstance(result["current_feedback"], list)
    assert len(result["events"]) > 1 and len(result["usage"]) == result["actual_call_count"]


def test_graph_module_has_no_openai_network_secret_or_old_graph_imports() -> None:
    source = (SRC_DIR / "six_agent_graph.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert imports.isdisjoint({"openai", "httpx", "httpx2", "requests", "llm_provider", "graph", "os"})
    assert "OPENAI_API_KEY" not in source


def test_fake_demo_finishes_without_network() -> None:
    completed = subprocess.run(
        [sys.executable, str(SRC_DIR / "six_agent_fake_demo.py")],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=15, check=False,
    )
    assert completed.returncode == 0
    assert "[DEMO] FERTIG" in completed.stdout
    assert "modellaufrufe=9" in completed.stdout
    assert "OPENAI_API_KEY" not in completed.stdout + completed.stderr
