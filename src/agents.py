from __future__ import annotations

import json

from audit_log import AuditLogger
from config import AppConfig
from llm_provider import FakeLLMProvider, LLMProvider, ProviderResponseError, REQUIRED_ELEMENT
from prompts import CHEF_SYSTEM_PROMPT, PRUEFER_SYSTEM_PROMPT, SPEZIALIST_SYSTEM_PROMPT
from state import WorkflowState


def _generate(provider: LLMProvider, agent: str, system_prompt: str, user_prompt: str):
    print(f"[AGENT] {agent} Eintritt", flush=True)
    try:
        return provider.generate(agent, system_prompt, user_prompt)
    finally:
        print(f"[AGENT] {agent} Verlassen", flush=True)


def _defaults(provider: LLMProvider | None, config: AppConfig | None) -> tuple[LLMProvider, AppConfig]:
    effective_config = config or AppConfig()
    effective_provider = provider or FakeLLMProvider(max_response_chars=effective_config.max_response_chars)
    return effective_provider, effective_config


def make_chef(logger: AuditLogger, provider: LLMProvider | None = None, config: AppConfig | None = None):
    provider, config = _defaults(provider, config)

    def chef(state: WorkflowState) -> dict[str, object]:
        if state["decision"] == "AKZEPTIERT":
            generated = _generate(provider, "CHEF", CHEF_SYSTEM_PROMPT, f"GEPRÜFTES ERGEBNIS:\n{state['specialist_answer']}")
            outgoing = logger.record(
                "CHEF", "BENUTZER", f"Freigegebenes Ergebnis übermittelt ({len(generated.text)} Zeichen).", state["review_round"],
                "AKZEPTIERT", generated.usage.as_dict(),
            )
            print("[CHEF] Endergebnis erhalten")
            print("[FERTIG] Ergebnis an Benutzer")
            return {
                "status": "erfolgreich", "final_answer": generated.text,
                "events": [outgoing], "usage": [generated.usage.as_dict()],
            }

        generated = _generate(provider, "CHEF", CHEF_SYSTEM_PROMPT, state["user_request"])
        received = logger.record("BENUTZER", "CHEF", f"Benutzerauftrag empfangen ({len(state['user_request'])} Zeichen).", 0)
        delegated = logger.record("CHEF", "SPEZIALIST", f"Arbeitsauftrag formuliert ({len(generated.text)} Zeichen).", 1, usage=generated.usage.as_dict())
        print("[CHEF] Auftrag an SPEZIALIST")
        return {
            "work_order": generated.text, "events": [received, delegated],
            "usage": [generated.usage.as_dict()],
        }

    return chef


def make_specialist(logger: AuditLogger, provider: LLMProvider | None = None, config: AppConfig | None = None):
    provider, config = _defaults(provider, config)

    def specialist(state: WorkflowState) -> dict[str, object]:
        review_round = state["review_round"] + 1
        prompt = f"ARBEITSAUFTRAG:\n{state['work_order']}"
        if state["feedback"]:
            prompt += f"\n\nPRÜFERKRITIK:\n{state['feedback']}"
        generated = _generate(provider, "SPEZIALIST", SPEZIALIST_SYSTEM_PROMPT, prompt)
        print("[SPEZIALIST] Antwort erstellt" if review_round == 1 else "[SPEZIALIST] Antwort wird überarbeitet")
        event = logger.record(
            "SPEZIALIST", "PRÜFER", f"Arbeitsergebnis übergeben ({len(generated.text)} Zeichen).", review_round,
            usage=generated.usage.as_dict(),
        )
        return {
            "specialist_answer": generated.text, "review_round": review_round,
            "events": [event], "usage": [generated.usage.as_dict()],
        }

    return specialist


def _parse_review(text: str) -> tuple[str, str, list[str]]:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise ProviderResponseError("Die Prüferantwort war kein gültiges JSON.")
    decision = payload.get("entscheidung")
    reason = str(payload.get("begruendung", "Keine Begründung angegeben."))
    improvements = payload.get("verbesserungen", [])
    if decision not in {"AKZEPTIERT", "ABGELEHNT"} or not isinstance(improvements, list):
        raise ProviderResponseError("Die strukturierte Prüferantwort war ungültig.")
    return decision, reason, [str(item) for item in improvements]


def make_reviewer(logger: AuditLogger, provider: LLMProvider | None = None, config: AppConfig | None = None):
    provider, config = _defaults(provider, config)

    def reviewer(state: WorkflowState) -> dict[str, object]:
        prompt = (
            f"AUFTRAG:\n{state['user_request']}\n\nERGEBNIS:\n{state['specialist_answer']}\n\n"
            "Prüfe strikt gegen den ursprünglichen Auftrag und antworte im geforderten JSON-Schema."
        )
        generated = _generate(provider, "PRÜFER", PRUEFER_SYSTEM_PROMPT, prompt)
        try:
            decision, reason, improvements = _parse_review(generated.text)
        except ProviderResponseError:
            logger.record(
                "PRÜFER", "CHEF", "Ungültige strukturierte Prüferantwort; Workflow abgebrochen.",
                state["review_round"], "", generated.usage.as_dict(),
            )
            raise
        feedback = reason + ((" Verbesserungshinweise: " + "; ".join(improvements)) if improvements else "")
        receiver = "CHEF" if decision == "AKZEPTIERT" else "SPEZIALIST"
        event = logger.record(
            "PRÜFER", receiver, feedback, state["review_round"],
            decision, generated.usage.as_dict(),
        )
        print("[PRÜFER] AKZEPTIERT" if decision == "AKZEPTIERT" else f"[PRÜFER] ABGELEHNT – Begründung: {feedback}")
        return {
            "decision": decision, "feedback": feedback,
            "events": [event], "usage": [generated.usage.as_dict()],
        }

    return reviewer


def make_failure(logger: AuditLogger):
    def failure(state: WorkflowState) -> dict[str, object]:
        message = f"Nach {state['max_rounds']} Prüfungen wurde keine Annahme erreicht."
        event = logger.record("PRÜFER", "CHEF", message, state["review_round"], "ABGELEHNT")
        print(f"[FEHLER] {message}")
        return {"status": "fehlgeschlagen", "final_answer": message, "events": [event]}

    return failure
