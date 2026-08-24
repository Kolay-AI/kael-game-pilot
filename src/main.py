from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import agents as agents_module
import graph as graph_module
import llm_provider as llm_provider_module
from config import ConfigurationError, calculate_required_model_calls, load_config
from graph import WorkflowBusyError, run_workflow
from llm_provider import ProviderError, create_provider


LIVE_TEST_TASK = "Nenne drei Vorteile eines regelmäßigen Projekt-Backups. Die Antwort soll genau drei nummerierte Punkte enthalten."


def _print_start_diagnostics(project_dir: Path) -> None:
    diagnostics = (
        "[START] main.py aktiv",
        f"[START] Python: {sys.version.split()[0]}",
        f"[START] Projektpfad: {project_dir.resolve()}",
        f"[START] main.py: {Path(__file__).resolve()}",
        f"[START] llm_provider.py: {Path(llm_provider_module.__file__).resolve()}",
        f"[START] agents.py: {Path(agents_module.__file__).resolve()}",
        f"[START] graph.py: {Path(graph_module.__file__).resolve()}",
    )
    for line in diagnostics:
        print(line, flush=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lokaler oder ausdrücklich freigegebener Drei-Agenten-Test")
    parser.add_argument(
        "--live-openai",
        action="store_true",
        help="zweite, ausdrückliche Freigabe zum Start des OpenAI-Live-Tests",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    project_dir = Path(__file__).resolve().parent.parent
    _print_start_diagnostics(project_dir)
    args = _parse_args(argv)
    try:
        config = load_config()
        if config.provider == "openai" and not args.live_openai:
            raise ConfigurationError(
                "OpenAI ist konfiguriert, aber --live-openai fehlt. Es wurde kein API-Aufruf ausgeführt."
            )
        if args.live_openai and config.provider != "openai":
            raise ConfigurationError("--live-openai erfordert MAS_PROVIDER=openai.")
        if args.live_openai:
            config = replace(
                config,
                max_review_cycles=min(config.max_review_cycles, 2),
                max_response_chars=min(config.max_response_chars, 1_200),
                max_output_tokens=min(config.max_output_tokens, 1_000),
            )
        provider = create_provider(config)
    except (ConfigurationError, ProviderError, ValueError) as exc:
        print(f"[KONFIGURATIONSFEHLER] {exc}")
        return 2

    print("Provider: FAKE – keine API-Kosten" if config.provider == "fake" else f"Provider: OPENAI – Cloud-Kosten möglich; maximal {config.max_review_cycles} Prüfzyklen")
    if config.provider == "openai":
        print(f"Prüfzyklen: {config.max_review_cycles}", flush=True)
        print(
            f"Erforderliches Aufrufbudget: {calculate_required_model_calls(config.max_review_cycles)}",
            flush=True,
        )
        print(f"Harte Sicherheitsgrenze: {config.hard_max_model_calls}", flush=True)
    request = LIVE_TEST_TASK if args.live_openai else "Erstelle einen nachvollziehbaren lokalen Multi-Agenten-Funktionstest."
    try:
        result, log_path = run_workflow(request, project_dir / "logs", provider=provider, config=config)
    except KeyboardInterrupt:
        print("\n[ABGEBROCHEN] Benutzer hat den Live-Test beendet.")
        return 130
    except (ProviderError, WorkflowBusyError) as exc:
        print(f"[PROVIDERFEHLER] {exc}")
        return 2

    print("\n--- ENDERGEBNIS ---")
    print(result["final_answer"])
    summary = result["usage_summary"]
    print(
        "\nNutzung: "
        f"{summary['api_aufrufe']} API-Aufrufe, "
        f"{summary['input_tokens']} Input-Tokens, "
        f"{summary['output_tokens']} Output-Tokens, "
        f"{summary['gesamt_tokens']} Tokens gesamt"
    )
    print(f"\nAudit-Protokoll: {log_path if log_path else 'deaktiviert'}")
    return 0 if result["status"] == "erfolgreich" else 1


if __name__ == "__main__":
    raise SystemExit(main())
