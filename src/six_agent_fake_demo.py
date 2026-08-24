from __future__ import annotations

from route_budget import CorrectionPathName
from six_agent_graph import (
    FakeSixAgentProvider,
    SixAgentGraphConfig,
    full_route_json,
    review_accepted,
    run_fake_six_agent_workflow,
    tester_failed,
    tester_passed,
)
from structured_routing import TesterFailureOrigin


def main() -> int:
    print("[DEMO] Sechs-Agenten-Fake-Workflow – keine Cloudkosten", flush=True)
    provider = FakeSixAgentProvider(
        route_text=full_route_json(),
        tester_results=(tester_failed(TesterFailureOrigin.UMSETZUNG), tester_passed()),
        review_results=(review_accepted(),),
    )
    config = SixAgentGraphConfig(
        hard_max_model_calls=9,
        global_correction_limit=1,
        allowed_correction_paths=frozenset({CorrectionPathName.TESTER_UMSETZUNG}),
    )
    result = run_fake_six_agent_workflow("Lokaler Fake-Auftrag", provider, config)
    print(
        f"[DEMO] status={result['status']}; modellaufrufe={result['actual_call_count']}; "
        f"korrekturen={result['global_correction_count']}",
        flush=True,
    )
    print("[DEMO] FERTIG" if result["status"] == "erfolgreich" else "[DEMO] FEHLER", flush=True)
    return 0 if result["status"] == "erfolgreich" else 1


if __name__ == "__main__":
    raise SystemExit(main())
