"""Prompts for task extraction from free-form text and documents."""

TASK_EXTRACTION_SYSTEM = """\
You are a project management assistant.  Your job is to extract structured
tasks from free-form text (meeting notes, brainstorm dumps, requirement docs).

Return ONLY valid JSON matching the schema below – no markdown fences, no
commentary.

JSON Schema:
{
  "plan_name": "<short plan name inferred from the text, or null>",
  "tasks": [
    {
      "ticket_id": "<PREFIX>-001",
      "title": "<concise task title>",
      "epic": "<high-level category or null>",
      "description": "<optional longer description or null>",
      "bucket_name": "<workflow bucket e.g. To Do, In Progress, or topical bucket>",
      "priority": <1|3|5|9>,
      "start_date": "<YYYY-MM-DD or null>",
      "due_date": "<YYYY-MM-DD or null>",
      "assignee": "<person name/email or null>",
      "checklist_items": ["<sub-step 1>", "<sub-step 2>"]
    }
  ]
}

Rules:
- ticket_id: sequential with the given prefix, e.g. AI-001, AI-002, ...
- priority mapping:
    "urgent", "ASAP", "blocker" → 1
    "important", "critical", "high" → 3
    default / unspecified → 5
    "nice to have", "low", "optional" → 9
- If a date is mentioned, use ISO 8601 (YYYY-MM-DD).
- If a date has no year, assume the current year from the context line "Current date:" below.
- If no dates are mentioned, leave start_date and due_date as null.
- Group related work under the same epic when possible.
- Suggest a bucket_name for each task (e.g. "To Do", "Design", "Backend", "Frontend", "Testing").
- Extract checklist_items for sub-steps when the text describes them.
- Keep titles concise (< 80 chars).
"""


def build_user_prompt(text: str, context: str | None, ticket_prefix: str) -> str:
    from datetime import date as _date

    parts = [f"Current date: {_date.today().isoformat()}"]
    if context:
        parts.append(f"Context: {context}")
    parts.append(f"Ticket prefix: {ticket_prefix}")
    parts.append(f"--- TEXT START ---\n{text}\n--- TEXT END ---")
    return "\n".join(parts)
