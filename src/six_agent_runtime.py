from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Mapping, Protocol

import httpx2
import openai

from six_agent_openai_bridge import SixAgentOpenAIBridge, SixAgentOpenAIConfig


DEFAULT_HARD_MAX_MODEL_CALLS = 4
MAX_HARD_MODEL_CALLS = 100
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 120.0
_MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class SixAgentRuntimeConfigError(ValueError):
    """Sanitized, non-secret runtime configuration error."""


class SixAgentClientCreationError(RuntimeError):
    """Sanitized client-factory error; the original exception is not exposed."""


@dataclass(frozen=True)
class SixAgentRuntimeConfig:
    model: str = "gpt-5-mini"
    max_output_tokens: int = 1_000
    request_timeout_seconds: float = 30.0
    max_retries: int = 0
    provider_name: str = "openai"
    live_enabled: bool = False
    hard_max_model_calls: int = DEFAULT_HARD_MAX_MODEL_CALLS

    def __post_init__(self) -> None:
        validate_model_name(self.model)
        _validate_positive_int(self.max_output_tokens, "max_output_tokens")
        _validate_timeout(self.request_timeout_seconds)
        if not isinstance(self.max_retries, int) or isinstance(self.max_retries, bool):
            raise SixAgentRuntimeConfigError("max_retries muss eine ganze Zahl sein.")
        if self.max_retries != 0:
            raise SixAgentRuntimeConfigError("max_retries muss für diese Runtime exakt 0 sein.")
        if self.provider_name != "openai":
            raise SixAgentRuntimeConfigError("provider_name muss 'openai' sein.")
        if not isinstance(self.live_enabled, bool):
            raise SixAgentRuntimeConfigError("live_enabled muss ein Boolean sein.")
        _validate_positive_int(self.hard_max_model_calls, "hard_max_model_calls")
        if self.hard_max_model_calls > MAX_HARD_MODEL_CALLS:
            raise SixAgentRuntimeConfigError(
                f"hard_max_model_calls darf höchstens {MAX_HARD_MODEL_CALLS} sein."
            )


@dataclass(frozen=True)
class LiveGateResult:
    live_allowed: bool
    offline_only: bool


def parse_bool(value: str, name: str) -> bool:
    if not isinstance(value, str) or not value.strip():
        raise SixAgentRuntimeConfigError(f"{name} darf nicht leer sein.")
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SixAgentRuntimeConfigError(f"{name} enthält keinen gültigen Boolean.")


def parse_positive_int(value: str, name: str) -> int:
    if not isinstance(value, str) or not value.strip():
        raise SixAgentRuntimeConfigError(f"{name} darf nicht leer sein.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SixAgentRuntimeConfigError(f"{name} muss eine positive ganze Zahl sein.") from None
    _validate_positive_int(parsed, name)
    return parsed


def parse_nonnegative_int(value: str, name: str) -> int:
    if not isinstance(value, str) or not value.strip():
        raise SixAgentRuntimeConfigError(f"{name} darf nicht leer sein.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SixAgentRuntimeConfigError(f"{name} muss eine nichtnegative ganze Zahl sein.") from None
    if parsed < 0:
        raise SixAgentRuntimeConfigError(f"{name} darf nicht negativ sein.")
    return parsed


def parse_positive_float(value: str, name: str) -> float:
    if not isinstance(value, str) or not value.strip():
        raise SixAgentRuntimeConfigError(f"{name} darf nicht leer sein.")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise SixAgentRuntimeConfigError(f"{name} muss eine positive Zahl sein.") from None
    if parsed <= 0:
        raise SixAgentRuntimeConfigError(f"{name} muss positiv sein.")
    return parsed


def validate_model_name(model: str) -> str:
    if not isinstance(model, str) or not model.strip():
        raise SixAgentRuntimeConfigError("MAS6_MODEL darf nicht leer sein.")
    if model != model.strip() or not _MODEL_PATTERN.fullmatch(model):
        raise SixAgentRuntimeConfigError("MAS6_MODEL enthält einen ungültigen Modellnamen.")
    return model


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise SixAgentRuntimeConfigError(f"{name} muss mindestens 1 sein.")


def _validate_timeout(value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise SixAgentRuntimeConfigError("request_timeout_seconds muss eine Zahl sein.")
    if not MIN_TIMEOUT_SECONDS <= float(value) <= MAX_TIMEOUT_SECONDS:
        raise SixAgentRuntimeConfigError(
            f"request_timeout_seconds muss zwischen {MIN_TIMEOUT_SECONDS:g} und "
            f"{MAX_TIMEOUT_SECONDS:g} Sekunden liegen."
        )


def load_nonsecret_runtime_config(
    environment: Mapping[str, str] | None = None,
) -> SixAgentRuntimeConfig:
    """Read only the explicitly supported, non-secret MAS6 variables."""
    source = os.environ if environment is None else environment

    def optional(name: str) -> str | None:
        return source.get(name)

    model_raw = optional("MAS6_MODEL")
    tokens_raw = optional("MAS6_MAX_OUTPUT_TOKENS")
    timeout_raw = optional("MAS6_REQUEST_TIMEOUT_SECONDS")
    retries_raw = optional("MAS6_MAX_RETRIES")
    limit_raw = optional("MAS6_HARD_MAX_MODEL_CALLS")
    live_raw = optional("MAS6_LIVE_ENABLED")

    return SixAgentRuntimeConfig(
        model=validate_model_name(model_raw) if model_raw is not None else "gpt-5-mini",
        max_output_tokens=(
            parse_positive_int(tokens_raw, "MAS6_MAX_OUTPUT_TOKENS")
            if tokens_raw is not None else 1_000
        ),
        request_timeout_seconds=(
            parse_positive_float(timeout_raw, "MAS6_REQUEST_TIMEOUT_SECONDS")
            if timeout_raw is not None else 30.0
        ),
        max_retries=(
            parse_nonnegative_int(retries_raw, "MAS6_MAX_RETRIES")
            if retries_raw is not None else 0
        ),
        live_enabled=(
            parse_bool(live_raw, "MAS6_LIVE_ENABLED") if live_raw is not None else False
        ),
        hard_max_model_calls=(
            parse_positive_int(limit_raw, "MAS6_HARD_MAX_MODEL_CALLS")
            if limit_raw is not None else DEFAULT_HARD_MAX_MODEL_CALLS
        ),
    )


def validate_live_gate(
    *, live_enabled: bool, api_key_present: bool, second_gate_enabled: bool = False,
) -> LiveGateResult:
    for value, name in ((live_enabled, "live_enabled"),
                        (api_key_present, "api_key_present"),
                        (second_gate_enabled, "second_gate_enabled")):
        if not isinstance(value, bool):
            raise SixAgentRuntimeConfigError(f"{name} muss ein Boolean sein.")
    if live_enabled and not api_key_present:
        raise SixAgentRuntimeConfigError(
            "Live-Betrieb ist freigegeben, aber es wurde kein API-Key bereitgestellt."
        )
    allowed = live_enabled and api_key_present and second_gate_enabled
    return LiveGateResult(live_allowed=allowed, offline_only=not allowed)


def build_client_timeout(runtime_config: SixAgentRuntimeConfig) -> httpx2.Timeout:
    """Build phase timeouts, not a guaranteed wall-clock deadline."""
    phase = runtime_config.request_timeout_seconds
    short_phase = min(10.0, phase)
    return httpx2.Timeout(
        connect=short_phase,
        read=phase,
        write=phase,
        pool=short_phase,
    )


class ClientFactory(Protocol):
    def __call__(self, **kwargs: object) -> object: ...


def _official_client_factory(**kwargs: object) -> object:
    return openai.OpenAI(**kwargs)


def create_openai_client(
    api_key: str,
    runtime_config: SixAgentRuntimeConfig,
    *,
    client_factory: ClientFactory = _official_client_factory,
) -> object:
    if not isinstance(api_key, str) or not api_key.strip():
        raise SixAgentRuntimeConfigError("Für die Client-Erzeugung ist ein API-Key erforderlich.")
    client: object | None = None
    failed = False
    try:
        client = client_factory(
            api_key=api_key,
            max_retries=runtime_config.max_retries,
            timeout=build_client_timeout(runtime_config),
        )
    except Exception:
        failed = True
    if failed:
        raise SixAgentClientCreationError(
            "Der OpenAI-Client konnte nicht sicher erzeugt werden; fehlerklasse=ClientFactory."
        )
    if client is None:
        raise SixAgentClientCreationError(
            "Der OpenAI-Client konnte nicht sicher erzeugt werden; fehlerklasse=LeeresErgebnis."
        )
    return client


def create_six_agent_bridge(
    client: object, runtime_config: SixAgentRuntimeConfig,
) -> SixAgentOpenAIBridge:
    bridge_config = SixAgentOpenAIConfig(
        model=runtime_config.model,
        max_output_tokens=runtime_config.max_output_tokens,
        request_timeout_seconds=runtime_config.request_timeout_seconds,
    )
    return SixAgentOpenAIBridge(client=client, config=bridge_config)


def create_six_agent_provider(
    *,
    api_key: str,
    runtime_config: SixAgentRuntimeConfig,
    second_gate_enabled: bool,
    client_factory: ClientFactory = _official_client_factory,
) -> SixAgentOpenAIBridge:
    gate = validate_live_gate(
        live_enabled=runtime_config.live_enabled,
        api_key_present=bool(api_key),
        second_gate_enabled=second_gate_enabled,
    )
    if not gate.live_allowed:
        raise SixAgentRuntimeConfigError(
            "Die zwei expliziten Live-Freigaben sind nicht vollständig gesetzt."
        )
    client = create_openai_client(
        api_key, runtime_config, client_factory=client_factory,
    )
    return create_six_agent_bridge(client, runtime_config)
