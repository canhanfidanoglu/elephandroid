"""Subscription plan gating dependency for FastAPI routes."""

import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.billing.models import Subscription
from src.database import get_db

logger = logging.getLogger(__name__)

# Plan hierarchy (higher index = more features)
PLAN_LEVELS = {"free": 0, "pro": 1, "enterprise": 2}


def require_plan(min_plan: str) -> Callable:
    """FastAPI dependency factory that checks the tenant has at least `min_plan`.

    Usage:
        @router.get("/feature", dependencies=[Depends(require_plan("pro"))])
        async def feature(): ...
    """
    min_level = PLAN_LEVELS.get(min_plan, 0)

    async def _check_plan(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> None:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")

        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        # No subscription record → treat as free tier
        current_level = PLAN_LEVELS.get(
            subscription.plan if subscription else "free", 0
        )

        if current_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"This feature requires a {min_plan} plan or higher. "
                f"Current plan: {subscription.plan if subscription else 'free'}",
            )

    return _check_plan
