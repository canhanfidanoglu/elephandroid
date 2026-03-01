"""Aggregate tasks from multiple sources, deduplicate, and merge."""

import logging
from difflib import SequenceMatcher

from src.excel.models import ParsedTask

logger = logging.getLogger(__name__)

# Similarity threshold for considering two tasks as duplicates
_SIMILARITY_THRESHOLD = 0.75


def _similarity(a: str, b: str) -> float:
    """Compute string similarity ratio (0.0 – 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_duplicate(task: ParsedTask, existing: list[ParsedTask]) -> bool:
    """Check if a task is a duplicate of any in the existing list."""
    for e in existing:
        if _similarity(task.title, e.title) >= _SIMILARITY_THRESHOLD:
            return True
    return False


def deduplicate_tasks(all_tasks: list[ParsedTask]) -> list[ParsedTask]:
    """Remove duplicate tasks based on title similarity.

    Keeps the first occurrence (higher priority source should come first).
    """
    unique: list[ParsedTask] = []
    duplicates_removed = 0
    for task in all_tasks:
        if _is_duplicate(task, unique):
            duplicates_removed += 1
            logger.debug("Duplicate removed: '%s'", task.title)
        else:
            unique.append(task)

    if duplicates_removed:
        logger.info("Deduplicated: %d duplicates removed, %d unique tasks", duplicates_removed, len(unique))
    return unique


def renumber_tasks(tasks: list[ParsedTask], prefix: str = "PRJ") -> list[ParsedTask]:
    """Re-assign sequential ticket IDs to the merged task list."""
    for idx, task in enumerate(tasks, start=1):
        task.ticket_id = f"{prefix}-{idx:03d}"
    return tasks


def merge_sources(
    sources: list[tuple[str, list[ParsedTask]]],
    prefix: str = "PRJ",
) -> list[ParsedTask]:
    """Merge tasks from multiple named sources, deduplicate, and renumber.

    Args:
        sources: List of (source_label, tasks) tuples.
                 e.g. [("Meeting 1", [...]), ("Email thread", [...]), ...]
        prefix: Ticket prefix for the merged project.

    Returns:
        Deduplicated and renumbered task list.
    """
    all_tasks: list[ParsedTask] = []
    for label, tasks in sources:
        logger.info("Source '%s': %d tasks", label, len(tasks))
        all_tasks.extend(tasks)

    logger.info("Total tasks before dedup: %d", len(all_tasks))
    unique = deduplicate_tasks(all_tasks)
    renumbered = renumber_tasks(unique, prefix)
    logger.info("Final merged: %d tasks", len(renumbered))
    return renumbered
