"""FastAPI routes for Teams Bot webhook.

The Bot Framework SDK expects an aiohttp server, but Elephandroid uses FastAPI.
This module bridges the two by manually constructing the adapter pipeline:
  1. Receive POST /api/messages from Azure Bot Service
  2. Deserialize the Activity
  3. Authenticate the incoming request via BotFrameworkAdapter
  4. Dispatch to the ElephandroidBot handler
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response

from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["teams-bot"])

# Lazy-init: adapter and bot are created on first request to avoid
# import errors when botbuilder is not installed.
_adapter = None
_bot = None


def _ensure_initialized():
    """Create the adapter and bot on first use."""
    global _adapter, _bot  # noqa: PLW0603

    if _adapter is not None:
        return

    from botbuilder.core import (
        BotFrameworkAdapter,
        BotFrameworkAdapterSettings,
    )

    from .bot import ElephandroidBot

    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.bot_app_id,
        app_password=settings.bot_app_password,
    )
    _adapter = BotFrameworkAdapter(adapter_settings)

    async def on_error(context, error):
        logger.error(
            "Bot adapter error: %s", error, exc_info=True
        )
        await context.send_activity("An internal error occurred. Please try again.")

    _adapter.on_turn_error = on_error
    _bot = ElephandroidBot()


@router.post("/api/messages")
async def messages(request: Request) -> Response:
    """Receive incoming activities from Azure Bot Service.

    This is the main webhook endpoint that Azure Bot Service sends
    messages to. It handles authentication, deserialization, and
    dispatches to the bot handler.
    """
    _ensure_initialized()

    # Read raw body and headers
    body = await request.body()
    auth_header = request.headers.get("Authorization", "")

    # Bot Framework SDK expects specific Activity format
    from botbuilder.schema import Activity

    activity = Activity().deserialize(await request.json())

    # Process the activity through the adapter
    response = await _adapter.process_activity(
        activity, auth_header, _bot.on_turn
    )

    if response:
        return Response(
            content=response.body,
            status_code=response.status,
            headers=dict(response.headers) if response.headers else None,
        )

    return Response(status_code=200)
