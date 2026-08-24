from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import openai
import httpx2


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from agents import REQUIRED_ELEMENT, make_reviewer  # noqa: E402
from audit_log import AuditLogger  # noqa: E402
from config import (  # noqa: E402
    AppConfig,
    ConfigurationError,
    calculate_required_model_calls,
    load_config,
)
from graph import run_workflow, summarize_usage  # noqa: E402
from llm_provider import (  # noqa: E402
    FakeLLMProvider,
    GenerationResult,
    LogicalCallLimitProvider,
    OpenAIProvider,
    ProviderError,
    ProviderResponseError,
    UsageData,
    create_provider,
    extract_response_text,
    safe_response_diagnostic,
)
from main import main  # noqa: E402
import main as main_module  # noqa: E402
import agents as agents_module  # noqa: E402
import graph as graph_module  # noqa: E402
import llm_provider as llm_provider_module  # noqa: E402
from prompts import PRUEFER_SYSTEM_PROMPT, SPEZIALIST_SYSTEM_PROMPT  # noqa: E402


@pytest.fixture(autouse=True)
def forbid_real_openai_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Während pytest darf kein echter OpenAI-Client entstehen")

    monkeypatch.setattr(openai, "OpenAI", forbidden)


class RecordingFakeProvider(FakeLLMProvider):
    def __init__(self) -> None:
        super().__init__()
        self.agents: list[str] = []
        self.calls: list[tuple[str, str, str]] = []

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        self.agents.append(agent)
        self.calls.append((agent, system_prompt, user_prompt))
        return super().generate(agent, system_prompt, user_prompt)


class AlwaysRejectProvider(FakeLLMProvider):
    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        if agent == "PRÜFER":
            text = json.dumps({
                "entscheidung": "ABGELEHNT",
                "begruendung": "Testweise immer abgelehnt.",
                "verbesserungen": ["Erneut überarbeiten"],
            })
            return GenerationResult(text, UsageData(agent=agent, provider=self.name, model=self.model))
        return super().generate(agent, system_prompt, user_prompt)


def test_complete_feedback_workflow(tmp_path: Path) -> None:
    result, log_path = run_workflow("Testauftrag", tmp_path)
    transitions = [(event["sender"], event["empfaenger"]) for event in result["events"]]
    decisions = [event["entscheidung"] for event in result["events"] if event["entscheidung"]]

    assert transitions[0:2] == [("BENUTZER", "CHEF"), ("CHEF", "SPEZIALIST")]
    assert transitions.count(("SPEZIALIST", "PRÜFER")) == 2
    assert ("PRÜFER", "SPEZIALIST") in transitions
    assert transitions[-2:] == [("PRÜFER", "CHEF"), ("CHEF", "BENUTZER")]
    assert decisions == ["ABGELEHNT", "AKZEPTIERT", "AKZEPTIERT"]
    assert result["review_round"] == 2
    assert result["decision"] == "AKZEPTIERT"
    assert result["status"] == "erfolgreich"
    assert REQUIRED_ELEMENT in result["final_answer"]
    assert log_path is not None and log_path.exists()
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == len(result["events"])
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert {row["workflow_id"] for row in rows} == {result["workflow_id"]}
    assert all("provider" in row and "modell" in row for row in rows)
    assert all(item["gesamt_tokens"] == 0 for item in result["usage"])


def test_workflow_stops_after_two_live_reviews(tmp_path: Path) -> None:
    config = AppConfig(max_review_cycles=2)
    result, _ = run_workflow("Abbruchtest", tmp_path, provider=AlwaysRejectProvider(), config=config)
    assert result["review_round"] == 2
    assert result["status"] == "fehlgeschlagen"
    assert "Nach 2 Prüfungen" in result["final_answer"]
    assert len(result["events"]) < 20


def test_reviewer_rejects_incomplete_answer(tmp_path: Path) -> None:
    reviewer = make_reviewer(AuditLogger(tmp_path))
    state = {"user_request": "Test", "specialist_answer": "Unvollständig", "review_round": 1}
    update = reviewer(state)  # type: ignore[arg-type]
    assert update["decision"] == "ABGELEHNT"
    assert "Audit-Protokoll" in update["feedback"]


def test_default_provider_is_fake_and_needs_no_key() -> None:
    config = load_config({})
    provider = create_provider(config, environ={})
    assert config.provider == "fake"
    assert config.max_review_cycles == 2
    assert config.hard_max_model_calls == 6
    assert isinstance(provider, FakeLLMProvider)
    assert provider.cloud_call_count == 0


def test_all_agents_use_provider_abstraction(tmp_path: Path) -> None:
    provider = RecordingFakeProvider()
    run_workflow("Testauftrag", tmp_path, provider=provider)
    assert provider.agents == ["CHEF", "SPEZIALIST", "PRÜFER", "SPEZIALIST", "PRÜFER", "CHEF"]
    assert provider.cloud_call_count == 0


def test_secret_is_redacted_from_audit(tmp_path: Path) -> None:
    secret = "sk-testwert123456789"
    logger = AuditLogger(tmp_path)
    logger.record("TEST", "TEST", f"OPENAI_API_KEY={secret}", 0)
    assert logger.path is not None
    content = logger.path.read_text(encoding="utf-8")
    assert secret not in content
    assert "[REDACTED]" in content


def test_explicit_openai_without_key_fails_before_any_call() -> None:
    with pytest.raises(ProviderError, match="kein API-Aufruf"):
        create_provider(AppConfig(provider="openai"), environ={})


def test_pytest_never_calls_openai(tmp_path: Path, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("OpenAIProvider.generate darf im Fake-Test nie laufen")

    monkeypatch.setattr(OpenAIProvider, "generate", forbidden)
    result, _ = run_workflow("Offline-Test", tmp_path)
    assert result["status"] == "erfolgreich"


def test_openai_provider_with_mock_client_copies_usage() -> None:
    response = SimpleNamespace(
        output_text="Kurze Mock-Antwort",
        usage=SimpleNamespace(input_tokens=11, output_tokens=7, total_tokens=18),
    )

    class MockResponses:
        def __init__(self) -> None:
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return response

    responses = MockResponses()
    client = SimpleNamespace(responses=responses)
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder", client=client,
        max_output_tokens=1_000,
    )
    result = provider.generate("CHEF", "System", "Benutzer")

    assert result.text == "Kurze Mock-Antwort"
    assert result.usage.as_dict() == {
        "agent": "CHEF", "provider": "openai", "modell": "gpt-5-mini",
        "input_tokens": 11, "output_tokens": 7, "gesamt_tokens": 18,
        "geschaetzte_kosten": None,
    }
    assert responses.kwargs["max_output_tokens"] == 1_000
    assert responses.kwargs["parallel_tool_calls"] is False
    assert responses.kwargs["store"] is False
    assert responses.kwargs["reasoning"] == {"effort": "minimal"}
    assert responses.kwargs["text"] == {"verbosity": "low"}
    assert responses.kwargs["timeout"].connect == 10.0
    assert responses.kwargs["timeout"].read == 30.0
    assert responses.kwargs["timeout"].write == 10.0
    assert responses.kwargs["timeout"].pool == 5.0
    assert "tools" not in responses.kwargs


def test_compact_agent_prompts_and_no_task_multiplication(tmp_path: Path) -> None:
    task = "Nenne drei Vorteile eines regelmäßigen Projekt-Backups."
    provider = RecordingFakeProvider()
    run_workflow(task, tmp_path, provider=provider)

    specialist_calls = [call for call in provider.calls if call[0] == "SPEZIALIST"]
    reviewer_calls = [call for call in provider.calls if call[0] == "PRÜFER"]
    assert "höchstens 250 Wörter" in SPEZIALIST_SYSTEM_PROMPT
    assert all("höchstens 250 Wörter" in call[1] for call in specialist_calls)
    assert "ausschließlich" in PRUEFER_SYSTEM_PROMPT
    assert "ein kurzer Satz" in PRUEFER_SYSTEM_PROMPT
    assert "höchstens drei kurze Einträge" in PRUEFER_SYSTEM_PROMPT
    assert provider.calls[0][2].count(task) == 1
    assert specialist_calls[0][2].count(task) == 1
    assert reviewer_calls[0][2].count(task) == 1


def test_openai_timeout_gets_exactly_one_retry() -> None:
    response = SimpleNamespace(
        output_text="Nach Retry erfolgreich",
        usage=SimpleNamespace(input_tokens=2, output_tokens=3, total_tokens=5),
    )

    class RetryResponses:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise openai.APITimeoutError(httpx2.Request("POST", "https://example.invalid"))
            return response

    responses = RetryResponses()
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder",
        client=SimpleNamespace(responses=responses),
    )
    result = provider.generate("CHEF", "System", "Benutzer")
    assert result.text == "Nach Retry erfolgreich"
    assert responses.calls == 2


def test_second_timeout_fails_controlled_with_status(capsys) -> None:
    class TimeoutResponses:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            raise openai.APITimeoutError(httpx2.Request("POST", "https://example.invalid"))

    responses = TimeoutResponses()
    ticks = iter([10.0, 42.5])
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder",
        client=SimpleNamespace(responses=responses), clock=lambda: next(ticks),
    )
    with pytest.raises(ProviderError, match="nach einem Retry"):
        provider.generate("SPEZIALIST", "System", "Prompt")
    output = capsys.readouterr().out
    assert responses.calls == 2
    assert provider.http_attempt_count == 2
    assert "[API] SPEZIALIST Timeout bei Versuch 1" in output
    assert "[API] SPEZIALIST vor einmaligem Retry" in output
    assert "Dauer: 32.5 s – Fehlerklasse: Timeout" in output


def test_slow_mock_marks_exact_synchronous_request_boundary(capsys) -> None:
    ticks = iter([5.0, 80.0])
    seen_timeout = None

    def slow_mock(**kwargs):
        nonlocal seen_timeout
        seen_timeout = kwargs["timeout"]
        return SimpleNamespace(
            output_text="Mock nach langer simulierter Wartezeit", status="completed",
            usage=SimpleNamespace(input_tokens=3, output_tokens=4, total_tokens=7),
        )

    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder",
        client=SimpleNamespace(responses=SimpleNamespace(create=slow_mock)),
        clock=lambda: next(ticks),
    )
    provider.generate("CHEF", "System", "Prompt")
    output = capsys.readouterr().out
    before = output.index("unmittelbar vor responses.create()")
    after = output.index("unmittelbar nach responses.create()")
    assert before < after
    assert "Dauer: 75.0 s" in output
    assert seen_timeout.read == 30.0


def test_network_error_gets_exactly_one_retry() -> None:
    response = SimpleNamespace(
        output_text="Erfolgreich", status="completed",
        usage=SimpleNamespace(input_tokens=2, output_tokens=1, total_tokens=3),
    )

    class NetworkResponses:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise openai.APIConnectionError(request=httpx2.Request("POST", "https://example.invalid"))
            return response

    responses = NetworkResponses()
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder",
        client=SimpleNamespace(responses=responses),
    )
    assert provider.generate("CHEF", "System", "Prompt").text == "Erfolgreich"
    assert responses.calls == 2
    assert provider.http_attempt_count == 2


def test_fast_call_reports_monotonic_duration_and_tokens(capsys) -> None:
    response = SimpleNamespace(
        output_text="OK", status="completed",
        usage=SimpleNamespace(input_tokens=4, output_tokens=2, total_tokens=6),
    )
    ticks = iter([100.0, 100.25])
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key="test-placeholder",
        client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response)),
        clock=lambda: next(ticks),
    )
    provider.generate("PRÜFER", "secret-system", "secret-prompt")
    output = capsys.readouterr().out
    assert "[API] PRÜFER gestartet" in output
    assert "[API] PRÜFER beendet – Dauer: 0.2 s – Tokens: 6" in output
    assert "secret" not in output


def test_client_has_explicit_phase_timeouts_and_no_sdk_retries(monkeypatch) -> None:
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(responses=SimpleNamespace())

    monkeypatch.setattr(openai, "OpenAI", fake_openai)
    provider = OpenAIProvider(model="gpt-5-mini", api_key="test-placeholder", timeout_seconds=30.0)
    provider._get_client()
    timeout = captured["timeout"]
    assert captured["max_retries"] == 0
    assert timeout.connect == 10.0
    assert timeout.read == 30.0
    assert timeout.write == 10.0
    assert timeout.pool == 5.0


def test_keyboard_interrupt_is_clean_and_stops(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MAS_PROVIDER", "fake")

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(main_module, "run_workflow", interrupted)
    assert main_module.main([]) == 130
    output = capsys.readouterr().out
    assert "[ABGEBROCHEN] Benutzer hat den Live-Test beendet." in output
    assert "Traceback" not in output


@pytest.mark.parametrize(("rounds", "required"), [(1, 4), (2, 6), (3, 8)])
def test_required_model_call_formula(rounds: int, required: int) -> None:
    assert calculate_required_model_calls(rounds) == required


@pytest.mark.parametrize("rounds", [0, -1])
def test_invalid_review_round_count_is_rejected(rounds: int) -> None:
    with pytest.raises(ConfigurationError, match="mindestens 1"):
        calculate_required_model_calls(rounds)


def test_two_rounds_with_hard_limit_six_are_allowed() -> None:
    config = AppConfig(max_review_cycles=2, hard_max_model_calls=6)
    assert config.max_review_cycles == 2
    assert config.hard_max_model_calls == 6


def test_three_rounds_with_hard_limit_six_are_blocked_before_provider(tmp_path: Path) -> None:
    class CountingProvider(FakeLLMProvider):
        calls = 0

        def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
            self.calls += 1
            return super().generate(agent, system_prompt, user_prompt)

    provider = CountingProvider()
    config = AppConfig(max_review_cycles=2, hard_max_model_calls=6)
    with pytest.raises(ConfigurationError, match="3 Prüfzyklen.*8 Modellaufrufe.*nur 6"):
        run_workflow("Grenztest", tmp_path, max_rounds=3, provider=provider, config=config)
    assert provider.calls == 0


def test_three_rounds_with_hard_limit_eight_are_allowed(tmp_path: Path) -> None:
    config = AppConfig(max_review_cycles=3, hard_max_model_calls=8)
    result, _ = run_workflow("Erlaubt", tmp_path, provider=FakeLLMProvider(), config=config)
    assert result["status"] == "erfolgreich"


def test_runtime_counter_blocks_actual_overrun() -> None:
    provider = LogicalCallLimitProvider(FakeLLMProvider(), maximum=1)
    provider.generate("CHEF", "System", "Auftrag")
    with pytest.raises(ProviderError, match="maximal 1 logischen"):
        provider.generate("CHEF", "System", "Auftrag")


def test_extracts_text_from_realistic_sdk_output_items() -> None:
    from openai.types.responses.response_output_message import ResponseOutputMessage
    from openai.types.responses.response_output_text import ResponseOutputText

    content = ResponseOutputText(
        annotations=[], text="Text aus dem Content-Block", type="output_text", logprobs=[],
    )
    message = ResponseOutputMessage(
        id="msg_mock", content=[content], role="assistant", status="completed", type="message",
    )
    response = SimpleNamespace(output_text="", output=[message], status="completed")
    assert extract_response_text(response) == "Text aus dem Content-Block"


def test_extracts_and_joins_dictionary_content_blocks() -> None:
    response = {
        "output_text": "",
        "output": [{
            "type": "message",
            "content": [
                {"type": "output_text", "text": "Erster Satz. "},
                {"type": "output_text", "text": "Zweiter Satz."},
            ],
        }],
    }
    assert extract_response_text(response) == "Erster Satz. Zweiter Satz."


def test_incomplete_reasoning_only_response_has_safe_diagnostic() -> None:
    secret = "sk-darf-nie-in-diagnose-erscheinen"
    response = SimpleNamespace(
        output_text="",
        output=[SimpleNamespace(type="reasoning", summary=[])],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        error=None,
        usage=SimpleNamespace(
            input_tokens=91,
            output_tokens=300,
            total_tokens=391,
            output_tokens_details=SimpleNamespace(reasoning_tokens=300),
        ),
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    provider = OpenAIProvider(
        model="gpt-5-mini", api_key=secret, client=client, max_output_tokens=1_000,
    )

    with pytest.raises(ProviderResponseError) as caught:
        provider.generate("CHEF", f"System {secret}", f"Prompt {secret}")
    message = str(caught.value)
    assert "status=incomplete" in message
    assert "incomplete_reason=max_output_tokens" in message
    assert "reasoning_tokens=300" in message
    assert "output_types=reasoning" in message
    assert secret not in message
    assert "System" not in message and "Prompt" not in message


def test_explicit_incomplete_status_rejects_partial_text() -> None:
    response = SimpleNamespace(
        output_text="Teilantwort",
        output=[],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        error=None,
        usage=None,
    )
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    provider = OpenAIProvider(model="gpt-5-mini", api_key="test-placeholder", client=client)
    with pytest.raises(ProviderResponseError, match="nicht vollständig"):
        provider.generate("SPEZIALIST", "System", "Prompt")


def test_completed_refusal_without_text_is_diagnosed_structurally() -> None:
    response = {
        "output_text": "",
        "output": [{
            "type": "message",
            "content": [{"type": "refusal", "refusal": "Nicht verfügbar"}],
        }],
        "status": "completed",
        "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
    }
    diagnostic = safe_response_diagnostic(response)
    assert "content_types=refusal" in diagnostic
    assert "input_tokens=4" in diagnostic
    client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs: response))
    provider = OpenAIProvider(model="gpt-5-mini", api_key="test-placeholder", client=client)
    with pytest.raises(ProviderResponseError, match="keine verwendbare Textantwort"):
        provider.generate("PRÜFER", "System", "Prompt")


def test_usage_summary_counts_only_openai_calls() -> None:
    summary = summarize_usage([
        UsageData("CHEF", "openai", "gpt-5-mini", 10, 4, 14).as_dict(),
        UsageData("PRÜFER", "openai", "gpt-5-mini", 8, 3, 11).as_dict(),
        UsageData("SPEZIALIST", "fake", "fake", 0, 0, 0).as_dict(),
    ])
    assert summary == {"api_aufrufe": 2, "input_tokens": 18, "output_tokens": 7, "gesamt_tokens": 25}


def test_invalid_reviewer_response_aborts_controlled(tmp_path: Path) -> None:
    class InvalidReviewerProvider(FakeLLMProvider):
        def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
            if agent == "PRÜFER":
                return GenerationResult(
                    "keine strukturierte Antwort",
                    UsageData(agent, self.name, self.model),
                )
            return super().generate(agent, system_prompt, user_prompt)

    with pytest.raises(ProviderResponseError, match="kein gültiges JSON"):
        run_workflow("Test", tmp_path, provider=InvalidReviewerProvider())


def test_openai_never_starts_without_live_flag(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MAS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    assert main([]) == 2
    assert "--live-openai fehlt" in capsys.readouterr().out


def test_live_start_prints_safe_budget_metadata(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MAS_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-placeholder")
    monkeypatch.setenv("MAS_MAX_REVIEW_CYCLES", "2")
    monkeypatch.setenv("MAS_HARD_MAX_MODEL_CALLS", "6")

    def completed_without_provider_call(*args, **kwargs):
        return ({
            "final_answer": "Mock",
            "usage_summary": {
                "api_aufrufe": 0, "input_tokens": 0,
                "output_tokens": 0, "gesamt_tokens": 0,
            },
            "status": "erfolgreich",
        }, None)

    monkeypatch.setattr(main_module, "run_workflow", completed_without_provider_call)
    assert main_module.main(["--live-openai"]) == 0
    output = capsys.readouterr().out
    assert "Prüfzyklen: 2" in output
    assert "Erforderliches Aufrufbudget: 6" in output
    assert "Harte Sicherheitsgrenze: 6" in output
    assert "test-placeholder" not in output


def test_logging_can_be_disabled(tmp_path: Path) -> None:
    config = AppConfig(logging_enabled=False)
    result, log_path = run_workflow("Ohne Datei", tmp_path / "nicht-anlegen", config=config)
    assert result["status"] == "erfolgreich"
    assert log_path is None
    assert not (tmp_path / "nicht-anlegen").exists()


def test_imports_resolve_to_this_project() -> None:
    expected_src = (PROJECT_DIR / "src").resolve()
    assert Path(main_module.__file__).resolve().parent == expected_src
    assert Path(graph_module.__file__).resolve().parent == expected_src
    assert Path(agents_module.__file__).resolve().parent == expected_src
    assert Path(llm_provider_module.__file__).resolve().parent == expected_src


def test_start_diagnostics_workflow_and_first_agent_are_visible(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MAS_PROVIDER", "fake")
    assert main_module.main([]) == 0
    output = capsys.readouterr().out
    assert "[START] main.py aktiv" in output
    assert f"[START] Projektpfad: {PROJECT_DIR.resolve()}" in output
    assert f"[START] main.py: {Path(main_module.__file__).resolve()}" in output
    assert f"[START] llm_provider.py: {Path(llm_provider_module.__file__).resolve()}" in output
    assert f"[START] agents.py: {Path(agents_module.__file__).resolve()}" in output
    assert f"[START] graph.py: {Path(graph_module.__file__).resolve()}" in output
    assert "[START] Workflow wird gestartet" in output
    assert output.index("[AGENT] CHEF Eintritt") > output.index("[START] Workflow wird gestartet")
