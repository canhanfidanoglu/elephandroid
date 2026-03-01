from fastapi import APIRouter, Depends, Form, UploadFile
from pydantic import BaseModel

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.config import settings
from src.planner.client import create_plan, set_plan_categories
from src.sync.engine import EPIC_CATEGORY_MAP, sync_tasks_to_planner

from src.providers import health_check
from src.providers.factory import get_llm_provider

from .models import ExtractionRequest, ExtractionResult
from .task_extractor import extract_from_document, extract_from_text

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/health")
async def ai_health() -> dict:
    provider = get_llm_provider()
    available = await health_check()
    return {
        "available": available,
        "llm_provider": provider.provider_name,
        "model": provider.model_name,
    }


@router.post("/extract-tasks")
async def extract_tasks(
    body: ExtractionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> ExtractionResult:
    return await extract_from_text(
        text=body.text,
        context=body.context,
        ticket_prefix=body.ticket_prefix,
    )


@router.post("/extract-from-document")
async def extract_from_doc(
    file: UploadFile,
    context: str = Form(""),
    ticket_prefix: str = Form("AI"),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ExtractionResult:
    file_bytes = await file.read()
    return await extract_from_document(
        filename=file.filename or "upload.txt",
        file_bytes=file_bytes,
        context=context or None,
        ticket_prefix=ticket_prefix,
    )


class ExtractAndSyncRequest(BaseModel):
    text: str
    context: str | None = None
    ticket_prefix: str = "AI"
    group_id: str
    plan_id: str | None = None
    plan_title: str | None = None
    auto_create_plan: bool = False
    auto_create_buckets: bool = False
    default_bucket_id: str | None = None


@router.post("/extract-and-sync")
async def extract_and_sync(
    body: ExtractAndSyncRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    # Step 1: Extract tasks
    extraction = await extract_from_text(
        text=body.text,
        context=body.context,
        ticket_prefix=body.ticket_prefix,
    )

    if not extraction.tasks:
        return {"extraction": extraction.model_dump(), "sync": None}

    plan_id = body.plan_id

    # Step 2: Auto-create plan if requested
    if body.auto_create_plan and not plan_id:
        title = body.plan_title or extraction.plan_name or "AI-Generated Plan"
        plan = await create_plan(user.access_token, body.group_id, title)
        plan_id = plan.id

        # Set category labels on the new plan
        category_labels = {v: k.title() for k, v in EPIC_CATEGORY_MAP.items()}
        try:
            await set_plan_categories(
                user.access_token, plan_id, category_labels
            )
        except Exception:
            pass  # non-critical

    if not plan_id:
        return {
            "error": "No plan_id provided and auto_create_plan is False",
            "extraction": extraction.model_dump(),
        }

    # Step 3: Sync to Planner
    default_bucket_id = body.default_bucket_id or ""
    sync_result = await sync_tasks_to_planner(
        access_token=user.access_token,
        tasks=extraction.tasks,
        plan_id=plan_id,
        default_bucket_id=default_bucket_id,
        auto_create_buckets=body.auto_create_buckets,
    )

    return {
        "extraction": extraction.model_dump(),
        "sync": sync_result.to_dict(),
        "plan_id": plan_id,
    }
