"""Graph API client for Teams chat messages."""

import asyncio
import logging

import httpx

BASE_URL = "https://graph.microsoft.com/v1.0"
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


async def list_chats(
    access_token: str,
    top: int = 20,
    chat_type: str | None = None,
) -> list[dict]:
    """List the user's recent Teams chats.

    Args:
        access_token: Graph API access token.
        top: Maximum number of chats to return.
        chat_type: Optional filter — "oneOnOne", "group", "meeting", or None for all.
            Filtering is done in Python since /me/chats has limited OData support.

    Returns:
        List of dicts with id, topic, chat_type, last_updated.
    """
    headers = _headers(access_token)

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client, "GET", f"{BASE_URL}/me/chats",
            headers=headers, params={"$top": str(top)}
        )
        chats = resp.json().get("value", [])

    result = []
    for chat in chats:
        raw_chat_type = chat.get("chatType", "")

        # Apply chat_type filter in Python
        if chat_type and raw_chat_type != chat_type:
            continue

        topic = chat.get("topic") or ""
        if not topic:
            topic = f"({raw_chat_type} chat)" if raw_chat_type else "(untitled)"
        result.append(
            {
                "id": chat["id"],
                "topic": topic,
                "chat_type": raw_chat_type,
                "last_updated": chat.get("lastUpdatedDateTime", ""),
            }
        )
    return result


async def get_chat_messages(
    access_token: str, chat_id: str, top: int = 50
) -> list[dict]:
    """Fetch messages from a specific Teams chat.

    Filters out system event messages, returns only user messages.

    Returns:
        List of dicts with from_name, content, created_at.
    """
    headers = _headers(access_token)

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client, "GET", f"{BASE_URL}/me/chats/{chat_id}/messages",
            headers=headers, params={"$top": str(top)}
        )
        messages = resp.json().get("value", [])

    result = []
    for msg in messages:
        # Skip system events
        if msg.get("messageType") != "message":
            continue

        from_user = msg.get("from", {})
        user_info = from_user.get("user", {}) if from_user else {}
        from_name = user_info.get("displayName", "Unknown")

        body = msg.get("body", {})
        content = body.get("content", "")
        if body.get("contentType", "").lower() == "html":
            from src.emails.client import strip_html
            content = strip_html(content)

        if not content.strip():
            continue

        result.append(
            {
                "from_name": from_name,
                "content": content,
                "created_at": msg.get("createdDateTime", ""),
            }
        )

    # Reverse to chronological order
    result.reverse()
    return result


def format_chat_to_text(messages: list[dict]) -> str:
    """Format chat messages into a plain text transcript.

    Similar to meetings/client.py _parse_vtt() output format.
    """
    lines = []
    for msg in messages:
        lines.append(f"{msg['from_name']}: {msg['content']}")
    return "\n".join(lines)


async def get_chat_attachments(
    access_token: str, chat_id: str, top: int = 50
) -> list[dict]:
    """Fetch file attachments shared in a Teams chat.

    Iterates through chat messages and extracts attachment info from messages
    that contain attachments. Teams chat attachments live inside the message
    body, so we extract available metadata for each one.

    Args:
        access_token: Graph API access token.
        chat_id: The Teams chat ID.
        top: Maximum number of messages to scan for attachments.

    Returns:
        List of dicts with name, content_type, content_url, message_from.
    """
    headers = _headers(access_token)

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client, "GET", f"{BASE_URL}/me/chats/{chat_id}/messages",
            headers=headers, params={"$top": str(top)},
        )
        messages = resp.json().get("value", [])

    result: list[dict] = []
    for msg in messages:
        if msg.get("messageType") != "message":
            continue

        attachments = msg.get("attachments") or []
        if not attachments:
            continue

        from_user = msg.get("from", {})
        user_info = from_user.get("user", {}) if from_user else {}
        from_name = user_info.get("displayName", "Unknown")

        for att in attachments:
            result.append(
                {
                    "name": att.get("name", ""),
                    "content_type": att.get("contentType", ""),
                    "content_url": att.get("contentUrl", ""),
                    "message_from": from_name,
                }
            )

    return result


def filter_chats_by_topic(chats: list[dict], query: str) -> list[dict]:
    """Filter chat list by topic/name substring match (case-insensitive).

    Args:
        chats: List of chat dicts (as returned by list_chats).
        query: Substring to search for in the chat topic.

    Returns:
        Filtered list of chat dicts whose topic contains the query.
    """
    lower_query = query.lower()
    return [c for c in chats if lower_query in c.get("topic", "").lower()]
