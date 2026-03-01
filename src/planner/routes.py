from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.auth.dependencies import AuthenticatedUser, get_current_user

from . import client
from .models import BucketInfo, PlanInfo

router = APIRouter(prefix="/planner")


class CreatePlanRequest(BaseModel):
    group_id: str
    title: str


class CreateBucketRequest(BaseModel):
    plan_id: str
    name: str


@router.get("/groups")
async def get_groups(
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    """List Microsoft 365 groups the current user belongs to."""
    return await client.list_groups(user.access_token)


@router.get("/plans")
async def get_plans(
    group_id: str = Query(..., description="The group ID to list plans for"),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[PlanInfo]:
    """List Planner plans for a given group."""
    return await client.list_plans(user.access_token, group_id)


@router.get("/buckets")
async def get_buckets(
    plan_id: str = Query(..., description="The plan ID to list buckets for"),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[BucketInfo]:
    """List buckets within a Planner plan."""
    return await client.list_buckets(user.access_token, plan_id)


@router.post("/plans")
async def post_create_plan(
    body: CreatePlanRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> PlanInfo:
    """Create a new Planner plan in a group."""
    return await client.create_plan(user.access_token, body.group_id, body.title)


@router.post("/buckets")
async def post_create_bucket(
    body: CreateBucketRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> BucketInfo:
    """Create a new bucket within a Planner plan."""
    return await client.create_bucket(user.access_token, body.plan_id, body.name)
