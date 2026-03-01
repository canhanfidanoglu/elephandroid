"""Billing API routes — checkout, portal, webhook, subscription status."""

import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import AuthenticatedUser, get_current_user
from src.auth.models import User
from src.billing import client as stripe_client
from src.billing.models import Subscription
from src.config import settings
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# ── Plan definitions ────────────────────────────────────────────────

PLANS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "stripe_price_id": None,
        "features": ["5 tasks/month", "Basic reports"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "stripe_price_id": settings.stripe_pro_price_id,
        "features": [
            "Unlimited tasks",
            "AI extraction",
            "RAG chat",
            "Meeting summaries",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": 99,
        "stripe_price_id": settings.stripe_enterprise_price_id,
        "features": [
            "Everything in Pro",
            "Teams Bot",
            "Priority support",
            "Custom integrations",
        ],
    },
}


# ── Request / Response schemas ──────────────────────────────────────


class CheckoutRequest(BaseModel):
    plan: str  # "pro" | "enterprise"
    success_url: str = "http://localhost:8000/billing/success"
    cancel_url: str = "http://localhost:8000/billing/cancel"


class PortalRequest(BaseModel):
    return_url: str = "http://localhost:8000/"


# ── Helpers ─────────────────────────────────────────────────────────


async def _get_or_create_subscription(
    db: AsyncSession, user: AuthenticatedUser
) -> Subscription:
    """Get the subscription for a user, or create a free-tier Stripe customer."""
    stmt = select(Subscription).where(Subscription.user_id == user.user_id)
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if subscription:
        return subscription

    # Look up tenant_id from User table
    user_row = await db.get(User, user.user_id)
    tenant_id = user_row.tenant_id if user_row else ""

    # Create Stripe customer
    customer = await stripe_client.create_customer(
        tenant_id=tenant_id, email=user.email, name=user.display_name
    )

    subscription = Subscription(
        tenant_id=tenant_id,
        user_id=user.user_id,
        stripe_customer_id=customer.id,
        plan="free",
        status="active",
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


# ── Routes ──────────────────────────────────────────────────────────


@router.get("/plans")
async def list_plans() -> dict:
    """List available subscription plans with pricing."""
    return {
        "plans": {
            key: {k: v for k, v in plan.items() if k != "stripe_price_id"}
            for key, plan in PLANS.items()
        }
    }


@router.get("/subscription")
async def get_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current user's subscription status."""
    subscription = await _get_or_create_subscription(db, user)
    return {
        "plan": subscription.plan,
        "status": subscription.status,
        "stripe_customer_id": subscription.stripe_customer_id,
        "current_period_end": (
            subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None
        ),
    }


@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a Stripe Checkout session for upgrading to a paid plan."""
    if body.plan not in ("pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'pro' or 'enterprise'.")

    price_id = PLANS[body.plan]["stripe_price_id"]
    if not price_id:
        raise HTTPException(status_code=400, detail="Stripe price ID not configured for this plan.")

    subscription = await _get_or_create_subscription(db, user)

    session = await stripe_client.create_checkout_session(
        customer_id=subscription.stripe_customer_id,
        price_id=price_id,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal(
    body: PortalRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a Stripe Customer Portal session for managing subscription."""
    subscription = await _get_or_create_subscription(db, user)
    session = await stripe_client.create_portal_session(
        customer_id=subscription.stripe_customer_id,
        return_url=body.return_url,
    )
    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Stripe webhook events. Verifies signature for security."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(db, data)
    else:
        logger.debug("Unhandled Stripe event: %s", event_type)

    return {"status": "ok"}


# ── Webhook handlers ────────────────────────────────────────────────


def _plan_from_price_id(price_id: str) -> str:
    """Map a Stripe price ID back to our plan name."""
    for plan_key, plan_info in PLANS.items():
        if plan_info.get("stripe_price_id") == price_id:
            return plan_key
    return "free"


async def _handle_checkout_completed(db: AsyncSession, session_data: dict) -> None:
    """Process a successful checkout — link subscription to customer."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    if not customer_id or not subscription_id:
        return

    stmt = select(Subscription).where(
        Subscription.stripe_customer_id == customer_id
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning("No subscription record for customer %s", customer_id)
        return

    # Fetch the Stripe subscription to get plan details
    stripe_sub = await stripe_client.get_subscription(subscription_id)
    price_id = stripe_sub["items"]["data"][0]["price"]["id"] if stripe_sub["items"]["data"] else ""

    subscription.stripe_subscription_id = subscription_id
    subscription.plan = _plan_from_price_id(price_id)
    subscription.status = stripe_sub["status"]
    subscription.current_period_end = datetime.utcfromtimestamp(
        stripe_sub["current_period_end"]
    )
    subscription.updated_at = datetime.utcnow()

    await db.commit()
    logger.info(
        "Checkout completed: customer=%s plan=%s", customer_id, subscription.plan
    )


async def _handle_subscription_updated(db: AsyncSession, sub_data: dict) -> None:
    """Handle subscription status changes (upgrade, downgrade, renewal)."""
    stripe_sub_id = sub_data.get("id")

    stmt = select(Subscription).where(
        Subscription.stripe_subscription_id == stripe_sub_id
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning("No subscription record for stripe sub %s", stripe_sub_id)
        return

    price_id = sub_data["items"]["data"][0]["price"]["id"] if sub_data.get("items", {}).get("data") else ""

    subscription.plan = _plan_from_price_id(price_id)
    subscription.status = sub_data.get("status", subscription.status)
    if sub_data.get("current_period_end"):
        subscription.current_period_end = datetime.utcfromtimestamp(
            sub_data["current_period_end"]
        )
    subscription.updated_at = datetime.utcnow()

    await db.commit()
    logger.info(
        "Subscription updated: %s → plan=%s status=%s",
        stripe_sub_id,
        subscription.plan,
        subscription.status,
    )


async def _handle_subscription_deleted(db: AsyncSession, sub_data: dict) -> None:
    """Handle subscription cancellation."""
    stripe_sub_id = sub_data.get("id")

    stmt = select(Subscription).where(
        Subscription.stripe_subscription_id == stripe_sub_id
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    subscription.plan = "free"
    subscription.status = "canceled"
    subscription.updated_at = datetime.utcnow()

    await db.commit()
    logger.info("Subscription canceled: %s", stripe_sub_id)


async def _handle_payment_failed(db: AsyncSession, invoice_data: dict) -> None:
    """Handle failed payment — mark subscription as past_due."""
    customer_id = invoice_data.get("customer")

    stmt = select(Subscription).where(
        Subscription.stripe_customer_id == customer_id
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    subscription.status = "past_due"
    subscription.updated_at = datetime.utcnow()

    await db.commit()
    logger.info("Payment failed for customer %s — marked past_due", customer_id)
