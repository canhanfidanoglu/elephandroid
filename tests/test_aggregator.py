"""Tests for wizard aggregator (deduplication + merging)."""

from src.wizard.aggregator import (
    _is_duplicate,
    _similarity,
    deduplicate_tasks,
    merge_sources,
    renumber_tasks,
)


class TestSimilarity:
    def test_identical_strings(self):
        assert _similarity("hello", "hello") == 1.0

    def test_case_insensitive(self):
        assert _similarity("Hello World", "hello world") == 1.0

    def test_completely_different(self):
        assert _similarity("abc", "xyz") < 0.5

    def test_similar_strings(self):
        score = _similarity("Implement login page", "Implement login screen")
        assert score > 0.7

    def test_empty_strings(self):
        assert _similarity("", "") == 1.0

    def test_one_empty(self):
        assert _similarity("hello", "") == 0.0


class TestIsDuplicate:
    def test_exact_duplicate(self, make_task):
        existing = [make_task(title="Build login page")]
        new_task = make_task(title="Build login page")
        assert _is_duplicate(new_task, existing) is True

    def test_similar_duplicate(self, make_task):
        existing = [make_task(title="Implement user authentication")]
        new_task = make_task(title="Implement user authentication system")
        assert _is_duplicate(new_task, existing) is True

    def test_not_duplicate(self, make_task):
        existing = [make_task(title="Build login page")]
        new_task = make_task(title="Set up CI/CD pipeline")
        assert _is_duplicate(new_task, existing) is False

    def test_empty_existing(self, make_task):
        new_task = make_task(title="Any task")
        assert _is_duplicate(new_task, []) is False

    def test_case_insensitive(self, make_task):
        existing = [make_task(title="BUILD LOGIN PAGE")]
        new_task = make_task(title="build login page")
        assert _is_duplicate(new_task, existing) is True


class TestDeduplicateTasks:
    def test_no_duplicates(self, make_task):
        tasks = [
            make_task(title="Build the login page"),
            make_task(title="Set up CI/CD pipeline"),
            make_task(title="Write API documentation"),
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 3

    def test_removes_exact_duplicates(self, make_task):
        tasks = [
            make_task(title="Build login page"),
            make_task(title="Build login page"),
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 1
        assert result[0].title == "Build login page"

    def test_keeps_first_occurrence(self, make_task):
        tasks = [
            make_task(ticket_id="A-001", title="Build login"),
            make_task(ticket_id="B-001", title="Build login"),
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 1
        assert result[0].ticket_id == "A-001"

    def test_empty_list(self):
        assert deduplicate_tasks([]) == []

    def test_single_task(self, make_task):
        tasks = [make_task(title="Solo")]
        result = deduplicate_tasks(tasks)
        assert len(result) == 1

    def test_multiple_duplicates(self, make_task):
        tasks = [
            make_task(title="Task Alpha"),
            make_task(title="Task Beta"),
            make_task(title="Task Alpha"),  # dup of 1
            make_task(title="Task Beta"),   # dup of 2
            make_task(title="Task Gamma"),
        ]
        result = deduplicate_tasks(tasks)
        assert len(result) == 3
        titles = [t.title for t in result]
        assert "Task Alpha" in titles
        assert "Task Beta" in titles
        assert "Task Gamma" in titles


class TestRenumberTasks:
    def test_sequential_numbering(self, make_task):
        tasks = [
            make_task(ticket_id="OLD-1", title="A"),
            make_task(ticket_id="OLD-2", title="B"),
            make_task(ticket_id="OLD-3", title="C"),
        ]
        result = renumber_tasks(tasks, prefix="PRJ")
        assert result[0].ticket_id == "PRJ-001"
        assert result[1].ticket_id == "PRJ-002"
        assert result[2].ticket_id == "PRJ-003"

    def test_custom_prefix(self, make_task):
        tasks = [make_task(title="X")]
        result = renumber_tasks(tasks, prefix="SPRINT")
        assert result[0].ticket_id == "SPRINT-001"

    def test_empty_list(self):
        assert renumber_tasks([]) == []


class TestMergeSources:
    def test_single_source(self, make_task):
        sources = [
            ("Meeting", [make_task(title="Build login page"), make_task(title="Set up CI/CD")])
        ]
        result = merge_sources(sources, prefix="PRJ")
        assert len(result) == 2
        assert result[0].ticket_id == "PRJ-001"
        assert result[1].ticket_id == "PRJ-002"

    def test_multiple_sources_with_dedup(self, make_task):
        sources = [
            ("Meeting", [make_task(title="Build API"), make_task(title="Write docs")]),
            ("Email", [make_task(title="Build API"), make_task(title="Deploy to staging")]),
        ]
        result = merge_sources(sources, prefix="WIZ")
        assert len(result) == 3
        titles = [t.title for t in result]
        assert "Build API" in titles
        assert "Write docs" in titles
        assert "Deploy to staging" in titles
        # All renumbered
        assert result[0].ticket_id == "WIZ-001"

    def test_empty_sources(self):
        result = merge_sources([], prefix="X")
        assert result == []

    def test_all_duplicates(self, make_task):
        sources = [
            ("S1", [make_task(title="Same task")]),
            ("S2", [make_task(title="Same task")]),
            ("S3", [make_task(title="Same task")]),
        ]
        result = merge_sources(sources)
        assert len(result) == 1
