"""Handle ACS Call Automation webhook events."""

import logging

from src.meetings.summarizer import summarize_transcript

from .transcript import TranscriptEntry, finish_call, get_call

logger = logging.getLogger(__name__)


async def handle_callback_events(events: list[dict]) -> None:
    """Process ACS callback events (POST /bot/callbacks).

    ACS sends events like CallConnected, CallDisconnected,
    TranscriptionStarted, TranscriptionStopped, etc.
    """
    for event in events:
        event_type = event.get("type", "")
        data = event.get("data", {})
        call_connection_id = data.get("callConnectionId", "")

        if "CallConnected" in event_type:
            logger.info("Call connected: %s", call_connection_id)

        elif "CallDisconnected" in event_type:
            logger.info("Call disconnected: %s", call_connection_id)
            await _on_call_ended(call_connection_id)

        elif "TranscriptionStarted" in event_type:
            logger.info("Transcription started for call %s", call_connection_id)

        elif "TranscriptionStopped" in event_type:
            logger.info("Transcription stopped for call %s", call_connection_id)

        elif "TranscriptionFailed" in event_type:
            reason = data.get("resultInformation", {}).get("message", "unknown")
            logger.error("Transcription failed for call %s: %s", call_connection_id, reason)

        else:
            logger.debug("Unhandled event type: %s", event_type)


async def _on_call_ended(call_connection_id: str) -> None:
    """When a call ends, process the accumulated transcript."""
    call = finish_call(call_connection_id)
    if not call:
        logger.warning("No active call found for %s", call_connection_id)
        return

    transcript_text = call.get_plain_text()
    if not transcript_text:
        logger.info("Call %s ended with empty transcript", call_connection_id)
        return

    logger.info(
        "Call %s ended — %d entries, %d chars. Processing...",
        call_connection_id,
        len(call.entries),
        len(transcript_text),
    )

    # Auto-summarize
    try:
        result = await summarize_transcript(
            transcript_text,
            meeting_subject=call.meeting_subject,
            ticket_prefix="MTG",
        )
        logger.info(
            "Meeting '%s' summarized: %d tasks extracted",
            call.meeting_subject,
            len(result["tasks"]),
        )
        # TODO: Store summary in DB, send notification to user,
        # and optionally auto-sync tasks to Planner
    except Exception as exc:
        logger.error("Failed to summarize transcript for call %s: %s", call_connection_id, exc)


def parse_websocket_transcription(data: dict) -> TranscriptEntry | None:
    """Parse a single ACS WebSocket transcription message into a TranscriptEntry.

    ACS sends JSON messages over WebSocket with format:
    {
        "kind": "TranscriptionData",
        "transcriptionData": {
            "text": "Hello everyone",
            "format": "display",
            "confidence": 0.95,
            "offset": 1234567890,
            "duration": 5000000,
            "words": [...],
            "participantRawID": "...",
            "resultStatus": "Final"  // or "Intermediate"
        }
    }
    """
    kind = data.get("kind", "")
    if kind != "TranscriptionData":
        return None

    td = data.get("transcriptionData", {})
    text = td.get("text", "").strip()
    if not text:
        return None

    # Extract speaker from participant info
    participant_id = td.get("participantRawID", "")
    # ACS may include display names in newer versions
    speaker = td.get("participantDisplayName", "") or participant_id or "Unknown"

    result_status = td.get("resultStatus", "Final")

    return TranscriptEntry(
        speaker=speaker,
        text=text,
        timestamp=str(td.get("offset", "")),
        confidence=td.get("confidence", 0.0),
        result_type="final" if result_status == "Final" else "partial",
    )
