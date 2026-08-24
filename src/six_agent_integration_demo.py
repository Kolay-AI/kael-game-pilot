from __future__ import annotations

import json

from route_budget import CorrectionPathName
from six_agent_graph import full_route_json, review_accepted, tester_failed, tester_passed
from six_agent_integration_graph import (
    DeterministicIntegrationRoles,
    IntegrationGraphConfig,
    run_six_agent_integration_workflow,
)
from six_agent_role_adapter import DeterministicRoleProvider
from six_agent_state import ModelRole
from structured_routing import TesterFailureOrigin


def _tester_json(result) -> str:
    return json.dumps({
        "entscheidung": result.entscheidung.value,
        "fehlerursprung": result.fehlerursprung.value,
        "begruendung": result.begruendung,
        "verbesserungen": list(result.verbesserungen),
    })


def _review_json(result) -> str:
    return json.dumps({
        "entscheidung": result.entscheidung.value,
        "fehlerursprung": result.fehlerursprung.value,
        "begruendung": result.begruendung,
        "verbesserungen": list(result.verbesserungen),
    })


def main() -> int:
    print("[6INT-DEMO] Start – vollständig offline", flush=True)
    provider = DeterministicRoleProvider({
        ModelRole.CHEF_ROUTER: [full_route_json()],
        ModelRole.PLANER: ["Plan v1"],
        ModelRole.ANALYST: ["Analyse v1"],
        ModelRole.UMSETZER: ["Umsetzung v1", "Umsetzung v2"],
        ModelRole.TESTER: [
            _tester_json(tester_failed(TesterFailureOrigin.UMSETZUNG)),
            _tester_json(tester_passed()),
        ],
        ModelRole.PRUEFER: [_review_json(review_accepted())],
    })
    roles = DeterministicIntegrationRoles()
    config = IntegrationGraphConfig(
        hard_max_model_calls=8,
        global_correction_limit=1,
        allowed_correction_paths=frozenset({CorrectionPathName.TESTER_UMSETZUNG}),
    )
    result = run_six_agent_integration_workflow("Offline-Integrationsauftrag", provider, roles, config)
    print(
        f"[6INT-DEMO] status={result['status']}; actual_call_count={result['actual_call_count']}; "
        f"global_correction_count={result['global_correction_count']}",
        flush=True,
    )
    print("[6INT-DEMO] FERTIG" if result["status"] == "erfolgreich" else "[6INT-DEMO] FEHLER", flush=True)
    return 0 if result["status"] == "erfolgreich" else 1


if __name__ == "__main__":
    raise SystemExit(main())
