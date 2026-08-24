from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from config import AppConfig  # noqa: E402
from graph import run_workflow  # noqa: E402
from llm_provider import GenerationResult, UsageData  # noqa: E402
from prompts import CHEF_SYSTEM_PROMPT, PRUEFER_SYSTEM_PROMPT, SPEZIALIST_SYSTEM_PROMPT  # noqa: E402


TASK = "Drei Vorteile regelmäßiger Projekt-Backups nennen."
WORK_ORDER = "Nenne genau drei konkrete Vorteile regelmäßiger Projekt-Backups."
ANSWER_1 = "1. Datenschutz. 2. Wiederherstellung. 3. Versionsstände."
ANSWER_2 = "1. Schutz vor Datenverlust. 2. Schnelle Wiederherstellung. 3. Saubere Versionsstände."
REJECT_REASON = "Der erste Punkt ist zu ungenau."
REJECT_IMPROVEMENTS = ["Ersten Punkt konkretisieren"]
REJECT_FEEDBACK = REJECT_REASON + " Verbesserungshinweise: " + "; ".join(REJECT_IMPROVEMENTS)
ACCEPT_REASON = "Alle drei konkreten Vorteile sind vorhanden."


class InstrumentedGraphProvider:
    name = "fake"
    model = "graph-trace-deterministic"

    def __init__(self, decisions: list[str]) -> None:
        self.decisions = decisions
        self.calls: list[dict[str, Any]] = []
        self.role_counts = {"CHEF": 0, "SPEZIALIST": 0, "PRÜFER": 0}

    def generate(self, agent: str, system_prompt: str, user_prompt: str) -> GenerationResult:
        self.role_counts[agent] += 1
        cycle = self.role_counts[agent] if agent != "CHEF" else max(0, self.role_counts["PRÜFER"])
        state_lengths = self._state_lengths(agent, user_prompt)
        metadata = {
            "call": len(self.calls) + 1,
            "agent": agent,
            "cycle": cycle,
            "system_chars": len(system_prompt),
            "user_chars": len(user_prompt),
            **state_lengths,
            # Nur für Assertions im Speicher; diese Inhalte werden niemals ausgegeben.
            "user_prompt": user_prompt,
        }
        self.calls.append(metadata)
        safe_lengths = "; ".join(
            f"{key}={value}" for key, value in state_lengths.items()
        )
        print(
            f"[GRAPH-TRACE] node={agent}; cycle={cycle}; call={metadata['call']}; "
            f"system_zeichen={len(system_prompt)}; user_zeichen={len(user_prompt)}; {safe_lengths}",
            flush=True,
        )

        if agent == "CHEF":
            text = user_prompt.split("GEPRÜFTES ERGEBNIS:\n", 1)[1] if "GEPRÜFTES ERGEBNIS:\n" in user_prompt else WORK_ORDER
        elif agent == "SPEZIALIST":
            text = ANSWER_1 if self.role_counts[agent] == 1 else ANSWER_2
        elif agent == "PRÜFER":
            decision = self.decisions[self.role_counts[agent] - 1]
            payload = {
                "entscheidung": decision,
                "begruendung": ACCEPT_REASON if decision == "AKZEPTIERT" else REJECT_REASON,
                "verbesserungen": [] if decision == "AKZEPTIERT" else REJECT_IMPROVEMENTS,
            }
            text = json.dumps(payload, ensure_ascii=False)
        else:
            raise AssertionError(f"Unerwartete Rolle: {agent}")
        return GenerationResult(text, UsageData(agent, self.name, self.model))

    @staticmethod
    def _state_lengths(agent: str, prompt: str) -> dict[str, int]:
        if agent == "CHEF":
            if prompt.startswith("GEPRÜFTES ERGEBNIS:\n"):
                return {"specialist_answer_zeichen": len(prompt.split("\n", 1)[1])}
            return {"user_request_zeichen": len(prompt)}
        if agent == "SPEZIALIST":
            body = prompt.split("ARBEITSAUFTRAG:\n", 1)[1]
            if "\n\nPRÜFERKRITIK:\n" in body:
                work_order, feedback = body.split("\n\nPRÜFERKRITIK:\n", 1)
            else:
                work_order, feedback = body, ""
            return {"work_order_zeichen": len(work_order), "feedback_zeichen": len(feedback)}
        task_and_answer = prompt.split("AUFTRAG:\n", 1)[1]
        task, remainder = task_and_answer.split("\n\nERGEBNIS:\n", 1)
        answer, _instruction = remainder.split("\n\nPrüfe strikt", 1)
        return {"user_request_zeichen": len(task), "specialist_answer_zeichen": len(answer)}


def _run(tmp_path: Path, decisions: list[str]):
    provider = InstrumentedGraphProvider(decisions)
    config = AppConfig(max_review_cycles=2, logging_enabled=False)
    result, _ = run_workflow(TASK, tmp_path, provider=provider, config=config)
    return result, provider


def test_scenario_a_accepts_first_review_with_exact_graph_order(tmp_path: Path, capsys) -> None:
    result, provider = _run(tmp_path, ["AKZEPTIERT"])
    assert [call["agent"] for call in provider.calls] == ["CHEF", "SPEZIALIST", "PRÜFER", "CHEF"]
    assert len(provider.calls) == 4
    assert result["review_round"] == 1
    assert result["status"] == "erfolgreich"
    assert result["work_order"] == WORK_ORDER
    assert result["specialist_answer"] == ANSWER_1
    assert result["final_answer"] == ANSWER_1
    assert len(result["usage"]) == 4
    assert len(result["events"]) == 5

    first_specialist = provider.calls[1]
    reviewer = provider.calls[2]
    final_chef = provider.calls[3]
    assert first_specialist["work_order_zeichen"] == len(WORK_ORDER)
    assert first_specialist["feedback_zeichen"] == 0
    assert reviewer["user_request_zeichen"] == len(TASK)
    assert reviewer["specialist_answer_zeichen"] == len(ANSWER_1)
    assert final_chef["specialist_answer_zeichen"] == len(ANSWER_1)
    trace = capsys.readouterr().out
    assert trace.count("[GRAPH-TRACE]") == 4
    assert "node=CHEF; cycle=0; call=1" in trace
    assert "node=PRÜFER; cycle=1; call=3" in trace


def test_scenario_b_rejects_then_accepts_without_uncontrolled_growth(tmp_path: Path, capsys) -> None:
    result, provider = _run(tmp_path, ["ABGELEHNT", "AKZEPTIERT"])
    assert [call["agent"] for call in provider.calls] == [
        "CHEF", "SPEZIALIST", "PRÜFER", "SPEZIALIST", "PRÜFER", "CHEF"
    ]
    assert len(provider.calls) == 6
    assert result["review_round"] == 2
    assert result["status"] == "erfolgreich"
    assert result["work_order"] == WORK_ORDER
    assert result["specialist_answer"] == ANSWER_2
    assert result["final_answer"] == ANSWER_2
    assert len(result["usage"]) == 6
    assert len(result["events"]) == 7

    first_specialist = provider.calls[1]
    first_reviewer = provider.calls[2]
    second_specialist = provider.calls[3]
    second_reviewer = provider.calls[4]
    final_chef = provider.calls[5]
    assert first_specialist["work_order_zeichen"] == len(WORK_ORDER)
    assert first_specialist["feedback_zeichen"] == 0
    assert second_specialist["work_order_zeichen"] == len(WORK_ORDER)
    assert second_specialist["feedback_zeichen"] == len(REJECT_FEEDBACK)
    assert first_reviewer["specialist_answer_zeichen"] == len(ANSWER_1)
    assert second_reviewer["specialist_answer_zeichen"] == len(ANSWER_2)
    assert final_chef["specialist_answer_zeichen"] == len(ANSWER_2)

    expected_second_user_chars = len("ARBEITSAUFTRAG:\n") + len(WORK_ORDER) + len("\n\nPRÜFERKRITIK:\n") + len(REJECT_FEEDBACK)
    assert second_specialist["user_chars"] == expected_second_user_chars
    assert ANSWER_1 not in second_specialist["user_prompt"]
    assert ANSWER_1 not in second_reviewer["user_prompt"]
    assert ANSWER_2 in second_reviewer["user_prompt"]
    trace = capsys.readouterr().out
    assert trace.count("[GRAPH-TRACE]") == 6
    assert "node=SPEZIALIST; cycle=2; call=4" in trace
    assert "node=PRÜFER; cycle=2; call=5" in trace


def test_only_events_and_usage_are_accumulative_state_fields() -> None:
    annotations = __import__("state").WorkflowState.__annotations__
    annotated_fields = {
        name for name, annotation in annotations.items() if "Annotated" in str(annotation)
    }
    assert annotated_fields == {"events", "usage"}
