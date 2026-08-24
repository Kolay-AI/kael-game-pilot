from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import sys
from typing import Mapping, Sequence

from route_budget import calculate_route_budget
from six_agent_bridge_fake_client import FakeOpenAIClient, completed_response
from six_agent_contracts import validate_chef_router_output
from six_agent_integration_graph import (
    DeterministicIntegrationRoles,
    IntegrationGraphConfig,
    run_six_agent_integration_workflow,
)
from six_agent_role_adapter import AdapterGenerationResult, SixAgentRoleProvider
from six_agent_runtime import (
    SixAgentRuntimeConfig,
    SixAgentRuntimeConfigError,
    create_six_agent_bridge,
    load_nonsecret_runtime_config,
)
from six_agent_state import ModelRole, SixAgentWorkflowState


EXIT_SUCCESS = 0
EXIT_CLI_OR_CONFIG = 2
EXIT_SAFETY_BLOCK = 3
EXIT_WORKFLOW_FAILURE = 4
EXIT_LIVE_NOT_IMPLEMENTED = 5
EXIT_INTERRUPTED = 130

DEFAULT_OFFLINE_REQUEST = "Erstelle eine kurze technische Offline-Demolösung."
MINIMAL_LIVE_BUDGET = 3
FULL_LIVE_BUDGET_WITHOUT_CORRECTION = 6


@dataclass(frozen=True)
class OfflineCliResult:
    exit_code: int
    state: SixAgentWorkflowState
    fake_request_count: int


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("Die CLI-Argumente sind ungültig.")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _ArgumentParser(description="Sicherer Offline-/Preflight-Einstieg für sechs Agenten")
    parser.add_argument("--request", help="Benutzerauftrag; im Live-Preflight verpflichtend")
    parser.add_argument(
        "--live-six-agent", action="store_true",
        help="zweites explizites Gate; führt derzeit ausschließlich den Preflight aus",
    )
    parser.add_argument(
        "--demo-full-route", action="store_true",
        help="offline eine vollständige Route simulieren; das Hard-Limit wird nicht überschrieben",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _route_json(*, full: bool) -> str:
    return json.dumps({
        "schema_version": 1,
        "planer": full,
        "analyst": full,
        "umsetzer": True,
        "tester": full,
        "pruefer": True,
        "complexity": "KOMPLEX" if full else "EINFACH",
        "reason_code": "VOLLSTAENDIGE_BEARBEITUNG" if full else "DIREKTE_UMSETZUNG",
    }, ensure_ascii=False, separators=(",", ":"))


def _review_json() -> str:
    return json.dumps({
        "entscheidung": "AKZEPTIERT",
        "fehlerursprung": "UNKLAR",
        "begruendung": "Offline-Prüfung akzeptiert.",
        "verbesserungen": [],
    }, ensure_ascii=False, separators=(",", ":"))


def _tester_json() -> str:
    return json.dumps({
        "entscheidung": "BESTANDEN",
        "fehlerursprung": "UNKLAR",
        "begruendung": "Offline-Test bestanden.",
        "verbesserungen": [],
    }, ensure_ascii=False, separators=(",", ":"))


def _default_fake_responses(*, full: bool) -> list[object]:
    if full:
        texts = (
            _route_json(full=True), "Offline-Plan", "Offline-Analyse",
            "Offline-Demolösung erfolgreich erstellt.", _tester_json(), _review_json(),
        )
    else:
        texts = (
            _route_json(full=False),
            "Offline-Demolösung erfolgreich erstellt.",
            _review_json(),
        )
    return [
        completed_response(text, input_tokens=index, output_tokens=index + 1)
        for index, text in enumerate(texts, start=1)
    ]


@dataclass
class _SafetyReportingProvider:
    provider: SixAgentRoleProvider
    runtime_config: SixAgentRuntimeConfig
    graph_config: IntegrationGraphConfig

    def generate(
        self, role: ModelRole, system_prompt: str, user_input: str,
    ) -> AdapterGenerationResult:
        result = self.provider.generate(role, system_prompt, user_input)
        if role is ModelRole.CHEF_ROUTER:
            try:
                route = validate_chef_router_output(result.text)
            except ValueError:
                # The adapter remains the sole authority for contract failure handling.
                return result
            budget = calculate_route_budget(
                route,
                hard_max_model_calls=self.runtime_config.hard_max_model_calls,
                global_correction_limit=self.graph_config.global_correction_limit,
                allowed_correction_paths=self.graph_config.allowed_correction_paths,
                http_attempts_per_call=1,
                finalizer_is_model=False,
            )
            print(f"[SICHERHEIT] Erforderliches RouteBudget: {budget.required_calls}", flush=True)
            print(
                "[SICHERHEIT] Route freigegeben"
                if budget.valid else "[SICHERHEIT] Route blockiert",
                flush=True,
            )
        return result


def run_offline_cli(
    runtime_config: SixAgentRuntimeConfig,
    request: str,
    *,
    full_route: bool = False,
    prepared_responses: list[object] | None = None,
) -> OfflineCliResult:
    print("[MODUS] OFFLINE – FakeOpenAIClient, keine Cloudkosten", flush=True)
    print(f"[SICHERHEIT] Hard-Limit: {runtime_config.hard_max_model_calls}", flush=True)
    client = FakeOpenAIClient.from_responses(
        _default_fake_responses(full=full_route)
        if prepared_responses is None else list(prepared_responses)
    )
    bridge = create_six_agent_bridge(client, runtime_config)
    graph_config = IntegrationGraphConfig(
        hard_max_model_calls=runtime_config.hard_max_model_calls,
        global_correction_limit=0,
        allowed_correction_paths=frozenset(),
    )
    provider = _SafetyReportingProvider(bridge, runtime_config, graph_config)
    state = run_six_agent_integration_workflow(
        request, provider, DeterministicIntegrationRoles(), graph_config,
        workflow_id="six-agent-cli-offline",
    )
    if state["status"] == "erfolgreich":
        print("[FERTIG]", flush=True)
        print(state["final_answer"], flush=True)
    else:
        print("[FEHLER] Workflow kontrolliert fehlgeschlagen.", flush=True)

    total_tokens = sum(int(item.get("gesamt_tokens", 0)) for item in state["usage"])
    print(f"[ZUSAMMENFASSUNG] Status: {state['status']}", flush=True)
    print(f"[ZUSAMMENFASSUNG] Modellaufrufe: {state['actual_call_count']}", flush=True)
    print(f"[ZUSAMMENFASSUNG] RouteBudget: {state['required_call_budget']}", flush=True)
    print(f"[ZUSAMMENFASSUNG] Hard-Limit: {state['hard_max_model_calls']}", flush=True)
    print(f"[ZUSAMMENFASSUNG] Fake Requests: {len(client.responses.call_history)}", flush=True)
    print(f"[ZUSAMMENFASSUNG] Tokens: {total_tokens}", flush=True)

    if state["status"] == "erfolgreich":
        exit_code = EXIT_SUCCESS
    elif state["required_call_budget"] > state["hard_max_model_calls"]:
        exit_code = EXIT_SAFETY_BLOCK
    else:
        exit_code = EXIT_WORKFLOW_FAILURE
    return OfflineCliResult(exit_code, state, len(client.responses.call_history))


def _run_live_preflight(config: SixAgentRuntimeConfig, request: str | None) -> int:
    if not config.live_enabled:
        print("[KONFIGURATIONSFEHLER] Runtime-Live-Gate ist nicht aktiviert.", flush=True)
        print("[LIVE-PREFLIGHT] Kein Live-Aufruf ausgeführt", flush=True)
        return EXIT_CLI_OR_CONFIG
    if not isinstance(request, str) or not request.strip():
        print("[KONFIGURATIONSFEHLER] Im Live-Preflight fehlt der Benutzerauftrag.", flush=True)
        print("[LIVE-PREFLIGHT] Kein Live-Aufruf ausgeführt", flush=True)
        return EXIT_CLI_OR_CONFIG
    print("[LIVE-PREFLIGHT] Runtime-Gate: OK", flush=True)
    print("[LIVE-PREFLIGHT] CLI-Gate: OK", flush=True)
    print("[LIVE-PREFLIGHT] Auftrag: vorhanden", flush=True)
    print(f"[LIVE-PREFLIGHT] Hard-Limit: {config.hard_max_model_calls}", flush=True)
    print(f"[LIVE-PREFLIGHT] Minimal möglicher Bedarf: {MINIMAL_LIVE_BUDGET}", flush=True)
    print(
        f"[LIVE-PREFLIGHT] Vollpfad ohne Korrektur: {FULL_LIVE_BUDGET_WITHOUT_CORRECTION}",
        flush=True,
    )
    print(
        "[LIVE-PREFLIGHT] Konkretes RouteBudget erst nach validierter CHEF_ROUTER-Antwort",
        flush=True,
    )
    if config.hard_max_model_calls < MINIMAL_LIVE_BUDGET:
        print("[LIVE-PREFLIGHT] Sicherheitsgrenze blockiert bereits den Minimalpfad.", flush=True)
        print("[LIVE-PREFLIGHT] Kein Live-Aufruf ausgeführt", flush=True)
        return EXIT_SAFETY_BLOCK
    print("[LIVE-PREFLIGHT] Secret-Gate: bewusst nicht geprüft; separate Injektion erforderlich", flush=True)
    print("[LIVE-PREFLIGHT] Kein Live-Aufruf ausgeführt", flush=True)
    return EXIT_LIVE_NOT_IMPLEMENTED


def main(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    prepared_responses: list[object] | None = None,
) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        args = _parse_args(argv)
        config = load_nonsecret_runtime_config(environment)
    except (SixAgentRuntimeConfigError, ValueError):
        print("[KONFIGURATIONSFEHLER] CLI oder Runtime-Konfiguration ist ungültig.", flush=True)
        return EXIT_CLI_OR_CONFIG

    if args.live_six_agent:
        if args.demo_full_route:
            print("[KONFIGURATIONSFEHLER] --demo-full-route ist ausschließlich offline erlaubt.", flush=True)
            return EXIT_CLI_OR_CONFIG
        return _run_live_preflight(config, args.request)

    request = args.request if isinstance(args.request, str) and args.request.strip() else DEFAULT_OFFLINE_REQUEST
    try:
        return run_offline_cli(
            config, request, full_route=args.demo_full_route,
            prepared_responses=prepared_responses,
        ).exit_code
    except KeyboardInterrupt:
        print("[ABGEBROCHEN] Benutzer hat den Offline-Lauf beendet.", flush=True)
        return EXIT_INTERRUPTED
    except Exception:
        print("[FEHLER] Offline-Workflow konnte kontrolliert nicht ausgeführt werden.", flush=True)
        return EXIT_WORKFLOW_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
