from datetime import date

from pydantic import BaseModel


class ColumnMapping(BaseModel):
    ticket_id: str = "A"
    epic: str = "B"
    title: str = "C"
    checklist: str = "D"
    assignee: str = "E"
    priority: str = "F"
    bucket: str = "G"
    start_date: str = "H"
    due_date: str = "I"
    notes: str = "J"
    start_row: int = 2  # skip header
    sheet_name: str | None = None  # None = all sheets
    sheet_as_bucket: bool = False  # True = sheet name becomes bucket name


class ParsedTask(BaseModel):
    ticket_id: str
    title: str
    epic: str | None = None
    description: str | None = None  # from Notes column
    bucket_name: str | None = None
    priority: int | None = None  # Planner: 1=urgent, 3=high, 5=medium, 9=low
    start_date: date | None = None
    due_date: date | None = None
    assignee: str | None = None
    checklist_items: list[str] = []
