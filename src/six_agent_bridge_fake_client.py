from __future__ import annotations

from dataclasses import dataclass, field

from prompts import (
    ANALYST_SYSTEM_PROMPT, PLANER_SYSTEM_PROMPT, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
    SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT, TESTER_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT,
)
from six_agent_state import ModelRole


PROMPT_ROLES = {
    SIX_AGENT_CHEF_ROUTER_SYSTEM_PROMPT: ModelRole.CHEF_ROUTER,
    PLANER_SYSTEM_PROMPT: ModelRole.PLANER,
    ANALYST_SYSTEM_PROMPT: ModelRole.ANALYST,
    UMSETZER_SYSTEM_PROMPT: ModelRole.UMSETZER,
    TESTER_SYSTEM_PROMPT: ModelRole.TESTER,
    SIX_AGENT_REVIEWER_SYSTEM_PROMPT: ModelRole.PRUEFER,
}


@dataclass(frozen=True)
class FakeOpenAICall:
    role: ModelRole
    model: str
    instructions_chars: int
    input_chars: int
    max_output_tokens: int
    reasoning_effort: str
    verbosity: str
    store: bool
    parallel_tool_calls: bool
    timeout: float


@dataclass
class FakeResponsesAPI:
    prepared: list[object]
    call_history: list[FakeOpenAICall] = field(default_factory=list)
    captured_requests: list[dict[str, object]] = field(default_factory=list, repr=False)

    def create(self, **kwargs: object) -> object:
        instructions = kwargs.get("instructions")
        if not isinstance(instructions, str) or instructions not in PROMPT_ROLES:
            raise AssertionError("Unbekannter Rollenprompt im Fake-Responses-Client.")
        user_input = kwargs.get("input")
        if not isinstance(user_input, str):
            raise AssertionError("Der Fake-Responses-Client erwartet Textinput.")
        self.call_history.append(FakeOpenAICall(
            role=PROMPT_ROLES[instructions],
            model=str(kwargs.get("model", "")),
            instructions_chars=len(instructions),
            input_chars=len(user_input),
            max_output_tokens=int(kwargs.get("max_output_tokens", 0)),
            reasoning_effort=str((kwargs.get("reasoning") or {}).get("effort", "")),  # type: ignore[union-attr]
            verbosity=str((kwargs.get("text") or {}).get("verbosity", "")),  # type: ignore[union-attr]
            store=bool(kwargs.get("store")),
            parallel_tool_calls=bool(kwargs.get("parallel_tool_calls")),
            timeout=float(kwargs.get("timeout", 0)),
        ))
        self.captured_requests.append(dict(kwargs))
        if not self.prepared:
            raise AssertionError("Unerwarteter zusätzlicher Fake-responses.create-Aufruf.")
        item = self.prepared.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class FakeOpenAIClient:
    responses: FakeResponsesAPI

    @classmethod
    def from_responses(cls, responses: list[object]) -> "FakeOpenAIClient":
        return cls(FakeResponsesAPI(list(responses)))


def completed_response(
    text: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict[str, object]:
    return {
        "status": "completed",
        "output_text": text,
        "output": [],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


def incomplete_response(partial_text: str = "PARTIAL") -> dict[str, object]:
    return {
        "status": "incomplete",
        "output_text": partial_text,
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": partial_text}]}],
        "usage": {"input_tokens": 1, "output_tokens": 1000, "total_tokens": 1001},
    }
