from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from config import AppConfig


REQUIRED_ELEMENT = "Prüfkriterium erfüllt: Audit-Protokoll vorhanden."


class ProviderError(RuntimeError):
    """Safe provider error whose message never contains credentials or prompts."""


class ProviderResponseError(ProviderError):
    pass


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _safe_label(value: Any, default: str = "unbekannt") -> str:
    if value is None:
        return default
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(value))[:64]
    return cleaned or default


def _extract_usage_values(response: Any) -> tuple[int, int, int, int]:
    usage = _field(response, "usage")
    input_tokens = int(_field(usage, "input_tokens", 0) or 0)
    output_tokens = int(_field(usage, "output_tokens", 0) or 0)
    reported_total = _field(usage, "total_tokens")
    total_tokens = input_tokens + output_tokens if reported_total is None else int(reported_total)
    output_details = _field(usage, "output_tokens_details")
    reasoning_tokens = int(_field(output_details, "reasoning_tokens", 0) or 0)
    return input_tokens, output_tokens, total_tokens, reasoning_tokens


def _text_value(content: Any) -> str:
    text = _field(content, "text", "")
    if isinstance(text, str):
        return text
    value = _field(text, "value", "")
    return value if isinstance(value, str) else ""


def extract_response_text(response: Any) -> str:
    """Extract visible assistant text from SDK objects or equivalent mock dictionaries."""
    try:
        direct = _field(response, "output_text", "")
    except Exception:
        direct = ""
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    texts: list[str] = []
    for output_item in _field(response, "output", []) or []:
        item_type = _field(output_item, "type")
        if item_type in {"output_text", "text"}:
            text = _text_value(output_item)
            if text:
                texts.append(text)
        if item_type != "message":
            continue
        for content in _field(output_item, "content", []) or []:
            if _field(content, "type") not in {"output_text", "text"}:
                continue
            text = _text_value(content)
            if text:
                texts.append(text)
    return "".join(texts).strip()


def safe_response_diagnostic(response: Any) -> str:
    """Return structural diagnostics only: never IDs, prompts, response text or secrets."""
    input_tokens, output_tokens, total_tokens, reasoning_tokens = _extract_usage_values(response)
    incomplete = _field(response, "incomplete_details")
    error = _field(response, "error")
    output_types: list[str] = []
    content_types: list[str] = []
    for item in _field(response, "output", []) or []:
        output_types.append(_safe_label(_field(item, "type")))
        for content in _field(item, "content", []) or []:
            content_types.append(_safe_label(_field(content, "type")))
    return "; ".join(
        (
            f"status={_safe_label(_field(response, 'status'))}",
            f"incomplete_reason={_safe_label(_field(incomplete, 'reason'), 'keiner')}",
            f"error_code={_safe_label(_field(error, 'code'), 'keiner')}",
            f"output_types={','.join(output_types) if output_types else 'keine'}",
            f"content_types={','.join(content_types) if content_types else 'keine'}",
            f"input_tokens={input_tokens}",
            f"output_tokens={output_tokens}",
            f"reasoning_tokens={reasoning_tokens}",
            f"total_tokens={total_tokens}",
        )
    )


@dataclass(frozen=True)
class UsageData:
    agent: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "provider": self.provider,
            "modell": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "gesamt_tokens": self.total_tokens,
            "geschaetzte_kosten": self.estimated_cost,
        }


@dataclass(frozen=True)
class GenerationResult:
    text: str
    usage: UsageData


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        """Generate text for one role without exposing provider details to the agent."""


class LogicalCallLimitProvider:
    """Workflow-scoped guard; HTTP retries remain internal to one logical call."""

    def __init__(self, provider: LLMProvider, maximum: int = 6) -> None:
        self._provider = provider
        self.maximum = maximum
        self.logical_call_count = 0
        self.name = provider.name
        self.model = provider.model

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        if self.logical_call_count >= self.maximum:
            raise ProviderError(
                f"Sicherheitsgrenze von maximal {self.maximum} logischen API-Aufrufen erreicht."
            )
        self.logical_call_count += 1
        return self._provider.generate(agent, system_prompt, user_prompt)


class FakeLLMProvider:
    name = "fake"

    def __init__(self, model: str = "fake-deterministic", max_response_chars: int = 4_000) -> None:
        self.model = model
        self.max_response_chars = max_response_chars
        self.cloud_call_count = 0

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        del system_prompt
        if agent == "CHEF":
            if "GEPRÜFTES ERGEBNIS:" in user_prompt:
                text = user_prompt.split("GEPRÜFTES ERGEBNIS:", 1)[1].strip()
            else:
                text = f"Bearbeite den folgenden Auftrag nachvollziehbar:\n{user_prompt.strip()}"
        elif agent == "SPEZIALIST":
            if "PRÜFERKRITIK:" in user_prompt:
                criticism = user_prompt.split("PRÜFERKRITIK:", 1)[1].strip()
                text = (
                    "Ergebnis: Der lokale Drei-Agenten-Ablauf wurde beschrieben.\n"
                    f"Verbesserung aufgrund der Prüferkritik: {criticism}\n"
                    f"{REQUIRED_ELEMENT}"
                )
            else:
                text = "Ergebnis: Der lokale Drei-Agenten-Ablauf wurde beschrieben."
        elif agent == "PRÜFER":
            result_section = user_prompt.split("ERGEBNIS:\n", 1)[-1]
            accepted = REQUIRED_ELEMENT in result_section
            payload = {
                "entscheidung": "AKZEPTIERT" if accepted else "ABGELEHNT",
                "begruendung": (
                    "Alle geforderten Elemente sind vorhanden."
                    if accepted else "Das geforderte Element zum Audit-Protokoll fehlt."
                ),
                "verbesserungen": [] if accepted else ["Audit-Protokoll ergänzen"],
            }
            text = json.dumps(payload, ensure_ascii=False)
        else:
            raise ProviderError(f"Unbekannte Agentenrolle: {agent}")

        return GenerationResult(
            text=text[: self.max_response_chars],
            usage=UsageData(agent=agent, provider=self.name, model=self.model),
        )


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        model: str,
        api_key: str,
        max_response_chars: int = 1_200,
        max_output_tokens: int = 1_000,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
        clock: Any = time.monotonic,
        max_attempts: int = 2,
    ) -> None:
        if not api_key:
            raise ProviderError(
                "OpenAI-Modus wurde gewählt, aber OPENAI_API_KEY ist nicht gesetzt. "
                "Es wurde kein API-Aufruf ausgeführt."
            )
        self.model = model
        self._api_key = api_key
        self.max_response_chars = max_response_chars
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._clock = clock
        self.http_attempt_count = 0
        if max_attempts not in {1, 2}:
            raise ValueError("Es sind nur ein oder zwei HTTP-Versuche zulässig.")
        self.max_attempts = max_attempts
        from httpx2 import Timeout

        self._request_timeout = Timeout(
            self.timeout_seconds,
            connect=min(10.0, self.timeout_seconds),
            read=self.timeout_seconds,
            write=min(10.0, self.timeout_seconds),
            pool=min(5.0, self.timeout_seconds),
        )

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._api_key,
                timeout=self._request_timeout,
                max_retries=0,
            )
        return self._client

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError

        started = self._clock()
        print(f"[API] {agent} gestartet", flush=True)
        response = None
        for attempt in range(self.max_attempts):
            try:
                self.http_attempt_count += 1
                request: dict[str, Any] = {
                    "model": self.model,
                    "instructions": system_prompt,
                    "input": user_prompt,
                    "max_output_tokens": self.max_output_tokens,
                    "parallel_tool_calls": False,
                    "store": False,
                    "text": {"verbosity": "low"},
                    "timeout": self._request_timeout,
                }
                if self.model == "gpt-5-mini":
                    request["reasoning"] = {"effort": "minimal"}
                estimated_input_tokens = math.ceil((len(system_prompt) + len(user_prompt)) / 4)
                print(
                    f"[API-METADATEN] rolle={agent}; input_nachrichten=1; "
                    f"system_zeichen={len(system_prompt)}; user_zeichen={len(user_prompt)}; "
                    f"input_tokens_geschaetzt={estimated_input_tokens}; modell={self.model}; "
                    f"max_output_tokens={self.max_output_tokens}; reasoning=minimal; verbosity=low",
                    flush=True,
                )
                print(f"[API] {agent} unmittelbar vor responses.create() – Versuch {attempt + 1}", flush=True)
                response = self._get_client().responses.create(**request)
                print(f"[API] {agent} unmittelbar nach responses.create() – Versuch {attempt + 1}", flush=True)
                break
            except AuthenticationError as exc:
                self._print_failure(agent, started, "Authentifizierung")
                raise ProviderError("OpenAI-Authentifizierung fehlgeschlagen. Schlüssel und Berechtigungen prüfen.") from exc
            except RateLimitError as exc:
                self._print_failure(agent, started, "Ratenlimit")
                raise ProviderError("OpenAI-Ratenlimit erreicht. Der Workflow wurde ohne Retry beendet.") from exc
            except (APITimeoutError, APIConnectionError) as exc:
                error_class = "Timeout" if isinstance(exc, APITimeoutError) else "Netzwerk"
                print(f"[API] {agent} {error_class} bei Versuch {attempt + 1}", flush=True)
                if attempt + 1 < self.max_attempts:
                    print(f"[API] {agent} vor einmaligem Retry", flush=True)
                    continue
                self._print_failure(agent, started, error_class)
                suffix = " nach einem Retry" if self.max_attempts == 2 else " ohne Retry"
                raise ProviderError(f"OpenAI-Netzwerkfehler oder Timeout{suffix}.") from exc
            except APIStatusError as exc:
                self._print_failure(agent, started, "APIStatus")
                raise ProviderError(f"OpenAI-API-Fehler mit Status {exc.status_code}.") from exc

        if response is None:
            self._print_failure(agent, started, "KeineResponse")
            raise ProviderResponseError("OpenAI lieferte kein Response-Objekt.")

        diagnostic = safe_response_diagnostic(response)
        status = _field(response, "status")
        if status and status != "completed":
            self._print_failure(agent, started, "UnvollstaendigeResponse")
            raise ProviderResponseError(f"OpenAI-Response war nicht vollständig. {diagnostic}")

        text = extract_response_text(response)
        if not text:
            self._print_failure(agent, started, "LeereResponse")
            raise ProviderResponseError(f"OpenAI lieferte keine verwendbare Textantwort. {diagnostic}")

        input_tokens, output_tokens, total_tokens, _ = _extract_usage_values(response)
        duration = self._clock() - started
        print(f"[API] {agent} beendet – Dauer: {duration:.1f} s – Tokens: {total_tokens}", flush=True)
        return GenerationResult(
            text=text[: self.max_response_chars],
            usage=UsageData(
                agent=agent,
                provider=self.name,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
        )

    def _print_failure(self, agent: str, started: float, error_class: str) -> None:
        duration = self._clock() - started
        print(
            f"[API] {agent} fehlgeschlagen – Dauer: {duration:.1f} s – Fehlerklasse: {error_class}",
            flush=True,
        )


def create_provider(config: AppConfig, environ: Mapping[str, str] | None = None, client: Any | None = None) -> LLMProvider:
    if config.provider == "fake":
        return FakeLLMProvider(max_response_chars=config.max_response_chars)
    values = os.environ if environ is None else environ
    return OpenAIProvider(
        model=config.model,
        api_key=values.get("OPENAI_API_KEY", ""),
        max_response_chars=config.max_response_chars,
        max_output_tokens=config.max_output_tokens,
        timeout_seconds=config.request_timeout_seconds,
        client=client,
    )
