from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Protocol

import openai

from six_agent_role_adapter import AdapterGenerationResult, AdapterUsageData
from six_agent_state import ModelRole
from structured_routing import ChefReasonCode, Complexity


class BridgeErrorKind(str, Enum):
    TIMEOUT = "Timeout"
    CONNECTION = "Connection"
    AUTHENTICATION = "Authentication"
    RATE_LIMIT = "RateLimit"
    API_STATUS = "APIStatus"
    INVALID_RESPONSE = "InvalidResponse"
    INCOMPLETE_RESPONSE = "IncompleteResponse"
    UNKNOWN = "Unknown"


class SixAgentBridgeError(RuntimeError):
    """Sanitized bridge error: never contains prompts, response text, IDs or SDK details."""

    def __init__(self, kind: BridgeErrorKind, diagnostic: str = "") -> None:
        self.kind = kind
        self.diagnostic = diagnostic
        message = f"OpenAI-Bridgefehler; klasse={kind.value}"
        if diagnostic:
            message = f"{message}; {diagnostic}"
        super().__init__(message)


@dataclass(frozen=True)
class SixAgentOpenAIConfig:
    model: str = "gpt-5-mini"
    max_output_tokens: int = 1_000
    request_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Das Bridge-Modell darf nicht leer sein.")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens muss mindestens 1 sein.")
        if self.request_timeout_seconds <= 0:
            raise ValueError("Der Request-Timeout muss positiv sein.")


class ResponsesAPI(Protocol):
    def create(self, **kwargs: object) -> object: ...


class InjectedOpenAIClient(Protocol):
    responses: ResponsesAPI


def chef_router_text_config() -> dict[str, object]:
    """Return the strict SDK 3.3.1 Responses text format for the router contract."""
    properties: dict[str, object] = {
        "schema_version": {"type": "integer", "enum": [1]},
        "planer": {"type": "boolean"},
        "analyst": {"type": "boolean"},
        "umsetzer": {"type": "boolean"},
        "tester": {"type": "boolean"},
        "pruefer": {"type": "boolean"},
        "complexity": {
            "type": "string",
            "enum": [item.value for item in Complexity],
        },
        "reason_code": {
            "type": "string",
            "enum": [item.value for item in ChefReasonCode],
        },
    }
    return {
        "verbosity": "low",
        "format": {
            "type": "json_schema",
            "name": "chef_route",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _text_value(content: Any) -> str:
    text = _field(content, "text", "")
    if isinstance(text, str):
        return text
    nested = _field(text, "value", "")
    return nested if isinstance(nested, str) else ""


def extract_visible_text(response: Any) -> str:
    """Extract visible text only; reasoning items are deliberately ignored."""
    try:
        direct = _field(response, "output_text", "")
    except Exception:
        direct = ""
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    blocks: list[str] = []
    for item in _field(response, "output", []) or []:
        item_type = _field(item, "type", "")
        if item_type in {"output_text", "text"}:
            value = _text_value(item)
            if value:
                blocks.append(value)
            continue
        if item_type != "message":
            continue
        for content in _field(item, "content", []) or []:
            if _field(content, "type", "") not in {"output_text", "text"}:
                continue
            value = _text_value(content)
            if value:
                blocks.append(value)
    return "".join(blocks).strip()


def _usage_values(response: Any) -> tuple[int, int, int, int]:
    usage = _field(response, "usage")
    input_tokens = int(_field(usage, "input_tokens", 0) or 0)
    output_tokens = int(_field(usage, "output_tokens", 0) or 0)
    reported_total = _field(usage, "total_tokens")
    total_tokens = input_tokens + output_tokens if reported_total is None else int(reported_total or 0)
    details = _field(usage, "output_tokens_details")
    reasoning_tokens = int(_field(details, "reasoning_tokens", 0) or 0)
    return input_tokens, output_tokens, total_tokens, reasoning_tokens


def _safe_label(value: Any, default: str = "unbekannt") -> str:
    if value is None:
        return default
    cleaned = "".join(character if character.isalnum() or character in "_.:-" else "_" for character in str(value))[:64]
    return cleaned or default


def safe_response_diagnostic(response: Any) -> str:
    input_tokens, output_tokens, total_tokens, reasoning_tokens = _usage_values(response)
    incomplete = _field(response, "incomplete_details")
    output_types = [
        _safe_label(_field(item, "type"))
        for item in (_field(response, "output", []) or [])
    ]
    return "; ".join((
        f"status={_safe_label(_field(response, 'status'))}",
        f"incomplete_reason={_safe_label(_field(incomplete, 'reason'), 'keiner')}",
        f"output_types={','.join(output_types) if output_types else 'keine'}",
        f"input_tokens={input_tokens}",
        f"output_tokens={output_tokens}",
        f"reasoning_tokens={reasoning_tokens}",
        f"total_tokens={total_tokens}",
    ))


def _error_kind(exc: Exception) -> BridgeErrorKind:
    if isinstance(exc, openai.APITimeoutError):
        return BridgeErrorKind.TIMEOUT
    if isinstance(exc, openai.AuthenticationError):
        return BridgeErrorKind.AUTHENTICATION
    if isinstance(exc, openai.RateLimitError):
        return BridgeErrorKind.RATE_LIMIT
    if isinstance(exc, openai.APIConnectionError):
        return BridgeErrorKind.CONNECTION
    if isinstance(exc, openai.APIStatusError):
        return BridgeErrorKind.API_STATUS
    if isinstance(exc, openai.APIResponseValidationError):
        return BridgeErrorKind.INVALID_RESPONSE
    return BridgeErrorKind.UNKNOWN


def _safe_api_error_value(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return "unknown"
    if not all(
        character.isascii() and (character.isalnum() or character in "_.-")
        for character in value
    ):
        return "unknown"
    lowered = value.lower()
    if any(marker in lowered for marker in (
        "secret", "token", "api_key", "apikey", "authorization", "bearer",
        "password", "credential", "request_id", "response_id",
    )):
        return "unknown"
    return value


def _safe_api_error_class(exc: openai.APIStatusError) -> str:
    if isinstance(exc, openai.BadRequestError):
        return "BadRequest"
    if isinstance(exc, openai.AuthenticationError):
        return "Authentication"
    if isinstance(exc, openai.PermissionDeniedError):
        return "PermissionDenied"
    if isinstance(exc, openai.NotFoundError):
        return "NotFound"
    if isinstance(exc, openai.ConflictError):
        return "Conflict"
    if isinstance(exc, openai.UnprocessableEntityError):
        return "UnprocessableEntity"
    if isinstance(exc, openai.RateLimitError):
        return "RateLimit"
    status_code = getattr(exc, "status_code", None)
    if isinstance(exc, openai.InternalServerError) or (
        isinstance(status_code, int)
        and not isinstance(status_code, bool)
        and 500 <= status_code <= 599
    ):
        return "ServerError"
    return "Unknown"


def safe_api_status_diagnostic(exc: openai.APIStatusError) -> str:
    """Expose only allowlisted, bounded API status metadata."""
    status_code = getattr(exc, "status_code", None)
    safe_status = (
        str(status_code)
        if isinstance(status_code, int)
        and not isinstance(status_code, bool)
        and 100 <= status_code <= 599
        else "unknown"
    )
    return "; ".join((
        f"status_code={safe_status}",
        f"api_error_class={_safe_api_error_class(exc)}",
        f"api_error_code={_safe_api_error_value(getattr(exc, 'code', None))}",
        f"api_error_type={_safe_api_error_value(getattr(exc, 'type', None))}",
    ))


class SixAgentOpenAIBridge:
    """Injected-client Responses bridge with no retry and no state or routing knowledge.

    The request timeout is passed to the SDK/HTTP layer. It is phase/network oriented
    and is not a guaranteed wall-clock deadline for the complete Python call.
    """

    def __init__(self, client: InjectedOpenAIClient, config: SixAgentOpenAIConfig) -> None:
        self._client = client
        self.config = config

    def generate(
        self, role: ModelRole, system_prompt: str, user_input: str,
    ) -> AdapterGenerationResult:
        text_config = (
            chef_router_text_config()
            if role is ModelRole.CHEF_ROUTER
            else {"verbosity": "low"}
        )
        try:
            response = self._client.responses.create(
                model=self.config.model,
                instructions=system_prompt,
                input=user_input,
                max_output_tokens=self.config.max_output_tokens,
                reasoning={"effort": "minimal"},
                text=text_config,
                store=False,
                parallel_tool_calls=False,
                timeout=self.config.request_timeout_seconds,
            )
        except SixAgentBridgeError:
            raise
        except Exception as exc:
            diagnostic = (
                safe_api_status_diagnostic(exc)
                if isinstance(exc, openai.APIStatusError)
                else ""
            )
            raise SixAgentBridgeError(_error_kind(exc), diagnostic) from None

        status = _field(response, "status")
        if status != "completed":
            diagnostic = safe_response_diagnostic(response)
            kind = (
                BridgeErrorKind.INCOMPLETE_RESPONSE
                if status == "incomplete" else BridgeErrorKind.INVALID_RESPONSE
            )
            raise SixAgentBridgeError(kind, diagnostic)
        text = extract_visible_text(response)
        if not text:
            raise SixAgentBridgeError(
                BridgeErrorKind.INVALID_RESPONSE,
                safe_response_diagnostic(response),
            )
        input_tokens, output_tokens, total_tokens, _ = _usage_values(response)
        return AdapterGenerationResult(
            text=text,
            usage=AdapterUsageData(
                role=role.value,
                provider="openai-six-agent",
                model=self.config.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
        )
