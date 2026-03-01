"""Graph API client for Teams online meetings and transcripts."""

import asyncio
import logging
from urllib.parse import quote

import httpx

BASE_URL = "https://graph.microsoft.com/v1.0"
BETA_URL = "https://graph.microsoft.com/beta"
MAX_RETRIES = 3

logger = logging.getLogger(__name__)


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        response = await client.request(method, url, **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "5"))
            await asyncio.sleep(retry_after)
            continue
        if response.status_code >= 500:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
                continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def list_calendar_teams_meetings(
    access_token: str,
    after: str | None = None,
    before: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List calendar events that are Teams meetings.

    Returns dicts with: id, subject, start, end, organizer, attendees,
    join_url, meeting_id (extracted from body).
    """
    headers = _headers(access_token)
    params: dict = {
        "$top": str(limit),
        "$orderby": "start/dateTime desc",
        "$select": "id,subject,start,end,organizer,attendees,onlineMeeting,isOnlineMeeting,bodyPreview",
    }
    filters = []
    if after:
        filters.append(f"start/dateTime ge '{after}'")
    if before:
        filters.append(f"start/dateTime le '{before}'")
    if filters:
        params["$filter"] = " and ".join(filters)

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await _request_with_retry(
            client, "GET", "/me/events", headers=headers, params=params
        )
        events = resp.json().get("value", [])

    meetings = []
    for ev in events:
        join_url = None
        online = ev.get("onlineMeeting")
        if online:
            join_url = online.get("joinUrl")
        if not join_url:
            continue  # not a Teams meeting

        organizer = ev.get("organizer", {}).get("emailAddress", {})
        attendees = [
            a.get("emailAddress", {}).get("address", "")
            for a in ev.get("attendees", [])
        ]
        meetings.append(
            {
                "event_id": ev["id"],
                "subject": ev.get("subject", ""),
                "start": ev.get("start", {}).get("dateTime", ""),
                "end": ev.get("end", {}).get("dateTime", ""),
                "organizer_name": organizer.get("name", ""),
                "organizer_email": organizer.get("address", ""),
                "attendees": attendees,
                "join_url": join_url,
            }
        )
    return meetings


async def _find_online_meeting_id(
    access_token: str, join_url: str
) -> str | None:
    """Find the online meeting ID by its join URL."""
    headers = _headers(access_token)
    encoded_url = quote(join_url, safe="")
    filter_str = f"JoinWebUrl eq '{join_url}'"
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        try:
            resp = await _request_with_retry(
                client,
                "GET",
                "/me/onlineMeetings",
                headers=headers,
                params={"$filter": filter_str},
            )
            meetings = resp.json().get("value", [])
            if meetings:
                return meetings[0]["id"]
        except httpx.HTTPStatusError as exc:
            logger.warning("Failed to find online meeting: %s", exc)
    return None


async def get_transcript_content(
    access_token: str, join_url: str
) -> dict:
    """Fetch transcript for a Teams meeting.

    Returns: {"content": str, "transcript_id": str} or raises ValueError.
    """
    meeting_id = await _find_online_meeting_id(access_token, join_url)
    if not meeting_id:
        raise ValueError("Could not find online meeting. Meeting may not exist or you may lack OnlineMeetings.Read permission.")

    headers = _headers(access_token)

    async with httpx.AsyncClient(base_url=BETA_URL) as client:
        # List transcripts
        resp = await _request_with_retry(
            client,
            "GET",
            f"/me/onlineMeetings/{meeting_id}/transcripts",
            headers=headers,
        )
        transcripts = resp.json().get("value", [])
        if not transcripts:
            raise ValueError("No transcripts available for this meeting. Ensure transcription was enabled during the meeting.")

        transcript_id = transcripts[0]["id"]

        # Get transcript content (text/vtt format)
        content_headers = {
            **headers,
            "Accept": "text/vtt",
        }
        content_resp = await _request_with_retry(
            client,
            "GET",
            f"/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
            headers=content_headers,
            params={"$format": "text/vtt"},
        )
        raw_vtt = content_resp.text

    # Parse VTT to plain text
    plain_text = _parse_vtt(raw_vtt)
    return {"content": plain_text, "transcript_id": transcript_id}


def _parse_vtt(vtt_text: str) -> str:
    """Parse WebVTT transcript into readable plain text.

    Extracts speaker and text, deduplicates consecutive same-speaker lines.
    """
    lines = vtt_text.split("\n")
    result = []
    current_speaker = None

    for line in lines:
        line = line.strip()
        # Skip VTT headers, timestamps, and empty lines
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        # Lines like "1", "2" etc. are cue IDs
        if line.isdigit():
            continue

        # Try to extract speaker: "Speaker Name: text"
        if ": " in line:
            parts = line.split(": ", 1)
            speaker = parts[0].strip("<>v")
            text = parts[1] if len(parts) > 1 else ""
        else:
            speaker = None
            text = line

        if not text.strip():
            continue

        if speaker and speaker != current_speaker:
            result.append(f"\n{speaker}:")
            current_speaker = speaker
        result.append(text)

    return " ".join(result).strip()
