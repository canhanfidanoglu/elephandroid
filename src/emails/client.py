"""Graph API client for Outlook email messages."""

import asyncio
import logging
from html.parser import HTMLParser

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


class _HTMLTextExtractor(HTMLParser):
    """Strip HTML tags, keeping only text content."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._pieces.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        # Collapse multiple blank lines
        lines = [line.strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def strip_html(html: str) -> str:
    """Convert HTML to plain text."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


async def list_inbox_messages(
    access_token: str,
    top: int = 20,
    after: str | None = None,
    before: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """List recent inbox messages.

    Args:
        access_token: Azure AD access token.
        top: Number of messages to retrieve.
        after: ISO datetime string; only return messages received after this.
        before: ISO datetime string; only return messages received before this.
        search: Free-text search query (Graph API $search on messages).

    Returns:
        List of dicts with id, subject, from_name, from_email, preview,
        received_at, has_attachments.
    """
    headers = _headers(access_token)
    params: dict[str, str] = {
        "$top": str(top),
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,bodyPreview,receivedDateTime,hasAttachments",
    }

    # Build $filter from after / before
    filters: list[str] = []
    if after:
        filters.append(f"receivedDateTime ge {after}")
    if before:
        filters.append(f"receivedDateTime le {before}")
    if filters:
        params["$filter"] = " and ".join(filters)

    if search:
        params["$search"] = f'"{search}"'

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client, "GET", f"{BASE_URL}/me/messages", headers=headers, params=params
        )
        messages = resp.json().get("value", [])

    result = []
    for msg in messages:
        from_addr = msg.get("from", {}).get("emailAddress", {})
        result.append(
            {
                "id": msg["id"],
                "subject": msg.get("subject", "(no subject)"),
                "from_name": from_addr.get("name", ""),
                "from_email": from_addr.get("address", ""),
                "preview": msg.get("bodyPreview", ""),
                "received_at": msg.get("receivedDateTime", ""),
                "has_attachments": msg.get("hasAttachments", False),
            }
        )
    return result


async def get_message_body(access_token: str, message_id: str) -> dict:
    """Fetch a single message's full body as plain text.

    Returns:
        Dict with subject, from_name, from_email, body_text, received_at.
    """
    headers = _headers(access_token)

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client, "GET", f"{BASE_URL}/me/messages/{message_id}",
            headers=headers, params={"$select": "subject,from,body,receivedDateTime"}
        )
        msg = resp.json()

    from_addr = msg.get("from", {}).get("emailAddress", {})
    body = msg.get("body", {})
    body_content = body.get("content", "")
    if body.get("contentType", "").lower() == "html":
        body_text = strip_html(body_content)
    else:
        body_text = body_content

    return {
        "subject": msg.get("subject", "(no subject)"),
        "from_name": from_addr.get("name", ""),
        "from_email": from_addr.get("address", ""),
        "body_text": body_text,
        "received_at": msg.get("receivedDateTime", ""),
    }


async def get_message_attachments(access_token: str, message_id: str) -> list[dict]:
    """Fetch attachments for a message.

    Returns list of dicts with: id, name, content_type, size, content_bytes (base64).
    Only returns file attachments (not item attachments).
    """
    headers = _headers(access_token)
    params = {"$select": "id,name,contentType,size,contentBytes"}

    async with httpx.AsyncClient() as client:
        resp = await _request_with_retry(
            client,
            "GET",
            f"{BASE_URL}/me/messages/{message_id}/attachments",
            headers=headers,
            params=params,
        )
        attachments = resp.json().get("value", [])

    result = []
    for att in attachments:
        if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue
        result.append(
            {
                "id": att.get("id", ""),
                "name": att.get("name", ""),
                "content_type": att.get("contentType", ""),
                "size": att.get("size", 0),
                "content_bytes": att.get("contentBytes", ""),
            }
        )
    return result


async def get_multiple_message_bodies(
    access_token: str, message_ids: list[str]
) -> list[dict]:
    """Fetch bodies for multiple messages. Returns list of body dicts."""
    results = []
    for message_id in message_ids:
        body = await get_message_body(access_token, message_id)
        results.append(body)
    return results
