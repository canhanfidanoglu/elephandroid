"""Bot routes — join meetings, receive ACS callbacks, WebSocket for transcription."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.config import settings
from src.meetings.client import _find_online_meeting_id

from .client import hang_up, join_meeting
from .events import handle_callback_events, parse_websocket_transcription
from .transcript import ActiveCall, get_call, list_active_calls, register_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"])


class JoinMeetingRequest(BaseModel):
    join_url: str
    meeting_subject: str = ""
    locale: str = "en-US"


@router.post("/join-meeting")
async def join_meeting_endpoint(
    body: JoinMeetingRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Send the bot to join a Teams meeting and start transcription.

    Requires the meeting's join URL (from calendar event).
    The bot connects, starts real-time transcription, and accumulates
    the transcript in memory until the call ends.
    """
    # 1. Resolve online meeting ID from join URL
    meeting_id = await _find_online_meeting_id(user.access_token, body.join_url)
    if not meeting_id:
        raise HTTPException(
            status_code=404,
            detail="Could not find Teams meeting. Ensure you have OnlineMeetings.Read permission.",
        )

    # 2. Get server_call_id from Graph API
    # For connect_call, we need the server_call_id which is the meeting ID for Teams meetings
    server_call_id = meeting_id

    # 3. Build callback and WebSocket URLs
    callback_url = f"{settings.acs_callback_url}"
    ws_url = settings.acs_callback_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = ws_url.replace("/callbacks", "/ws/transcription")

    # 4. Connect bot to meeting
    try:
        call_connection_id = join_meeting(
            server_call_id=server_call_id,
            callback_url=callback_url,
            ws_url=ws_url,
            locale=body.locale,
        )
    except Exception as exc:
        logger.error("Failed to join meeting: %s", exc)
        raise HTTPException(status_code=502, detail=f"Failed to join meeting: {exc}")

    # 5. Register active call
    active_call = ActiveCall(
        call_connection_id=call_connection_id,
        server_call_id=server_call_id,
        meeting_subject=body.meeting_subject,
        meeting_join_url=body.join_url,
        user_id=user.user_id,
        access_token=user.access_token,
    )
    register_call(active_call)

    return {
        "call_connection_id": call_connection_id,
        "status": "connected",
        "meeting_subject": body.meeting_subject,
    }


@router.post("/leave-meeting")
async def leave_meeting_endpoint(
    call_connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Remove the bot from a meeting."""
    call = get_call(call_connection_id)
    if not call:
        raise HTTPException(status_code=404, detail="Active call not found")

    try:
        hang_up(call_connection_id)
    except Exception as exc:
        logger.error("Failed to hang up: %s", exc)
        raise HTTPException(status_code=502, detail=f"Failed to leave meeting: {exc}")

    return {"status": "left", "call_connection_id": call_connection_id}


@router.get("/active-calls")
async def get_active_calls(
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    """List currently active bot calls."""
    return list_active_calls()


@router.get("/transcript/{call_connection_id}")
async def get_live_transcript(
    call_connection_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Get the current transcript for an active call."""
    call = get_call(call_connection_id)
    if not call:
        raise HTTPException(status_code=404, detail="Active call not found")
    return {
        "call_connection_id": call_connection_id,
        "meeting_subject": call.meeting_subject,
        "entry_count": len(call.entries),
        "transcript": call.get_plain_text(),
        "is_active": call.is_active,
    }


# --- ACS Callback Endpoint ---

@router.post("/callbacks")
async def acs_callbacks(request: Request) -> dict:
    """Receive call events from ACS (CallConnected, CallDisconnected, etc.)."""
    body = await request.json()
    # ACS sends events as a list
    events = body if isinstance(body, list) else [body]
    await handle_callback_events(events)
    return {"status": "ok"}


# --- WebSocket for Real-Time Transcription ---

@router.websocket("/ws/transcription")
async def transcription_websocket(websocket: WebSocket):
    """WebSocket endpoint that ACS sends real-time transcription data to.

    ACS connects here and streams transcript chunks as JSON messages.
    We parse each message and add it to the corresponding active call's transcript.
    """
    await websocket.accept()
    logger.info("Transcription WebSocket connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            entry = parse_websocket_transcription(data)
            if entry is None:
                continue

            # Find the active call to add this entry to
            # ACS includes callConnectionId in metadata
            call_connection_id = data.get("callConnectionId", "")
            call = get_call(call_connection_id)
            if call:
                call.add_entry(entry)
            else:
                # If we can't match, try to add to any active call
                # (fallback for single-call scenarios)
                active = list_active_calls()
                if active:
                    fallback_call = get_call(active[0]["call_connection_id"])
                    if fallback_call:
                        fallback_call.add_entry(entry)

    except WebSocketDisconnect:
        logger.info("Transcription WebSocket disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
