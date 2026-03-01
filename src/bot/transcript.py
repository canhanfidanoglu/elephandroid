"""In-memory transcript accumulator per active call."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TranscriptEntry:
    speaker: str
    text: str
    timestamp: str
    confidence: float = 0.0
    result_type: str = "final"  # "partial" or "final"


@dataclass
class ActiveCall:
    call_connection_id: str
    server_call_id: str
    meeting_subject: str = ""
    meeting_join_url: str = ""
    user_id: str = ""
    access_token: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    entries: list[TranscriptEntry] = field(default_factory=list)
    is_active: bool = True

    def add_entry(self, entry: TranscriptEntry) -> None:
        if entry.result_type == "final":
            self.entries.append(entry)

    def get_plain_text(self) -> str:
        """Build readable plain text from transcript entries."""
        if not self.entries:
            return ""
        lines = []
        current_speaker = None
        for entry in self.entries:
            if entry.speaker != current_speaker:
                lines.append(f"\n{entry.speaker}:")
                current_speaker = entry.speaker
            lines.append(entry.text)
        return " ".join(lines).strip()


# Global registry of active calls: call_connection_id -> ActiveCall
_active_calls: dict[str, ActiveCall] = {}


def register_call(call: ActiveCall) -> None:
    _active_calls[call.call_connection_id] = call
    logger.info("Registered call %s for meeting '%s'", call.call_connection_id, call.meeting_subject)


def get_call(call_connection_id: str) -> ActiveCall | None:
    return _active_calls.get(call_connection_id)


def finish_call(call_connection_id: str) -> ActiveCall | None:
    call = _active_calls.pop(call_connection_id, None)
    if call:
        call.is_active = False
        logger.info(
            "Finished call %s — %d transcript entries",
            call_connection_id,
            len(call.entries),
        )
    return call


def list_active_calls() -> list[dict]:
    return [
        {
            "call_connection_id": c.call_connection_id,
            "meeting_subject": c.meeting_subject,
            "started_at": c.started_at.isoformat(),
            "entry_count": len(c.entries),
        }
        for c in _active_calls.values()
        if c.is_active
    ]
