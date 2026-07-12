"""Thin wrapper around the Stripe SDK for the embedded Payment Element flow.

Active only when settings.STRIPE_SECRET_KEY is set; orders.views falls back
to the fake provider otherwise.
"""
from decimal import Decimal

import stripe
from django.conf import settings


def to_minor_units(amount):
    """Decimal major units -> int minor units (10.50 -> 1050)."""
    return int((amount * 100).quantize(Decimal('1')))


def payment_intent_for(order):
    """Return an open PaymentIntent for the order, creating one if needed.

    The intent id is stored on the order so repeated pay clicks reuse it
    instead of littering the Stripe account with abandoned intents.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if order.payment_intent_id:
        intent = stripe.PaymentIntent.retrieve(order.payment_intent_id)
        if intent.status not in ('succeeded', 'canceled'):
            return intent
    intent = stripe.PaymentIntent.create(
        amount=to_minor_units(order.total),
        currency=settings.STRIPE_CURRENCY,
        metadata={'order_id': str(order.id)},
        automatic_payment_methods={'enabled': True},
    )
    order.payment_intent_id = intent.id
    order.save(update_fields=['payment_intent_id', 'updated_at'])
    return intent


def retrieve_intent(intent_id):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.PaymentIntent.retrieve(intent_id)
