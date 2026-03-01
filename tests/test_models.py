"""Tests for Pydantic models (ParsedTask, ColumnMapping, SyncResult)."""

from datetime import date

import pytest
from pydantic import ValidationError

from src.excel.models import ColumnMapping, ParsedTask
from src.sync.engine import SyncResult, _resolve_categories, EPIC_CATEGORY_MAP


class TestParsedTask:
    def test_minimal_construction(self):
        t = ParsedTask(ticket_id="T-001", title="Hello")
        assert t.ticket_id == "T-001"
        assert t.title == "Hello"
        assert t.epic is None
        assert t.bucket_name is None
        assert t.priority is None
        assert t.checklist_items == []

    def test_full_construction(self):
        t = ParsedTask(
            ticket_id="PRJ-042",
            title="Build login page",
            epic="Product Foundation",
            description="Notes go here",
            bucket_name="Sprint 1",
            priority=3,
            start_date=date(2025, 1, 1),
            due_date=date(2025, 1, 31),
            assignee="alice@example.com",
            checklist_items=["Design", "Implement", "Test"],
        )
        assert t.priority == 3
        assert len(t.checklist_items) == 3
        assert t.start_date == date(2025, 1, 1)
        assert t.description == "Notes go here"

    def test_date_from_string(self):
        t = ParsedTask(ticket_id="T-1", title="x", due_date="2025-06-15")
        assert t.due_date == date(2025, 6, 15)

    def test_invalid_date_raises(self):
        with pytest.raises(ValidationError):
            ParsedTask(ticket_id="T-1", title="x", due_date="not-a-date")

    def test_checklist_default_empty(self):
        t = ParsedTask(ticket_id="T-1", title="x")
        assert t.checklist_items == []
        # Ensure different instances don't share the list
        t2 = ParsedTask(ticket_id="T-2", title="y")
        t.checklist_items.append("item")
        assert t2.checklist_items == []


class TestColumnMapping:
    def test_defaults(self):
        m = ColumnMapping()
        assert m.ticket_id == "A"
        assert m.title == "C"
        assert m.start_row == 2
        assert m.sheet_name is None
        assert m.sheet_as_bucket is False

    def test_custom_mapping(self):
        m = ColumnMapping(title="D", start_row=5, sheet_as_bucket=True)
        assert m.title == "D"
        assert m.start_row == 5
        assert m.sheet_as_bucket is True


class TestSyncResult:
    def test_initial_state(self):
        r = SyncResult()
        assert r.total_rows == 0
        assert r.tasks_created == 0
        assert r.tasks_failed == 0
        assert r.errors == []

    def test_to_dict(self):
        r = SyncResult()
        r.total_rows = 10
        r.tasks_created = 8
        r.tasks_failed = 2
        r.errors = ["err1", "err2"]
        d = r.to_dict()
        assert d == {
            "total_rows": 10,
            "tasks_created": 8,
            "tasks_failed": 2,
            "errors": ["err1", "err2"],
        }

    def test_errors_independence(self):
        r1 = SyncResult()
        r2 = SyncResult()
        r1.errors.append("oops")
        assert r2.errors == []


class TestResolveCategories:
    def test_known_epic(self):
        assert _resolve_categories("Product Foundation") == {"category1": True}

    def test_case_insensitive(self):
        assert _resolve_categories("AI/ML CORE") == {"category4": True}

    def test_unknown_epic(self):
        assert _resolve_categories("Unknown Epic") == {}

    def test_none_epic(self):
        assert _resolve_categories(None) == {}

    def test_empty_string(self):
        assert _resolve_categories("") == {}

    def test_all_epics_mapped(self):
        for epic_name, cat_key in EPIC_CATEGORY_MAP.items():
            result = _resolve_categories(epic_name)
            assert result == {cat_key: True}, f"Failed for {epic_name}"
