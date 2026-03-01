"""Adaptive Card templates for rich Teams bot responses."""

from __future__ import annotations


def task_list_card(plan_name: str, tasks: list[dict]) -> dict:
    """Build an Adaptive Card showing a list of Planner tasks.

    Each task shows title, status, priority, and due date.
    """
    priority_labels = {1: "Urgent", 3: "High", 5: "Medium", 9: "Low"}
    priority_colors = {1: "Attention", 3: "Warning", 5: "Default", 9: "Good"}

    task_rows = []
    for t in tasks:
        pct = t.get("percent_complete", 0)
        if pct == 100:
            status = "Done"
            status_color = "Good"
        elif pct > 0:
            status = "In Progress"
            status_color = "Warning"
        else:
            status = "Not Started"
            status_color = "Default"

        pri = t.get("priority", 5)
        pri_label = priority_labels.get(pri, "Medium")
        pri_color = priority_colors.get(pri, "Default")

        due = t.get("due_date") or "-"

        task_rows.append(
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": t.get("title", "Untitled"),
                                "weight": "Bolder" if pct < 100 else "Default",
                                "wrap": True,
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": status,
                                "color": status_color,
                                "horizontalAlignment": "Center",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": pri_label,
                                "color": pri_color,
                                "horizontalAlignment": "Center",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": due[:10] if due != "-" else "-",
                                "horizontalAlignment": "Center",
                            }
                        ],
                    },
                ],
            }
        )

    # Summary counts
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("percent_complete", 0) == 100)
    in_prog = sum(
        1 for t in tasks if 0 < t.get("percent_complete", 0) < 100
    )
    not_started = total - done - in_prog

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Tasks: {plan_name}",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": (
                    f"{total} tasks | {done} done | "
                    f"{in_prog} in progress | {not_started} not started"
                ),
                "isSubtle": True,
                "spacing": "None",
            },
            {"type": "ColumnSet", "columns": [
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": "Task", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "Status", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "Priority", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "Due", "weight": "Bolder"}
                ]},
            ]},
            *task_rows,
        ],
    }


def extracted_tasks_card(tasks: list[dict], source: str = "text") -> dict:
    """Build an Adaptive Card showing extracted tasks for review."""
    task_items = []
    for t in tasks:
        pri_map = {1: "Urgent", 3: "High", 5: "Medium", 9: "Low"}
        pri_label = pri_map.get(t.get("priority", 5), "Medium")
        bucket = t.get("bucket_name") or "To Do"

        task_items.append(
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": t.get("ticket_id", ""),
                                "weight": "Bolder",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": t.get("title", "Untitled"),
                                "wrap": True,
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {"type": "TextBlock", "text": pri_label}
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {"type": "TextBlock", "text": bucket}
                        ],
                    },
                ],
            }
        )

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Extracted Tasks (from {source})",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": f"{len(tasks)} tasks extracted",
                "isSubtle": True,
                "spacing": "None",
            },
            {"type": "ColumnSet", "columns": [
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "ID", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "stretch", "items": [
                    {"type": "TextBlock", "text": "Task", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "Priority", "weight": "Bolder"}
                ]},
                {"type": "Column", "width": "auto", "items": [
                    {"type": "TextBlock", "text": "Bucket", "weight": "Bolder"}
                ]},
            ]},
            *task_items,
        ],
    }


def report_card(report_text: str, plan_name: str) -> dict:
    """Build an Adaptive Card for a natural language report."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Report: {plan_name}",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": report_text,
                "wrap": True,
            },
        ],
    }


def project_created_card(
    plan_title: str, plan_id: str, task_count: int, sync_summary: dict
) -> dict:
    """Build an Adaptive Card confirming project creation."""
    created = sync_summary.get("created", 0)
    failed = sync_summary.get("failed", 0)
    buckets = sync_summary.get("buckets_created", 0)

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Project Created",
                "size": "Large",
                "weight": "Bolder",
                "color": "Good",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Plan", "value": plan_title},
                    {"title": "Tasks Created", "value": str(created)},
                    {"title": "Buckets Created", "value": str(buckets)},
                    {"title": "Failed", "value": str(failed)},
                ],
            },
        ],
    }


def error_card(title: str, message: str) -> dict:
    """Build an Adaptive Card for error messages."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "size": "Medium",
                "weight": "Bolder",
                "color": "Attention",
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ],
    }


def help_card() -> dict:
    """Build an Adaptive Card with available bot commands."""
    commands = [
        ("/tasks <plan_id>", "List tasks in a Planner plan"),
        ("/extract <text>", "Extract tasks from text using AI"),
        ("/create-project", "Create a Planner project from extracted tasks"),
        ("/report <plan_id>", "Generate a natural language progress report"),
        ("/help", "Show this help message"),
    ]

    cmd_items = []
    for cmd, desc in commands:
        cmd_items.append(
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "auto",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": f"`{cmd}`",
                                "fontType": "Monospace",
                                "weight": "Bolder",
                            }
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {"type": "TextBlock", "text": desc, "wrap": True}
                        ],
                    },
                ],
            }
        )

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "Elephandroid Bot",
                "size": "Large",
                "weight": "Bolder",
            },
            {
                "type": "TextBlock",
                "text": "Available commands:",
                "isSubtle": True,
                "spacing": "None",
            },
            *cmd_items,
        ],
    }
