"""Teams bot implementation using Bot Framework SDK.

Extends TeamsActivityHandler to handle messages in Teams channels and 1:1 chats.
Integrates with existing Elephandroid services (Planner, AI extraction, reports).
"""

from __future__ import annotations

import json
import logging
from datetime import date

from botbuilder.core import CardFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from . import cards

try:
    from botbuilder.core.teams import TeamsActivityHandler
except ImportError:
    # Fallback if teams extension is not available
    from botbuilder.core import ActivityHandler as TeamsActivityHandler

logger = logging.getLogger(__name__)

# In-memory store for last extraction results per conversation (for /create-project flow)
_extraction_cache: dict[str, dict] = {}


class ElephandroidBot(TeamsActivityHandler):
    """Conversational Teams bot for Elephandroid.

    Handles slash commands and natural language messages in Teams.
    Uses on-behalf-of flow or direct Graph API calls via the user's
    access token obtained from bot SSO (when configured).
    """

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle incoming messages — dispatch slash commands or echo help."""
        text = (turn_context.activity.text or "").strip()

        # Teams sometimes prepends the bot mention — strip it
        if turn_context.activity.entities:
            for entity in turn_context.activity.entities:
                if entity.type == "mention":
                    mentioned_text = getattr(entity, "text", "") or ""
                    text = text.replace(mentioned_text, "").strip()

        if not text:
            await self._send_help(turn_context)
            return

        # Parse command
        lower = text.lower()
        if lower.startswith("/help") or lower == "help":
            await self._send_help(turn_context)
        elif lower.startswith("/tasks"):
            await self._handle_tasks(turn_context, text)
        elif lower.startswith("/extract"):
            await self._handle_extract(turn_context, text)
        elif lower.startswith("/create-project"):
            await self._handle_create_project(turn_context, text)
        elif lower.startswith("/report"):
            await self._handle_report(turn_context, text)
        else:
            # Treat as natural language — show help
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=(
                        f'I received: "{text}"\n\n'
                        "Use /help to see available commands, or try:\n"
                        "- `/tasks <plan_id>` to list tasks\n"
                        "- `/extract <text>` to extract tasks from text\n"
                        "- `/report <plan_id>` for a progress report"
                    ),
                )
            )

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        """Send a welcome message when the bot is added to a conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                card = cards.help_card()
                attachment = CardFactory.adaptive_card(card)
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        attachments=[attachment],
                        text="Welcome to Elephandroid! Here are the available commands.",
                    )
                )

    # ── Command Handlers ──────────────────────────────────────────────

    async def _send_help(self, turn_context: TurnContext) -> None:
        card = cards.help_card()
        attachment = CardFactory.adaptive_card(card)
        await turn_context.send_activity(
            Activity(type=ActivityTypes.message, attachments=[attachment])
        )

    async def _handle_tasks(self, turn_context: TurnContext, text: str) -> None:
        """Handle /tasks <plan_id> — list tasks from a Planner plan."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="Usage: `/tasks <plan_id>`\n\nProvide the Planner plan ID.",
                )
            )
            return

        plan_id = parts[1].strip()

        try:
            from src.planner.client import list_tasks

            # Bot uses application-level permissions, so access_token comes from
            # bot credentials or OBO flow. For now, we use a placeholder that
            # the route layer will replace with a real token.
            access_token = self._get_access_token(turn_context)
            if not access_token:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text="Authentication required. Please configure bot SSO or provide a token.",
                    )
                )
                return

            tasks = await list_tasks(access_token, plan_id)

            if not tasks:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text=f"No tasks found in plan `{plan_id}`.",
                    )
                )
                return

            # Get plan name
            import httpx

            async with httpx.AsyncClient(
                base_url="https://graph.microsoft.com/v1.0"
            ) as client:
                resp = await client.get(
                    f"/planner/plans/{plan_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                plan_name = resp.json().get("title", plan_id)

            task_dicts = [
                {
                    "title": t.title,
                    "percent_complete": t.percent_complete,
                    "priority": t.priority,
                    "due_date": t.due_date,
                    "bucket_id": t.bucket_id,
                }
                for t in tasks
            ]
            card = cards.task_list_card(plan_name, task_dicts)
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )
        except Exception as exc:
            logger.error("Error listing tasks: %s", exc, exc_info=True)
            card = cards.error_card("Failed to list tasks", str(exc))
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )

    async def _handle_extract(self, turn_context: TurnContext, text: str) -> None:
        """Handle /extract <text> — extract tasks from free-form text."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=(
                        "Usage: `/extract <text>`\n\n"
                        "Paste meeting notes, requirements, or any text to extract tasks."
                    ),
                )
            )
            return

        input_text = parts[1].strip()

        try:
            from src.ai.task_extractor import extract_from_text

            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="Extracting tasks... This may take a moment.",
                )
            )

            result = await extract_from_text(
                text=input_text, context=None, ticket_prefix="BOT"
            )

            if not result.tasks:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text="No tasks could be extracted from the provided text.",
                    )
                )
                return

            # Cache for /create-project
            conv_id = turn_context.activity.conversation.id
            _extraction_cache[conv_id] = {
                "tasks": [t.model_dump(mode="json") for t in result.tasks],
                "plan_name": result.plan_name,
            }

            task_dicts = [t.model_dump(mode="json") for t in result.tasks]
            card = cards.extracted_tasks_card(task_dicts, source="text")
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[attachment],
                    text=(
                        f"Extracted {len(result.tasks)} tasks. "
                        "Use `/create-project <group_id> [plan_title]` to create a Planner project."
                    ),
                )
            )
        except Exception as exc:
            logger.error("Error extracting tasks: %s", exc, exc_info=True)
            card = cards.error_card("Failed to extract tasks", str(exc))
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )

    async def _handle_create_project(
        self, turn_context: TurnContext, text: str
    ) -> None:
        """Handle /create-project <group_id> [plan_title].

        Uses cached extraction results from the last /extract command.
        """
        conv_id = turn_context.activity.conversation.id
        cached = _extraction_cache.get(conv_id)

        if not cached or not cached.get("tasks"):
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=(
                        "No extracted tasks found. "
                        "Run `/extract <text>` first to extract tasks."
                    ),
                )
            )
            return

        parts = text.split(maxsplit=2)
        if len(parts) < 2 or not parts[1].strip():
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=(
                        "Usage: `/create-project <group_id> [plan_title]`\n\n"
                        "Provide the M365 group ID. Optional plan title after it."
                    ),
                )
            )
            return

        group_id = parts[1].strip()
        plan_title = parts[2].strip() if len(parts) > 2 else (
            cached.get("plan_name") or "Bot-Created Plan"
        )

        access_token = self._get_access_token(turn_context)
        if not access_token:
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="Authentication required.",
                )
            )
            return

        try:
            from src.excel.models import ParsedTask
            from src.planner.client import create_plan, set_plan_categories
            from src.sync.engine import EPIC_CATEGORY_MAP, sync_tasks_to_planner

            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=f"Creating project '{plan_title}'...",
                )
            )

            tasks = [ParsedTask(**t) for t in cached["tasks"]]

            plan = await create_plan(access_token, group_id, plan_title)

            category_labels = {v: k.title() for k, v in EPIC_CATEGORY_MAP.items()}
            try:
                await set_plan_categories(access_token, plan.id, category_labels)
            except Exception:
                pass  # non-critical

            sync_result = await sync_tasks_to_planner(
                access_token=access_token,
                tasks=tasks,
                plan_id=plan.id,
                default_bucket_id="",
                auto_create_buckets=True,
            )

            card = cards.project_created_card(
                plan_title, plan.id, len(tasks), sync_result.to_dict()
            )
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )

            # Clear cache
            _extraction_cache.pop(conv_id, None)

        except Exception as exc:
            logger.error("Error creating project: %s", exc, exc_info=True)
            card = cards.error_card("Failed to create project", str(exc))
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )

    async def _handle_report(self, turn_context: TurnContext, text: str) -> None:
        """Handle /report <plan_id> [query] — generate a natural language report."""
        parts = text.split(maxsplit=2)
        if len(parts) < 2 or not parts[1].strip():
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=(
                        "Usage: `/report <plan_id> [question]`\n\n"
                        "Example: `/report abc123 What is the sprint progress?`"
                    ),
                )
            )
            return

        plan_id = parts[1].strip()
        query = parts[2].strip() if len(parts) > 2 else "Give me a progress summary."

        access_token = self._get_access_token(turn_context)
        if not access_token:
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="Authentication required.",
                )
            )
            return

        try:
            from src.prompts import NL_REPORT_SYSTEM
            from src.providers import stream_chat
            from src.reports.data_fetcher import build_plan_report

            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="Generating report...",
                )
            )

            report = await build_plan_report(access_token, plan_id)
            report_data = report.model_dump_json(indent=2)

            system = NL_REPORT_SYSTEM.format(
                current_date=date.today().isoformat()
            )
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Project data:\n{report_data}\n\n"
                        f"User request: {query}"
                    ),
                },
            ]

            # Collect streamed chunks into full text
            report_text = ""
            async for chunk in stream_chat(messages):
                report_text += chunk

            card = cards.report_card(report_text, report.plan_name)
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )
        except Exception as exc:
            logger.error("Error generating report: %s", exc, exc_info=True)
            card = cards.error_card("Failed to generate report", str(exc))
            attachment = CardFactory.adaptive_card(card)
            await turn_context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[attachment])
            )

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _get_access_token(turn_context: TurnContext) -> str | None:
        """Extract access token from turn state.

        The route handler injects the token into turn state via the
        'access_token' key when it is available from SSO or OBO flow.
        """
        state = turn_context.turn_state or {}
        return state.get("access_token")
