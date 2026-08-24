from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import openai
import httpx2
import pytest


PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from openai.resources.responses.responses import Responses  # noqa: E402
from openai.types.responses.response_format_text_json_schema_config_param import (  # noqa: E402
    ResponseFormatTextJSONSchemaConfigParam,
)
from openai.types.responses.response_text_config_param import ResponseTextConfigParam  # noqa: E402
from prompts import (  # noqa: E402
    ANALYST_SYSTEM_PROMPT, PLANER_SYSTEM_PROMPT, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
    TESTER_SYSTEM_PROMPT, UMSETZER_SYSTEM_PROMPT,
)
from six_agent_contracts import (  # noqa: E402
    build_analyst_input, build_implementer_input, build_planner_input,
    build_reviewer_input, build_tester_input,
)
from six_agent_openai_bridge import (  # noqa: E402
    BridgeErrorKind, SixAgentBridgeError, SixAgentOpenAIBridge,
    SixAgentOpenAIConfig, chef_router_text_config, extract_visible_text,
)
from six_agent_role_adapter import (  # noqa: E402
    SafeRoleDiagnostic, run_analyst, run_implementer, run_planner, run_reviewer, run_tester,
)
from six_agent_state import ModelRole, create_initial_six_agent_state  # noqa: E402


class FakeResponses:
    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.items:
            raise AssertionError("Unerwarteter zweiter responses.create-Aufruf")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, *items):
        self.responses = FakeResponses(*items)


def _usage_object(input_tokens=3, output_tokens=4, total_tokens=7, reasoning_tokens=0):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens,
        output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning_tokens),
    )


def _completed(text="OK", *, usage=None):
    return SimpleNamespace(status="completed", output_text=text, output=[], usage=usage or _usage_object())


def _bridge(response, **config):
    client = FakeClient(response)
    return SixAgentOpenAIBridge(client, SixAgentOpenAIConfig(**config)), client


def _tester_json():
    return json.dumps({"entscheidung": "BESTANDEN", "fehlerursprung": "UNKLAR",
                       "begruendung": "Bestanden", "verbesserungen": []})


def _review_json():
    return json.dumps({"entscheidung": "AKZEPTIERT", "fehlerursprung": "UNKLAR",
                       "begruendung": "Akzeptiert", "verbesserungen": []})


def test_installed_sdk_signature_supports_every_bridge_request_parameter() -> None:
    assert openai.__version__ == "3.3.1"
    parameters = set(inspect.signature(Responses.create).parameters)
    assert {"model", "instructions", "input", "max_output_tokens", "reasoning", "text",
            "store", "parallel_tool_calls", "timeout"} <= parameters


def test_installed_sdk_331_types_support_strict_json_schema_text_format() -> None:
    assert openai.__version__ == "3.3.1"
    assert "format" in ResponseTextConfigParam.__annotations__
    assert {"type", "name", "schema", "strict"} <= set(
        ResponseFormatTextJSONSchemaConfigParam.__annotations__
    )


def test_request_mapping_is_exact_and_has_no_tools_or_extra_parameters() -> None:
    bridge, client = _bridge(_completed(), model="gpt-5-mini", max_output_tokens=777, request_timeout_seconds=31.5)
    result = bridge.generate(ModelRole.PLANER, "SYSTEM", "USER")
    assert result.text == "OK"
    assert client.responses.calls == [{
        "model": "gpt-5-mini", "instructions": "SYSTEM", "input": "USER",
        "max_output_tokens": 777, "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"}, "store": False,
        "parallel_tool_calls": False, "timeout": 31.5,
    }]
    assert "tools" not in client.responses.calls[0]


def test_completed_planner_response_has_safe_content_free_diagnostic() -> None:
    secret = "PLAN_RESPONSE_SECRET"
    bridge, _ = _bridge(_completed(f"- Schritt eins\n- {secret}"))
    result = bridge.generate(ModelRole.PLANER, "PROMPT_SECRET", "USER_SECRET")
    diagnostic = result.diagnostic.as_dict()
    assert diagnostic == {
        "role": "PLANER",
        "layer": "bridge", "reason_code": "completed",
        "response_status": "completed", "output_empty": False,
        "output_char_count": len(result.text), "output_word_count": 5,
        "word_limit_exceeded": None, "char_limit_exceeded": None,
        "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
        "markdown_codeblock_present": False, "list_structure_present": True,
    }
    assert all(marker not in str(diagnostic) for marker in (
        secret, "PROMPT_SECRET", "USER_SECRET",
    ))


@pytest.mark.parametrize("role", list(ModelRole))
def test_bridge_diagnostic_uses_actual_role_without_evaluating_contract_limits(role) -> None:
    bridge, client = _bridge(_completed("- SAFE_VISIBLE_TEXT"))
    diagnostic = bridge.generate(role, "PROMPT_SECRET", "USER_SECRET").diagnostic.as_dict()
    assert diagnostic["role"] == role.value
    assert diagnostic["layer"] == "bridge"
    assert diagnostic["word_limit_exceeded"] is None
    assert diagnostic["char_limit_exceeded"] is None
    assert len(client.responses.calls) == 1
    assert all(marker not in str(diagnostic) for marker in (
        "SAFE_VISIBLE_TEXT", "PROMPT_SECRET", "USER_SECRET",
    ))


@pytest.mark.parametrize("role", list(ModelRole))
@pytest.mark.parametrize(("response", "status", "reason"), [
    (_completed(""), "completed", "empty_output"),
    ({"status": "incomplete", "output_text": "PARTIAL_SECRET", "output": [],
      "usage": {"input_tokens": 8, "output_tokens": 9, "total_tokens": 17}},
     "incomplete", "IncompleteResponse"),
    ({"status": "failed", "output_text": "FAILED_SECRET", "output": [],
      "usage": {"input_tokens": 5, "output_tokens": 0, "total_tokens": 5}},
     "failed", "InvalidResponse"),
])
def test_bridge_failures_have_safe_structured_diagnostic_for_actual_role(
    response, status, reason, role,
) -> None:
    bridge, _ = _bridge(response)
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(role, "PROMPT_SECRET", "USER_SECRET")
    diagnostic = caught.value.safe_diagnostic.as_dict()
    assert diagnostic["role"] == role.value
    assert diagnostic["layer"] == "bridge"
    assert diagnostic["response_status"] == status
    assert diagnostic["reason_code"] == reason
    assert diagnostic["word_limit_exceeded"] is None
    assert diagnostic["char_limit_exceeded"] is None
    assert all(marker not in str(diagnostic) for marker in (
        "PARTIAL_SECRET", "FAILED_SECRET", "PROMPT_SECRET", "USER_SECRET",
    ))


def test_chef_router_request_uses_exact_strict_structured_output_schema() -> None:
    bridge, client = _bridge(_completed())
    bridge.generate(ModelRole.CHEF_ROUTER, "SYSTEM", "USER")
    request = client.responses.calls[0]
    assert request["text"] == chef_router_text_config()
    assert request["text"] == {
        "verbosity": "low",
        "format": {
            "type": "json_schema",
            "name": "chef_route",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "schema_version": {"type": "integer", "enum": [1]},
                    "planer": {"type": "boolean"},
                    "analyst": {"type": "boolean"},
                    "umsetzer": {"type": "boolean"},
                    "tester": {"type": "boolean"},
                    "pruefer": {"type": "boolean"},
                    "complexity": {
                        "type": "string",
                        "enum": ["EINFACH", "MITTEL", "KOMPLEX"],
                    },
                    "reason_code": {
                        "type": "string",
                        "enum": [
                            "DIREKTE_UMSETZUNG", "PLANUNG_ERFORDERLICH",
                            "ANALYSE_ERFORDERLICH", "VOLLSTAENDIGE_BEARBEITUNG",
                        ],
                    },
                },
                "required": [
                    "schema_version", "planer", "analyst", "umsetzer",
                    "tester", "pruefer", "complexity", "reason_code",
                ],
                "additionalProperties": False,
            },
        },
    }
    assert "json_schema" not in request["text"]["format"]
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize("role", [ModelRole.PLANER, ModelRole.ANALYST])
def test_non_router_roles_keep_plain_text_request_mapping(role: ModelRole) -> None:
    bridge, client = _bridge(_completed())
    bridge.generate(role, "SYSTEM", "USER")
    assert client.responses.calls[0]["text"] == {"verbosity": "low"}


def test_implementer_gets_sufficient_output_budget_without_changing_config_default() -> None:
    bridge, client = _bridge(_completed(), max_output_tokens=1_000)
    bridge.generate(ModelRole.UMSETZER, "SYSTEM", "USER")
    assert bridge.config.max_output_tokens == 1_000
    assert client.responses.calls[0]["max_output_tokens"] == 1_600
    assert client.responses.calls[0]["reasoning"] == {"effort": "minimal"}
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(("role", "name", "decisions", "origins"), [
    (ModelRole.TESTER, "tester_result", ["BESTANDEN", "FEHLER"],
     ["UMSETZUNG", "TEST", "UNKLAR"]),
    (ModelRole.PRUEFER, "review_result", ["AKZEPTIERT", "ABGELEHNT", "UNKLAR"],
     ["PLANUNG", "ANALYSE", "UMSETZUNG", "TEST", "UNKLAR"]),
])
def test_structured_roles_use_strict_responses_json_schema(role, name, decisions, origins) -> None:
    bridge, client = _bridge(_completed())
    bridge.generate(role, "SYSTEM", "USER")
    text = client.responses.calls[0]["text"]
    assert text["verbosity"] == "low"
    assert text["format"]["type"] == "json_schema"
    assert text["format"]["name"] == name
    assert text["format"]["strict"] is True
    schema = text["format"]["schema"]
    assert schema["required"] == [
        "entscheidung", "fehlerursprung", "begruendung", "verbesserungen",
    ]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["entscheidung"]["enum"] == decisions
    assert schema["properties"]["fehlerursprung"]["enum"] == origins
    assert schema["properties"]["begruendung"] == {"type": "string"}
    assert schema["properties"]["verbesserungen"] == {
        "type": "array", "items": {"type": "string"},
    }


def test_completed_output_text_and_object_usage_map_to_adapter_result() -> None:
    bridge, _ = _bridge(_completed("Antwort", usage=_usage_object(11, 13, 24, 5)))
    result = bridge.generate(ModelRole.ANALYST, "S", "U")
    assert result.text == "Antwort"
    assert result.usage.role == ModelRole.ANALYST.value
    assert result.usage.provider == "openai-six-agent"
    assert (result.usage.input_tokens, result.usage.output_tokens, result.usage.total_tokens) == (11, 13, 24)
    assert not hasattr(result.usage, "reasoning_tokens")


def test_empty_output_text_falls_back_to_message_content() -> None:
    response = SimpleNamespace(
        status="completed", output_text="",
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text="Fallback")])],
        usage=_usage_object(),
    )
    bridge, _ = _bridge(response)
    assert bridge.generate(ModelRole.UMSETZER, "S", "U").text == "Fallback"


def test_multiple_visible_blocks_are_joined_in_order() -> None:
    response = {"status": "completed", "output_text": "", "usage": {}, "output": [
        {"type": "message", "content": [
            {"type": "output_text", "text": "Teil 1 "},
            {"type": "output_text", "text": {"value": "Teil 2"}},
        ]},
        {"type": "output_text", "text": " Teil 3"},
    ]}
    assert extract_visible_text(response) == "Teil 1 Teil 2 Teil 3"


def test_dictionary_response_and_usage_are_supported() -> None:
    response = {"status": "completed", "output_text": "Dict", "output": [],
                "usage": {"input_tokens": 2, "output_tokens": 5, "total_tokens": 7}}
    bridge, _ = _bridge(response)
    result = bridge.generate(ModelRole.TESTER, "S", "U")
    assert result.text == "Dict" and result.usage.total_tokens == 7


def test_reasoning_item_is_never_extracted_as_visible_text() -> None:
    response = {"status": "completed", "output_text": "", "usage": {}, "output": [
        {"type": "reasoning", "text": "PRIVATE_REASONING_MARKER",
         "content": [{"type": "output_text", "text": "ALSO_PRIVATE"}]},
        {"type": "message", "content": [{"type": "output_text", "text": "Sichtbar"}]},
    ]}
    bridge, _ = _bridge(response)
    assert bridge.generate(ModelRole.PRUEFER, "S", "U").text == "Sichtbar"


@pytest.mark.parametrize("status", ["failed", "cancelled", "queued", "in_progress"])
def test_every_noncompleted_status_fails_closed(status) -> None:
    bridge, client = _bridge({"status": status, "output_text": "PARTIAL_SECRET", "output": [], "usage": {}})
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.PLANER, "S", "U")
    assert caught.value.kind is BridgeErrorKind.INVALID_RESPONSE
    assert "PARTIAL_SECRET" not in str(caught.value)
    assert len(client.responses.calls) == 1


def test_incomplete_max_tokens_has_safe_technical_diagnostic_and_rejects_partial_text() -> None:
    secret = "TOP_SECRET_RESPONSE_MARKER"
    response = {"status": "incomplete", "output_text": secret,
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [{"type": "message", "content": [{"type": "output_text", "text": secret}]}],
        "usage": {"input_tokens": 10, "output_tokens": 1000, "total_tokens": 1010,
                  "output_tokens_details": {"reasoning_tokens": 25}}, "id": "resp-secret-id"}
    bridge, _ = _bridge(response)
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.PLANER, "TOP_SECRET_PROMPT_MARKER", "USER_SECRET")
    message = str(caught.value)
    assert caught.value.kind is BridgeErrorKind.INCOMPLETE_RESPONSE
    for expected in ("status=incomplete", "incomplete_reason=max_output_tokens", "input_tokens=10",
                     "output_tokens=1000", "reasoning_tokens=25", "total_tokens=1010"):
        assert expected in message
    for forbidden in (secret, "TOP_SECRET_PROMPT_MARKER", "USER_SECRET", "resp-secret-id"):
        assert forbidden not in message


def test_completed_without_visible_text_fails_closed() -> None:
    bridge, _ = _bridge({"status": "completed", "output_text": "", "output": [{"type": "reasoning"}], "usage": {}})
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.PLANER, "S", "U")
    assert caught.value.kind is BridgeErrorKind.INVALID_RESPONSE


def test_provider_exception_is_sanitized_and_never_retried() -> None:
    marker = "sk-test-super-secret TOP_SECRET_PROMPT_MARKER USERINPUT RESPONSE-ID"
    client = FakeClient(RuntimeError(marker))
    bridge = SixAgentOpenAIBridge(client, SixAgentOpenAIConfig())
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.PLANER, marker, marker)
    assert caught.value.kind is BridgeErrorKind.UNKNOWN
    assert marker not in str(caught.value)
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(("exception_factory", "kind"), [
    (lambda request, response: openai.APITimeoutError(request), BridgeErrorKind.TIMEOUT),
    (lambda request, response: openai.APIConnectionError(message="secret connection", request=request), BridgeErrorKind.CONNECTION),
    (lambda request, response: openai.AuthenticationError("secret auth", response=response, body=None), BridgeErrorKind.AUTHENTICATION),
    (lambda request, response: openai.RateLimitError("secret rate", response=response, body=None), BridgeErrorKind.RATE_LIMIT),
    (lambda request, response: openai.APIStatusError("secret status", response=response, body=None), BridgeErrorKind.API_STATUS),
])
def test_sdk_exception_categories_are_sanitized(exception_factory, kind) -> None:
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    response = httpx2.Response(429, request=request)
    client = FakeClient(exception_factory(request, response))
    bridge = SixAgentOpenAIBridge(client, SixAgentOpenAIConfig())
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.PLANER, "TOP_SECRET_PROMPT_MARKER", "USER_SECRET")
    assert caught.value.kind is kind
    assert "secret" not in str(caught.value).lower()
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize(("error_class", "status", "safe_class", "kind"), [
    (openai.BadRequestError, 400, "BadRequest", BridgeErrorKind.API_STATUS),
    (openai.AuthenticationError, 401, "Authentication", BridgeErrorKind.AUTHENTICATION),
    (openai.PermissionDeniedError, 403, "PermissionDenied", BridgeErrorKind.API_STATUS),
    (openai.NotFoundError, 404, "NotFound", BridgeErrorKind.API_STATUS),
    (openai.ConflictError, 409, "Conflict", BridgeErrorKind.API_STATUS),
    (openai.UnprocessableEntityError, 422, "UnprocessableEntity", BridgeErrorKind.API_STATUS),
    (openai.RateLimitError, 429, "RateLimit", BridgeErrorKind.RATE_LIMIT),
    (openai.InternalServerError, 503, "ServerError", BridgeErrorKind.API_STATUS),
    (openai.APIStatusError, 418, "Unknown", BridgeErrorKind.API_STATUS),
])
def test_api_status_diagnostic_uses_only_safe_allowlisted_fields(
    error_class, status: int, safe_class: str, kind: BridgeErrorKind,
) -> None:
    request = httpx2.Request(
        "POST", "https://example.invalid/v1/responses",
        headers={"Authorization": "Bearer HEADER_SECRET_MARKER"},
    )
    response = httpx2.Response(
        status, request=request,
        headers={"x-request-id": "REQUEST_ID_SECRET_MARKER", "x-secret": "HEADER_SECRET"},
    )
    error = error_class(
        "EXCEPTION_MESSAGE_SECRET_MARKER",
        response=response,
        body={
            "code": "safe_code-1.2",
            "type": "safe_type-3.4",
            "message": "BODY_SECRET_MARKER",
            "nested": {"secret": "NESTED_SECRET_MARKER"},
        },
    )
    client = FakeClient(error)
    bridge = SixAgentOpenAIBridge(client, SixAgentOpenAIConfig())
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(
            ModelRole.PLANER,
            "PROMPT_SECRET_MARKER",
            "USER_INPUT_SECRET_MARKER",
        )
    assert caught.value.kind is kind
    assert caught.value.diagnostic == "; ".join((
        f"status_code={status}",
        f"api_error_class={safe_class}",
        "api_error_code=safe_code-1.2",
        "api_error_type=safe_type-3.4",
    ))
    rendered = str(caught.value)
    for forbidden in (
        "EXCEPTION_MESSAGE_SECRET_MARKER", "BODY_SECRET_MARKER",
        "NESTED_SECRET_MARKER", "HEADER_SECRET_MARKER", "HEADER_SECRET",
        "REQUEST_ID_SECRET_MARKER", "PROMPT_SECRET_MARKER",
        "USER_INPUT_SECRET_MARKER", "Authorization", "x-request-id",
    ):
        assert forbidden not in rendered
    assert len(client.responses.calls) == 1


def test_api_status_diagnostic_rejects_injected_code_and_type() -> None:
    request = httpx2.Request("POST", "https://example.invalid/v1/responses")
    response = httpx2.Response(
        400, request=request, headers={"x-request-id": "SECRET_RESPONSE_ID"},
    )
    error = openai.BadRequestError(
        "RAW_EXCEPTION_SECRET",
        response=response,
        body={
            "code": "SECRET_CODE_MARKER",
            "type": "TOKEN_TYPE_MARKER",
            "message": "RAW_BODY_SECRET",
        },
    )
    bridge, client = _bridge(error)
    with pytest.raises(SixAgentBridgeError) as caught:
        bridge.generate(ModelRole.CHEF_ROUTER, "SECRET_PROMPT", "SECRET_USER_INPUT")
    assert caught.value.diagnostic == "; ".join((
        "status_code=400",
        "api_error_class=BadRequest",
        "api_error_code=unknown",
        "api_error_type=unknown",
    ))
    rendered = str(caught.value)
    for forbidden in (
        "SECRET_CODE_MARKER", "TOKEN_TYPE_MARKER", "RAW_BODY_SECRET",
        "RAW_EXCEPTION_SECRET", "SECRET_RESPONSE_ID", "SECRET_PROMPT",
        "SECRET_USER_INPUT",
    ):
        assert forbidden not in rendered
    assert len(client.responses.calls) == 1


def test_total_tokens_falls_back_to_input_plus_output() -> None:
    response = {"status": "completed", "output_text": "OK", "output": [],
                "usage": {"input_tokens": 6, "output_tokens": 7}}
    bridge, _ = _bridge(response)
    assert bridge.generate(ModelRole.PLANER, "S", "U").usage.total_tokens == 13


def _role_state():
    state = create_initial_six_agent_state("bridge-adapter", "Auftrag", hard_max_model_calls=10)
    state["required_call_budget"] = 10
    state["status"] = "laeuft"
    state["planning_result"] = "Plan"
    state["analysis_result"] = "Analyse"
    state["implementation_result"] = "Umsetzung"
    return state


@pytest.mark.parametrize(("role", "runner", "prompt", "expected_input", "text", "field"), [
    (ModelRole.PLANER, run_planner, PLANER_SYSTEM_PROMPT, build_planner_input("Auftrag"), "Neuer Plan", "planning_result"),
    (ModelRole.ANALYST, run_analyst, ANALYST_SYSTEM_PROMPT,
     build_analyst_input("Auftrag", planning_result="Plan"), "Neue Analyse", "analysis_result"),
    (ModelRole.UMSETZER, run_implementer, UMSETZER_SYSTEM_PROMPT,
     build_implementer_input("Auftrag", planning_result="Plan", analysis_result="Analyse"), "Neue Umsetzung", "implementation_result"),
    (ModelRole.TESTER, run_tester, TESTER_SYSTEM_PROMPT,
     build_tester_input("Auftrag", "Umsetzung", planning_result="Plan", analysis_result="Analyse"), _tester_json(), "testing_result"),
    (ModelRole.PRUEFER, run_reviewer, SIX_AGENT_REVIEWER_SYSTEM_PROMPT,
     build_reviewer_input("Auftrag", "Umsetzung", planning_result="Plan", analysis_result="Analyse"), _review_json(), "review_result"),
])
def test_all_five_roles_integrate_with_bridge_without_adapter_special_cases(
    role, runner, prompt, expected_input, text, field,
) -> None:
    bridge, client = _bridge(_completed(text, usage=_usage_object(8, 9, 17)))
    update = runner(_role_state(), bridge)
    assert update["actual_call_count"] == 1
    assert update["iteration_counts"].count(role) == 1
    assert update[field]
    assert update["usage"][0]["provider"] == "openai-six-agent"
    assert update["usage"][0]["gesamt_tokens"] == 17
    assert client.responses.calls[0]["instructions"] == prompt
    assert client.responses.calls[0]["input"] == expected_input
    assert len(client.responses.calls) == 1


def test_import_and_bridge_use_never_construct_a_real_openai_client(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Ein echter OpenAI-Client darf nicht erzeugt werden")
    monkeypatch.setattr(openai, "OpenAI", forbidden)
    bridge, _ = _bridge(_completed())
    assert bridge.generate(ModelRole.PLANER, "S", "U").text == "OK"


def test_bridge_has_no_state_mutation_routing_environment_or_client_construction() -> None:
    source = (SRC_DIR / "six_agent_openai_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)
    forbidden_text = ("SixAgentWorkflowState", "actual_call_count", "iteration_counts",
                      "global_correction_count", "target_for_failure_origin", "RoutingTarget",
                      "next_agent", "ChefRoute", "OPENAI_API_KEY", "getenv", "environ", "OpenAI(")
    assert all(value not in source for value in forbidden_text)
    assert "SixAgentWorkflowState" not in imported_names
