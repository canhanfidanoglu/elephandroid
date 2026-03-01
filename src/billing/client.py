"""Stripe API client wrapper."""

import logging

import stripe

from src.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_api_key


async def create_customer(tenant_id: str, email: str, name: str = "") -> stripe.Customer:
    """Create a Stripe customer for a tenant."""
    return stripe.Customer.create(
        email=email,
        name=name or email,
        metadata={"tenant_id": tenant_id},
    )


async def create_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """Create a Stripe Checkout session for subscription."""
    return stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )


async def create_portal_session(customer_id: str, return_url: str) -> stripe.billing_portal.Session:
    """Create a Stripe Customer Portal session for subscription management."""
    return stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )


async def cancel_subscription(subscription_id: str) -> stripe.Subscription:
    """Cancel a Stripe subscription at period end."""
    return stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=True,
    )


async def get_subscription(subscription_id: str) -> stripe.Subscription:
    """Retrieve a Stripe subscription."""
    return stripe.Subscription.retrieve(subscription_id)
