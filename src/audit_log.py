from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


SECRET_PATTERNS = (
    re.compile(r"(?i)(OPENAI_API_KEY\s*=\s*)\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def redact_secrets(value: str) -> str:
    redacted = value
    redacted = SECRET_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[1].sub("[REDACTED]", redacted)
    return redacted


class AuditLogger:
    """Writes one UTF-8 JSON object per agent hand-off."""

    def __init__(self, log_dir: Path, workflow_id: str | None = None, path: Path | None = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self.workflow_id = workflow_id or uuid4().hex
        if enabled:
            log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = (path or log_dir / f"workflow-{timestamp}-{uuid4().hex[:8]}.jsonl") if enabled else None

    def record(
        self,
        sender: str,
        receiver: str,
        message: str,
        review_round: int,
        decision: str = "",
        usage: dict[str, object] | None = None,
    ) -> dict[str, object]:
        event: dict[str, object] = {
            "workflow_id": self.workflow_id,
            "zeit": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "sender": sender,
            "empfaenger": receiver,
            "durchlauf": review_round,
            "nachricht": redact_secrets(message),
            "entscheidung": decision,
            "nutzung": usage or {},
            "provider": (usage or {}).get("provider", ""),
            "modell": (usage or {}).get("modell", ""),
            "input_tokens": (usage or {}).get("input_tokens", 0),
            "output_tokens": (usage or {}).get("output_tokens", 0),
            "gesamt_tokens": (usage or {}).get("gesamt_tokens", 0),
        }
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event
