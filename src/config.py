from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(ValueError):
    pass


def calculate_required_model_calls(max_review_cycles: int) -> int:
    if not isinstance(max_review_cycles, int) or isinstance(max_review_cycles, bool) or max_review_cycles < 1:
        raise ConfigurationError("Die Anzahl der Prüfzyklen muss mindestens 1 sein.")
    return 2 * max_review_cycles + 2


def validate_model_call_budget(max_review_cycles: int, hard_max_model_calls: int) -> int:
    required_calls = calculate_required_model_calls(max_review_cycles)
    if not isinstance(hard_max_model_calls, int) or isinstance(hard_max_model_calls, bool) or hard_max_model_calls < 1:
        raise ConfigurationError("Die harte Modellaufrufgrenze muss mindestens 1 sein.")
    if required_calls > hard_max_model_calls:
        raise ConfigurationError(
            f"Für {max_review_cycles} Prüfzyklen werden bis zu {required_calls} Modellaufrufe benötigt, "
            f"die Sicherheitsobergrenze erlaubt jedoch nur {hard_max_model_calls}."
        )
    return required_calls


@dataclass(frozen=True)
class AppConfig:
    provider: str = "fake"
    model: str = "gpt-5-mini"
    max_review_cycles: int = 2
    hard_max_model_calls: int = 6
    max_response_chars: int = 4_000
    max_output_tokens: int = 1_000
    logging_enabled: bool = True
    request_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.provider not in {"fake", "openai"}:
            raise ConfigurationError("Provider muss 'fake' oder 'openai' sein.")
        validate_model_call_budget(self.max_review_cycles, self.hard_max_model_calls)
        if self.max_response_chars < 100:
            raise ConfigurationError("Die maximale Antwortlänge muss mindestens 100 Zeichen sein.")
        if not 32 <= self.max_output_tokens <= 2_000:
            raise ConfigurationError("Das Output-Tokenlimit muss zwischen 32 und 2000 liegen.")
        if self.request_timeout_seconds <= 0:
            raise ConfigurationError("Der Provider-Timeout muss größer als 0 sein.")


def _read_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "ja", "yes", "on"}:
        return True
    if normalized in {"0", "false", "nein", "no", "off"}:
        return False
    raise ConfigurationError(f"Ungültiger Wahrheitswert: {value!r}")


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    values = os.environ if environ is None else environ
    return AppConfig(
        provider=values.get("MAS_PROVIDER", "fake").strip().lower(),
        model=values.get("MAS_MODEL", "gpt-5-mini").strip(),
        max_review_cycles=int(values.get("MAS_MAX_REVIEW_CYCLES", "2")),
        hard_max_model_calls=int(values.get("MAS_HARD_MAX_MODEL_CALLS", "6")),
        max_response_chars=int(values.get("MAS_MAX_RESPONSE_CHARS", "4000")),
        max_output_tokens=int(values.get("MAS_MAX_OUTPUT_TOKENS", "1000")),
        logging_enabled=_read_bool(values.get("MAS_LOGGING", "true")),
        request_timeout_seconds=float(values.get("MAS_REQUEST_TIMEOUT_SECONDS", "30")),
    )
