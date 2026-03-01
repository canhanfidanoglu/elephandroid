"""Tests for chat CRUD action helpers (pure functions, no API calls)."""

from src.chat.actions import _find_task_by_title, _format_task_list, _STATUS_MAP, _PRIORITY_LABELS


class TestFindTaskByTitle:
    def test_exact_match(self, make_task_info):
        tasks = [
            make_task_info(id="1", title="Build login page"),
            make_task_info(id="2", title="Write unit tests"),
        ]
        result = _find_task_by_title(tasks, "Build login page")
        assert result is not None
        assert result.id == "1"

    def test_case_insensitive(self, make_task_info):
        tasks = [make_task_info(id="1", title="Build Login Page")]
        result = _find_task_by_title(tasks, "build login page")
        assert result is not None
        assert result.id == "1"

    def test_partial_match(self, make_task_info):
        tasks = [make_task_info(id="1", title="Build login page for mobile app")]
        result = _find_task_by_title(tasks, "login page")
        assert result is not None
        assert result.id == "1"

    def test_exact_preferred_over_partial(self, make_task_info):
        tasks = [
            make_task_info(id="1", title="Build login page for mobile"),
            make_task_info(id="2", title="login page"),
        ]
        result = _find_task_by_title(tasks, "login page")
        assert result is not None
        assert result.id == "2"  # exact match

    def test_no_match(self, make_task_info):
        tasks = [make_task_info(id="1", title="Build login page")]
        result = _find_task_by_title(tasks, "Deploy to production")
        assert result is None

    def test_empty_list(self):
        result = _find_task_by_title([], "anything")
        assert result is None

    def test_whitespace_handling(self, make_task_info):
        tasks = [make_task_info(id="1", title="Build login page")]
        result = _find_task_by_title(tasks, "  Build login page  ")
        assert result is not None


class TestFormatTaskList:
    def test_empty_tasks(self, make_bucket):
        result = _format_task_list([], [make_bucket()])
        assert result == "No tasks found in this plan."

    def test_single_task(self, make_task_info, make_bucket):
        tasks = [make_task_info(title="My Task", bucket_id="b1", percent_complete=0, priority=5)]
        buckets = [make_bucket(id="b1", name="Sprint 1")]
        result = _format_task_list(tasks, buckets)
        assert "1 tasks" in result
        assert "Sprint 1" in result
        assert "My Task" in result
        assert "Not Started" in result

    def test_status_labels(self, make_task_info, make_bucket):
        tasks = [
            make_task_info(id="1", title="Done task", bucket_id="b1", percent_complete=100),
            make_task_info(id="2", title="WIP task", bucket_id="b1", percent_complete=50),
            make_task_info(id="3", title="Todo task", bucket_id="b1", percent_complete=0),
        ]
        buckets = [make_bucket(id="b1", name="Bucket")]
        result = _format_task_list(tasks, buckets)
        assert "Done" in result
        assert "In Progress" in result
        assert "Not Started" in result
        assert "1 done" in result
        assert "1 in progress" in result

    def test_grouped_by_bucket(self, make_task_info, make_bucket):
        tasks = [
            make_task_info(id="1", title="Task A", bucket_id="b1"),
            make_task_info(id="2", title="Task B", bucket_id="b2"),
        ]
        buckets = [
            make_bucket(id="b1", name="Sprint 1"),
            make_bucket(id="b2", name="Sprint 2"),
        ]
        result = _format_task_list(tasks, buckets)
        assert "Sprint 1" in result
        assert "Sprint 2" in result

    def test_unknown_bucket(self, make_task_info, make_bucket):
        tasks = [make_task_info(title="Orphan", bucket_id="xxx")]
        buckets = [make_bucket(id="b1", name="Known")]
        result = _format_task_list(tasks, buckets)
        assert "Unknown" in result

    def test_due_date_shown(self, make_task_info, make_bucket):
        tasks = [make_task_info(title="T", bucket_id="b1", due_date="2025-03-15T00:00:00Z")]
        buckets = [make_bucket(id="b1", name="B")]
        result = _format_task_list(tasks, buckets)
        assert "due 2025-03-15" in result

    def test_priority_labels(self, make_task_info, make_bucket):
        tasks = [make_task_info(title="Urgent one", bucket_id="b1", priority=1)]
        buckets = [make_bucket(id="b1", name="B")]
        result = _format_task_list(tasks, buckets)
        assert "Urgent" in result


class TestStatusMap:
    def test_completed_variants(self):
        for word in ["completed", "done", "finished", "complete"]:
            assert _STATUS_MAP[word] == 100

    def test_in_progress_variants(self):
        for word in ["in progress", "started", "working", "active"]:
            assert _STATUS_MAP[word] == 50

    def test_not_started_variants(self):
        for word in ["not started", "reopen", "todo", "pending"]:
            assert _STATUS_MAP[word] == 0


class TestPriorityLabels:
    def test_all_labels(self):
        assert _PRIORITY_LABELS[1] == "Urgent"
        assert _PRIORITY_LABELS[3] == "Important"
        assert _PRIORITY_LABELS[5] == "Medium"
        assert _PRIORITY_LABELS[9] == "Low"
