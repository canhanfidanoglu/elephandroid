from pydantic import BaseModel

from src.excel.models import ParsedTask


class ExtractionRequest(BaseModel):
    text: str
    context: str | None = None
    ticket_prefix: str = "AI"


class ExtractionResult(BaseModel):
    plan_name: str | None = None
    tasks: list[ParsedTask] = []


class DocumentExtractionRequest(BaseModel):
    context: str | None = None
    ticket_prefix: str = "AI"
