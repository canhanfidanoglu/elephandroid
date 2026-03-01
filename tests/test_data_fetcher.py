"""Tests for report data_fetcher logic (build_plan_report)."""

from unittest.mock import AsyncMock, patch

import pytest

from src.planner.models import BucketInfo, TaskInfo
from src.reports.data_fetcher import CATEGORY_EPIC_MAP, build_plan_report


def _mock_httpx_response(title="Test Plan"):
    """Create a mock httpx response for plan details.

    httpx Response.json() is a regular (sync) method, so use MagicMock.
    """
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"title": title}
    return mock_resp


@pytest.fixture
def mock_planner():
    """Patch list_tasks and list_buckets."""
    with (
        patch("src.reports.data_fetcher.list_tasks", new_callable=AsyncMock) as m_tasks,
        patch("src.reports.data_fetcher.list_buckets", new_callable=AsyncMock) as m_buckets,
        patch("src.reports.data_fetcher.httpx.AsyncClient") as m_http,
    ):
        # Default: mock httpx plan fetch
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(return_value=_mock_httpx_response("My Plan"))
        m_http.return_value = ctx

        yield m_tasks, m_buckets


@pytest.mark.asyncio
class TestBuildPlanReport:
    async def test_empty_plan(self, mock_planner):
        m_tasks, m_buckets = mock_planner
        m_tasks.return_value = []
        m_buckets.return_value = [
            BucketInfo(id="b1", name="To Do", plan_id="p1", order_hint=""),
        ]

        report = await build_plan_report("token", "plan-1")
        assert report.plan_name == "My Plan"
        assert report.total_tasks == 0
        assert report.completed_tasks == 0
        assert report.overall_percentage == 0.0
        assert len(report.buckets) == 1
        assert report.buckets[0].total == 0

    async def test_mixed_tasks(self, mock_planner):
        m_tasks, m_buckets = mock_planner
        m_tasks.return_value = [
            TaskInfo(id="t1", title="Done task", bucket_id="b1", percent_complete=100, priority=5),
            TaskInfo(id="t2", title="WIP task", bucket_id="b1", percent_complete=50, priority=3),
            TaskInfo(id="t3", title="Todo task", bucket_id="b1", percent_complete=0, priority=9),
            TaskInfo(id="t4", title="Done task 2", bucket_id="b2", percent_complete=100, priority=5),
        ]
        m_buckets.return_value = [
            BucketInfo(id="b1", name="Sprint 1", plan_id="p1", order_hint=""),
            BucketInfo(id="b2", name="Sprint 2", plan_id="p1", order_hint=""),
        ]

        report = await build_plan_report("token", "plan-1")
        assert report.total_tasks == 4
        assert report.completed_tasks == 2
        assert report.overall_percentage == 50.0

        # Check bucket breakdown
        s1 = next(b for b in report.buckets if b.name == "Sprint 1")
        assert s1.total == 3
        assert s1.completed == 1
        assert s1.in_progress == 1
        assert s1.not_started == 1

        s2 = next(b for b in report.buckets if b.name == "Sprint 2")
        assert s2.total == 1
        assert s2.completed == 1

    async def test_all_completed(self, mock_planner):
        m_tasks, m_buckets = mock_planner
        m_tasks.return_value = [
            TaskInfo(id="t1", title="T1", bucket_id="b1", percent_complete=100, priority=5),
            TaskInfo(id="t2", title="T2", bucket_id="b1", percent_complete=100, priority=5),
        ]
        m_buckets.return_value = [
            BucketInfo(id="b1", name="B1", plan_id="p1", order_hint=""),
        ]

        report = await build_plan_report("token", "plan-1")
        assert report.overall_percentage == 100.0
        assert report.completed_tasks == 2

    async def test_epic_progress(self, mock_planner):
        m_tasks, m_buckets = mock_planner
        m_tasks.return_value = [
            TaskInfo(
                id="t1", title="T1", bucket_id="b1", percent_complete=100,
                applied_categories={"category1": True},
            ),
            TaskInfo(
                id="t2", title="T2", bucket_id="b1", percent_complete=0,
                applied_categories={"category1": True},
            ),
            TaskInfo(
                id="t3", title="T3", bucket_id="b1", percent_complete=100,
                applied_categories={"category4": True},
            ),
        ]
        m_buckets.return_value = [
            BucketInfo(id="b1", name="B1", plan_id="p1", order_hint=""),
        ]

        report = await build_plan_report("token", "plan-1")
        assert len(report.epics) == 2

        pf = next(e for e in report.epics if e.name == "Product Foundation")
        assert pf.total == 2
        assert pf.completed == 1
        assert pf.percentage == 50.0

        ai = next(e for e in report.epics if e.name == "AI/ML Core")
        assert ai.total == 1
        assert ai.completed == 1
        assert ai.percentage == 100.0

    async def test_task_in_unknown_bucket(self, mock_planner):
        m_tasks, m_buckets = mock_planner
        m_tasks.return_value = [
            TaskInfo(id="t1", title="Orphan", bucket_id="unknown-bucket", percent_complete=100),
        ]
        m_buckets.return_value = [
            BucketInfo(id="b1", name="Known", plan_id="p1", order_hint=""),
        ]

        report = await build_plan_report("token", "plan-1")
        # Task still counted in totals
        assert report.total_tasks == 1
        assert report.completed_tasks == 1
        # Known bucket has 0 tasks
        assert report.buckets[0].total == 0


class TestCategoryEpicMap:
    def test_all_six_categories(self):
        assert len(CATEGORY_EPIC_MAP) == 6
        assert "category1" in CATEGORY_EPIC_MAP
        assert "category6" in CATEGORY_EPIC_MAP

    def test_values_are_strings(self):
        for key, val in CATEGORY_EPIC_MAP.items():
            assert isinstance(key, str)
            assert isinstance(val, str)
