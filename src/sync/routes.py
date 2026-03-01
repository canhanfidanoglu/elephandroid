from fastapi import APIRouter, Depends, Form, UploadFile

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.excel.models import ColumnMapping
from src.sync.engine import sync_excel_to_planner

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/excel-to-planner")
async def excel_to_planner(
    file: UploadFile,
    plan_id: str = Form(...),
    default_bucket_id: str = Form(...),
    sheet_as_bucket: bool = Form(False),
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    file_bytes = await file.read()
    mapping = ColumnMapping(sheet_as_bucket=sheet_as_bucket)
    result = await sync_excel_to_planner(
        access_token=user.access_token,
        file_bytes=file_bytes,
        plan_id=plan_id,
        default_bucket_id=default_bucket_id,
        mapping=mapping,
    )
    return result.to_dict()
