"""ACS Call Automation client — join Teams meetings with transcription."""

import logging

from src.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        from azure.communication.callautomation import CallAutomationClient
    except ImportError:
        raise ImportError(
            "azure-communication-callautomation is required for meeting bot. "
            "Install with: pip install 'elephandroid[acs]'"
        )

    if not settings.acs_connection_string:
        raise ValueError("ACS_CONNECTION_STRING is not configured")

    _client = CallAutomationClient.from_connection_string(settings.acs_connection_string)
    return _client


def join_meeting(
    server_call_id: str,
    callback_url: str,
    ws_url: str,
    locale: str = "en-US",
    display_name: str = "Elephandroid Bot",
) -> str:
    """Connect to an existing Teams meeting and start transcription.

    Args:
        server_call_id: The server call ID from Graph API online meeting.
        callback_url: URL for ACS to send call events (connected, disconnected, etc.).
        ws_url: WebSocket URL for receiving real-time transcript data.
        locale: Transcription language locale.
        display_name: Bot display name in the meeting.

    Returns:
        call_connection_id for tracking this call.
    """
    from azure.communication.callautomation import TranscriptionOptions

    client = _get_client()

    transcription = TranscriptionOptions(
        transport_url=ws_url,
        transport_type="websocket",
        locale=locale,
        start_transcription=True,
    )

    call_connection_properties = client.connect_call(
        callback_url=callback_url,
        server_call_id=server_call_id,
        transcription=transcription,
        source_display_name=display_name,
    )

    call_connection_id = call_connection_properties.call_connection_id
    logger.info(
        "Connected to meeting (server_call_id=%s) — call_connection_id=%s",
        server_call_id,
        call_connection_id,
    )
    return call_connection_id


def hang_up(call_connection_id: str) -> None:
    """Remove the bot from the meeting."""
    client = _get_client()
    call_connection = client.get_call_connection(call_connection_id)
    call_connection.hang_up(is_for_everyone=False)
    logger.info("Bot hung up from call %s", call_connection_id)
