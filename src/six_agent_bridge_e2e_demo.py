from __future__ import annotations

import json
import sys

from route_budget import CorrectionPathName
from six_agent_bridge_fake_client import FakeOpenAIClient, completed_response
from six_agent_graph import full_route_json
from six_agent_integration_graph import (
    DeterministicIntegrationRoles, IntegrationGraphConfig,
    run_six_agent_integration_workflow,
)
from six_agent_openai_bridge import SixAgentOpenAIBridge, SixAgentOpenAIConfig


def _tester(decision: str, origin: str, improvements: list[str]) -> str:
    return json.dumps({"entscheidung": decision, "fehlerursprung": origin,
        "begruendung": "Offline-Test", "verbesserungen": improvements})


def _review() -> str:
    return json.dumps({"entscheidung": "AKZEPTIERT", "fehlerursprung": "UNKLAR",
        "begruendung": "Offline akzeptiert", "verbesserungen": []})


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("[E2E] Start – Fake Responses API", flush=True)
    client = FakeOpenAIClient.from_responses([
        completed_response(full_route_json()),
        completed_response("Plan v1"), completed_response("Analyse v1"),
        completed_response("Umsetzung v1"),
        completed_response(_tester("FEHLER", "UMSETZUNG", ["Umsetzung korrigieren"])),
        completed_response("Umsetzung v2"), completed_response(_tester("BESTANDEN", "UNKLAR", [])),
        completed_response(_review()),
    ])
    bridge = SixAgentOpenAIBridge(client, SixAgentOpenAIConfig())
    roles = DeterministicIntegrationRoles()
    config = IntegrationGraphConfig(hard_max_model_calls=8, global_correction_limit=1,
        allowed_correction_paths=frozenset({CorrectionPathName.TESTER_UMSETZUNG}))
    result = run_six_agent_integration_workflow("Offline-E2E-Auftrag", bridge, roles, config)
    for call in client.responses.call_history:
        print(f"[E2E] {call.role.value} → Fake Responses API", flush=True)
    print("[E2E] CHEF_FINAL", flush=True)
    print(f"[E2E] status={result['status']}; actual_call_count={result['actual_call_count']}; "
          f"global_correction_count={result['global_correction_count']}; "
          f"fake_requests={len(client.responses.call_history)}", flush=True)
    print("[E2E] FERTIG" if result["status"] == "erfolgreich" else "[E2E] FEHLER", flush=True)
    return 0 if result["status"] == "erfolgreich" else 1


if __name__ == "__main__":
    raise SystemExit(main())
