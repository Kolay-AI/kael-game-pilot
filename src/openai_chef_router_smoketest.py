from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Callable, Mapping, Protocol, Sequence

from prompts import SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT
from route_budget import RouteBudgetError, calculate_route_budget, require_valid_route_budget
from six_agent_contracts import build_chef_router_input, validate_chef_router_output
from six_agent_openai_bridge import SixAgentBridgeError
from six_agent_role_adapter import SixAgentRoleProvider
from six_agent_runtime import (
    ClientFactory,
    SixAgentClientCreationError,
    SixAgentRuntimeConfigError,
    create_openai_client,
    create_six_agent_bridge,
    load_nonsecret_runtime_config,
    validate_live_gate,
)
from six_agent_state import ModelRole
from structured_routing import StructuredOutputError


EXIT_SUCCESS = 0
EXIT_CLI_CONFIG_GATE = 2
EXIT_BUDGET_BLOCK = 3
EXIT_API_RESPONSE_VALIDATION = 4
EXIT_INTERRUPTED = 130


class RouterSmokeConfigurationError(ValueError):
    """Sanitized smoke-test configuration failure."""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise RouterSmokeConfigurationError("Die CLI-Argumente sind ungültig.")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _ArgumentParser(description="Isolierter CHEF_ROUTER Live-Smoke-Test")
    parser.add_argument("--live-chef-router-smoke", action="store_true")
    parser.add_argument("--request")
    return parser.parse_args(list(argv) if argv is not None else None)


def load_openai_api_key(environment: Mapping[str, str] | None = None) -> str:
    """The only secret boundary; replace this function completely in offline tests."""
    source = os.environ if environment is None else environment
    value = source.get("OPENAI_API_KEY")
    if not isinstance(value, str) or not value.strip():
        raise RouterSmokeConfigurationError("Der API-Key fehlt.")
    return value


def _print_route(route) -> None:
    values = (
        ("schema_version", route.schema_version),
        ("complexity", route.complexity.value),
        ("reason_code", route.reason_code.value),
        ("planer", str(route.planer).lower()),
        ("analyst", str(route.analyst).lower()),
        ("umsetzer", str(route.umsetzer).lower()),
        ("tester", str(route.tester).lower()),
        ("pruefer", str(route.pruefer).lower()),
    )
    for name, value in values:
        print(f"[ROUTER-SMOKE] {name}: {value}", flush=True)


def run_router_smoke(
    argv: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    secret_loader: Callable[[], str] | None = None,
    client_factory: ClientFactory | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    try:
        args = _parse_args(argv)
        config = load_nonsecret_runtime_config(environment)
    except (RouterSmokeConfigurationError, SixAgentRuntimeConfigError):
        print("[ROUTER-SMOKE] Konfigurationsfehler", flush=True)
        return EXIT_CLI_CONFIG_GATE

    if not args.live_chef_router_smoke:
        print("[ROUTER-SMOKE] Live-Gate fehlt", flush=True)
        return EXIT_CLI_CONFIG_GATE
    if not config.live_enabled:
        print("[ROUTER-SMOKE] Runtime-Live-Gate fehlt", flush=True)
        return EXIT_CLI_CONFIG_GATE
    if not isinstance(args.request, str) or not args.request.strip():
        print("[ROUTER-SMOKE] Benutzerauftrag fehlt", flush=True)
        return EXIT_CLI_CONFIG_GATE

    try:
        api_key = (
            secret_loader() if secret_loader is not None
            else load_openai_api_key(environment)
        )
        validate_live_gate(
            live_enabled=config.live_enabled,
            api_key_present=bool(api_key),
            second_gate_enabled=args.live_chef_router_smoke,
        )
    except (RouterSmokeConfigurationError, SixAgentRuntimeConfigError):
        print("[ROUTER-SMOKE] API-Key fehlt", flush=True)
        return EXIT_CLI_CONFIG_GATE

    try:
        client = (
            create_openai_client(api_key, config)
            if client_factory is None
            else create_openai_client(api_key, config, client_factory=client_factory)
        )
        bridge: SixAgentRoleProvider = create_six_agent_bridge(client, config)
    except KeyboardInterrupt:
        print("[ROUTER-SMOKE] vom Benutzer abgebrochen", flush=True)
        return EXIT_INTERRUPTED
    except SixAgentClientCreationError:
        print("[ROUTER-SMOKE] Client-Erzeugung fehlgeschlagen", flush=True)
        return EXIT_CLI_CONFIG_GATE
    except Exception:
        print("[ROUTER-SMOKE] Unbekannter kontrollierter Clientfehler", flush=True)
        return EXIT_CLI_CONFIG_GATE

    print("[ROUTER-SMOKE] Start", flush=True)
    print(f"[ROUTER-SMOKE] Modell: {config.model}", flush=True)
    print(f"[ROUTER-SMOKE] Hard-Limit: {config.hard_max_model_calls}", flush=True)
    print("[ROUTER-SMOKE] unmittelbar vor CHEF_ROUTER Request", flush=True)

    started = clock()
    try:
        generated = bridge.generate(
            ModelRole.CHEF_ROUTER,
            SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT,
            build_chef_router_input(args.request),
        )
    except KeyboardInterrupt:
        print("[ROUTER-SMOKE] vom Benutzer abgebrochen", flush=True)
        return EXIT_INTERRUPTED
    except SixAgentBridgeError as exc:
        duration = clock() - started
        print(f"[ROUTER-SMOKE] Dauer: {duration:.1f} s", flush=True)
        print(f"[ROUTER-SMOKE] Fehlerklasse: {exc.kind.value}", flush=True)
        if exc.diagnostic:
            print(f"[ROUTER-SMOKE] Diagnose: {exc.diagnostic}", flush=True)
        return EXIT_API_RESPONSE_VALIDATION
    except Exception:
        duration = clock() - started
        print(f"[ROUTER-SMOKE] Dauer: {duration:.1f} s", flush=True)
        print("[ROUTER-SMOKE] Fehlerklasse: Unbekannt", flush=True)
        return EXIT_API_RESPONSE_VALIDATION

    duration = clock() - started
    print("[ROUTER-SMOKE] Request zurückgekehrt", flush=True)
    print(f"[ROUTER-SMOKE] Dauer: {duration:.1f} s", flush=True)
    try:
        route = validate_chef_router_output(generated.text)
    except (StructuredOutputError, TypeError):
        print("[ROUTER-SMOKE] Fehlerklasse: InvalidResponse/ChefRoute", flush=True)
        return EXIT_API_RESPONSE_VALIDATION

    print("[ROUTER-SMOKE] ChefRoute validiert", flush=True)
    _print_route(route)
    print(f"[ROUTER-SMOKE] input_tokens: {generated.usage.input_tokens}", flush=True)
    print(f"[ROUTER-SMOKE] output_tokens: {generated.usage.output_tokens}", flush=True)
    print(f"[ROUTER-SMOKE] total_tokens: {generated.usage.total_tokens}", flush=True)

    try:
        budget = calculate_route_budget(
            route,
            hard_max_model_calls=config.hard_max_model_calls,
            global_correction_limit=0,
            allowed_correction_paths=frozenset(),
            http_attempts_per_call=1,
            finalizer_is_model=False,
        )
    except RouteBudgetError:
        print("[ROUTER-SMOKE] Fehlerklasse: BudgetBlock", flush=True)
        return EXIT_BUDGET_BLOCK

    print(f"[ROUTER-SMOKE] Required calls: {budget.required_calls}", flush=True)
    print(f"[ROUTER-SMOKE] Hard limit: {budget.hard_limit}", flush=True)
    try:
        require_valid_route_budget(budget)
    except RouteBudgetError:
        print("[ROUTER-SMOKE] Budget: BLOCKIERT", flush=True)
        return EXIT_BUDGET_BLOCK
    print("[ROUTER-SMOKE] Budget: OK", flush=True)
    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    return run_router_smoke(argv)


if __name__ == "__main__":
    raise SystemExit(main())

