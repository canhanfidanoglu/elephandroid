import io
import json
from collections.abc import AsyncGenerator
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.prompts import NL_REPORT_SYSTEM
from src.providers import stream_chat

from .data_fetcher import build_plan_report
from .docx_builder import build_docx
from .pptx_builder import build_pptx

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/plan-progress")
async def plan_progress_json(
    plan_id: str = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return plan progress report as JSON."""
    report = await build_plan_report(user.access_token, plan_id)
    return report


@router.get("/plan-progress/pptx")
async def plan_progress_pptx(
    plan_id: str = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return plan progress report as a PPTX file download."""
    report = await build_plan_report(user.access_token, plan_id)
    pptx_bytes = build_pptx(report)
    return StreamingResponse(
        io.BytesIO(pptx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="{report.plan_name}_report.pptx"'
        },
    )


@router.get("/plan-progress/docx")
async def plan_progress_docx(
    plan_id: str = Query(...),
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Return plan progress report as a DOCX file download."""
    report = await build_plan_report(user.access_token, plan_id)
    docx_bytes = build_docx(report)
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{report.plan_name}_report.docx"'
        },
    )


# --- Natural Language Report ---


class NLReportRequest(BaseModel):
    plan_id: str
    query: str  # e.g. "Bu haftaki ilerleme nasil?", "Show overdue tasks"


async def _stream_nl_report(
    report_data: str, query: str
) -> AsyncGenerator[str, None]:
    """Stream an LLM-generated report from plan data."""
    system = NL_REPORT_SYSTEM.format(current_date=date.today().isoformat())
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Project data:\n{report_data}\n\nUser request: {query}"},
    ]
    async for chunk in stream_chat(messages):
        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/natural-language")
async def natural_language_report(
    body: NLReportRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Generate an LLM-powered natural language report from Planner data.

    Streams the response as SSE chunks.
    Examples:
    - "Bu haftaki ilerleme nasil?"
    - "List overdue tasks and blockers"
    - "Sprint 2 burndown durumu"
    - "Give me a summary for the weekly standup"
    """
    report = await build_plan_report(user.access_token, body.plan_id)
    report_data = report.model_dump_json(indent=2)

    return StreamingResponse(
        _stream_nl_report(report_data, body.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
