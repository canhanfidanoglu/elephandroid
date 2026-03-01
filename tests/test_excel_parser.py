from datetime import date
from io import BytesIO

import openpyxl
import pytest

from src.excel.models import ColumnMapping, ParsedTask
from src.excel.parser import parse_excel


def _make_workbook(rows: list[list], sheet_name="Product Backlog") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    # Header row matching the backlog format
    ws.append(["Ticket ID", "Epic", "Task Title", "Checklist Item", "Assignee", "Priority", "Bucket", "Start Date", "Due Date", "Notes"])
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


class TestParseExcel:
    def test_task_with_checklist(self):
        data = _make_workbook([
            ["FTR-1", "Epic 1", "My Task", None, None, "High", "Backlog", "2025-03-03", "2025-03-10", None],
            [None, "Epic 1", "My Task", "Checklist item 1", None, None, None, None, None, None],
            [None, "Epic 1", "My Task", "Checklist item 2", None, None, None, None, None, None],
        ])
        tasks = parse_excel(data)
        assert len(tasks) == 1
        t = tasks[0]
        assert t.ticket_id == "FTR-1"
        assert t.title == "My Task"
        assert t.epic == "Epic 1"
        assert t.bucket_name == "Backlog"
        assert t.priority == 3  # High
        assert t.checklist_items == ["Checklist item 1", "Checklist item 2"]

    def test_multiple_tasks(self):
        data = _make_workbook([
            ["FTR-1", "Epic", "Task 1", None, None, "High", "Backlog", None, None, None],
            [None, None, None, "Sub 1", None, None, None, None, None, None],
            ["FTR-2", "Epic", "Task 2", None, None, "Low", "Sprint 1", None, None, None],
            [None, None, None, "Sub A", None, None, None, None, None, None],
            [None, None, None, "Sub B", None, None, None, None, None, None],
        ])
        tasks = parse_excel(data)
        assert len(tasks) == 2
        assert tasks[0].ticket_id == "FTR-1"
        assert tasks[0].checklist_items == ["Sub 1"]
        assert tasks[1].ticket_id == "FTR-2"
        assert tasks[1].checklist_items == ["Sub A", "Sub B"]
        assert tasks[1].bucket_name == "Sprint 1"

    def test_task_without_checklist(self):
        data = _make_workbook([
            ["FTR-1", "Epic", "Task 1", None, None, "Medium", "Backlog", None, None, "Some notes"],
        ])
        tasks = parse_excel(data)
        assert len(tasks) == 1
        assert tasks[0].checklist_items == []
        assert tasks[0].description == "Some notes"

    def test_priority_mapping(self):
        data = _make_workbook([
            ["T1", None, "Task", None, None, "Critical", None, None, None, None],
            ["T2", None, "Task", None, None, "High", None, None, None, None],
            ["T3", None, "Task", None, None, "Medium", None, None, None, None],
            ["T4", None, "Task", None, None, "Low", None, None, None, None],
            ["T5", None, "Task", None, None, None, None, None, None, None],
        ])
        tasks = parse_excel(data)
        assert tasks[0].priority == 1  # Critical
        assert tasks[1].priority == 3  # High
        assert tasks[2].priority == 5  # Medium
        assert tasks[3].priority == 9  # Low
        assert tasks[4].priority is None

    def test_real_backlog_file(self):
        tasks = parse_excel("/Users/canhanfidanoglu/Projects/Elephandroid/data/backlog.xlsx")
        assert len(tasks) > 0
        # First task should be FTR-1
        assert tasks[0].ticket_id == "FTR-1"
        assert tasks[0].title == "Market Research & Competitor Analysis"
        assert len(tasks[0].checklist_items) > 0
        # All tasks should have ticket IDs
        for t in tasks:
            assert t.ticket_id.startswith("FTR-")

    def test_empty_workbook(self):
        data = _make_workbook([])
        tasks = parse_excel(data)
        assert tasks == []
