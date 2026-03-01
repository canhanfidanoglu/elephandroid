"""Tests for Teams Bot module — cards and bot command parsing."""

import pytest

from src.teams_bot.cards import (
    error_card,
    extracted_tasks_card,
    help_card,
    project_created_card,
    report_card,
    task_list_card,
)


# ── Adaptive Card Tests ───────────────────────────────────────────────


class TestTaskListCard:
    def test_empty_task_list(self):
        card = task_list_card("Test Plan", [])
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.5"
        # Header should contain plan name
        assert any(
            "Test Plan" in str(item.get("text", ""))
            for item in card["body"]
        )

    def test_task_list_with_tasks(self):
        tasks = [
            {
                "title": "Task 1",
                "percent_complete": 100,
                "priority": 1,
                "due_date": "2025-06-01",
            },
            {
                "title": "Task 2",
                "percent_complete": 50,
                "priority": 5,
                "due_date": None,
            },
            {
                "title": "Task 3",
                "percent_complete": 0,
                "priority": 9,
                "due_date": "2025-07-01",
            },
        ]
        card = task_list_card("My Plan", tasks)
        assert card["type"] == "AdaptiveCard"
        # Should have header + summary + column header + 3 task rows
        body = card["body"]
        assert len(body) >= 6

    def test_summary_counts(self):
        tasks = [
            {"title": "Done", "percent_complete": 100, "priority": 5},
            {"title": "WIP", "percent_complete": 50, "priority": 5},
            {"title": "New", "percent_complete": 0, "priority": 5},
        ]
        card = task_list_card("Plan", tasks)
        summary = card["body"][1]["text"]
        assert "3 tasks" in summary
        assert "1 done" in summary
        assert "1 in progress" in summary
        assert "1 not started" in summary


class TestExtractedTasksCard:
    def test_extraction_card(self):
        tasks = [
            {
                "ticket_id": "BOT-001",
                "title": "Setup auth",
                "priority": 3,
                "bucket_name": "Backend",
            },
            {
                "ticket_id": "BOT-002",
                "title": "Write tests",
                "priority": 5,
                "bucket_name": "Testing",
            },
        ]
        card = extracted_tasks_card(tasks, source="meeting notes")
        assert card["type"] == "AdaptiveCard"
        assert "meeting notes" in card["body"][0]["text"]
        assert "2 tasks" in card["body"][1]["text"]


class TestReportCard:
    def test_report_card(self):
        card = report_card("All tasks are on track.", "Sprint 1")
        assert card["type"] == "AdaptiveCard"
        body_texts = [item.get("text", "") for item in card["body"]]
        assert "Report: Sprint 1" in body_texts
        assert "All tasks are on track." in body_texts


class TestProjectCreatedCard:
    def test_project_created(self):
        card = project_created_card(
            "New Project",
            "plan-123",
            5,
            {"created": 5, "failed": 0, "buckets_created": 2},
        )
        assert card["type"] == "AdaptiveCard"
        facts = card["body"][1]["facts"]
        fact_values = {f["title"]: f["value"] for f in facts}
        assert fact_values["Plan"] == "New Project"
        assert fact_values["Tasks Created"] == "5"
        assert fact_values["Buckets Created"] == "2"
        assert fact_values["Failed"] == "0"


class TestErrorCard:
    def test_error_card(self):
        card = error_card("Something went wrong", "Connection timeout")
        assert card["type"] == "AdaptiveCard"
        assert card["body"][0]["text"] == "Something went wrong"
        assert card["body"][0]["color"] == "Attention"
        assert card["body"][1]["text"] == "Connection timeout"


class TestHelpCard:
    def test_help_card_structure(self):
        card = help_card()
        assert card["type"] == "AdaptiveCard"
        assert card["body"][0]["text"] == "Elephandroid Bot"
        # Should have header + subtitle + 5 command rows
        assert len(card["body"]) >= 7

    def test_help_card_commands(self):
        card = help_card()
        # Flatten all text from the card
        all_text = str(card)
        assert "/tasks" in all_text
        assert "/extract" in all_text
        assert "/create-project" in all_text
        assert "/report" in all_text
        assert "/help" in all_text
