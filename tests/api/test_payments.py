"""Stripe payment flow with the SDK mocked; the fake-provider path lives
in test_shop_flow. Settings blank the stripe keys under pytest, so each
test opts in via override_settings."""
from unittest import mock

import pytest
from django.test import override_settings

from orders.models import Order, Payment
from tests.api.test_shop_flow import order_payload

pytestmark = pytest.mark.django_db

STRIPE_ON = dict(STRIPE_SECRET_KEY='sk_test_x', STRIPE_PUBLISHABLE_KEY='pk_test_x')


@pytest.fixture
def pending_order(api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product),
                               format='json').json()['id']
    return Order.objects.get(pk=order_id)


def intent(id='pi_123', status='requires_payment_method', secret='pi_123_secret'):
    return mock.Mock(id=id, status=status, client_secret=secret)


@override_settings(**STRIPE_ON)
@mock.patch('stripe.PaymentIntent.create')
def test_pay_returns_client_secret(create, api_client, pending_order):
    create.return_value = intent()
    res = api_client.post(f'/api/orders/{pending_order.id}/pay/')
    assert res.status_code == 200
    assert res.json() == {'provider': 'stripe', 'client_secret': 'pi_123_secret',
                          'publishable_key': 'pk_test_x'}
    pending_order.refresh_from_db()
    assert pending_order.payment_intent_id == 'pi_123'
    assert pending_order.status == Order.Status.PENDING
    assert create.call_args.kwargs['metadata'] == {'order_id': str(pending_order.id)}


@override_settings(**STRIPE_ON)
@mock.patch('stripe.PaymentIntent.create')
@mock.patch('stripe.PaymentIntent.retrieve')
def test_pay_reuses_open_intent(retrieve, create, api_client, pending_order):
    pending_order.payment_intent_id = 'pi_old'
    pending_order.save(update_fields=['payment_intent_id'])
    retrieve.return_value = intent(id='pi_old', secret='pi_old_secret')
    res = api_client.post(f'/api/orders/{pending_order.id}/pay/')
    assert res.json()['client_secret'] == 'pi_old_secret'
    create.assert_not_called()


@override_settings(**STRIPE_ON)
@mock.patch('stripe.PaymentIntent.retrieve')
def test_confirm_payment_marks_paid(retrieve, api_client, pending_order):
    pending_order.payment_intent_id = 'pi_123'
    pending_order.save(update_fields=['payment_intent_id'])
    retrieve.return_value = intent(status='succeeded')
    res = api_client.post(f'/api/orders/{pending_order.id}/confirm_payment/')
    assert res.status_code == 200
    assert res.json()['status'] == 'paid'
    assert res.json()['payment']['provider'] == 'stripe'
    assert res.json()['payment']['transaction_id'] == 'pi_123'


@override_settings(**STRIPE_ON)
@mock.patch('stripe.PaymentIntent.retrieve')
def test_confirm_payment_rejects_open_intent(retrieve, api_client, pending_order):
    pending_order.payment_intent_id = 'pi_123'
    pending_order.save(update_fields=['payment_intent_id'])
    retrieve.return_value = intent(status='requires_payment_method')
    res = api_client.post(f'/api/orders/{pending_order.id}/confirm_payment/')
    assert res.status_code == 400
    pending_order.refresh_from_db()
    assert pending_order.status == Order.Status.PENDING


def test_confirm_payment_without_intent_rejected(api_client, pending_order):
    res = api_client.post(f'/api/orders/{pending_order.id}/confirm_payment/')
    assert res.status_code == 400


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_x')
def test_webhook_rejects_bad_signature(api_client):
    res = api_client.post('/api/stripe/webhook/', {'fake': 'event'}, format='json')
    assert res.status_code == 400


def test_webhook_unconfigured_returns_503(api_client):
    res = api_client.post('/api/stripe/webhook/', {'fake': 'event'}, format='json')
    assert res.status_code == 503


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_x')
@mock.patch('stripe.Webhook.construct_event')
def test_webhook_marks_order_paid(construct, api_client, pending_order):
    construct.return_value = {
        'type': 'payment_intent.succeeded',
        'data': {'object': {'id': 'pi_123',
                            'metadata': {'order_id': str(pending_order.id)}}},
    }
    res = api_client.post('/api/stripe/webhook/', {}, format='json')
    assert res.status_code == 200
    pending_order.refresh_from_db()
    assert pending_order.status == Order.Status.PAID
    assert pending_order.payment.transaction_id == 'pi_123'


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_x')
@mock.patch('stripe.Webhook.construct_event')
def test_webhook_ignores_unknown_order(construct, api_client):
    construct.return_value = {
        'type': 'payment_intent.succeeded',
        'data': {'object': {'id': 'pi_123', 'metadata': {}}},
    }
    res = api_client.post('/api/stripe/webhook/', {}, format='json')
    assert res.status_code == 200
    assert Payment.objects.count() == 0


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_x', **STRIPE_ON)
@mock.patch('stripe.PaymentIntent.retrieve')
@mock.patch('stripe.Webhook.construct_event')
def test_webhook_then_confirm_is_idempotent(construct, retrieve, api_client,
                                            pending_order):
    pending_order.payment_intent_id = 'pi_123'
    pending_order.save(update_fields=['payment_intent_id'])
    construct.return_value = {
        'type': 'payment_intent.succeeded',
        'data': {'object': {'id': 'pi_123',
                            'metadata': {'order_id': str(pending_order.id)}}},
    }
    api_client.post('/api/stripe/webhook/', {}, format='json')
    retrieve.return_value = intent(status='succeeded')
    res = api_client.post(f'/api/orders/{pending_order.id}/confirm_payment/')
    assert res.status_code == 200
    assert Payment.objects.filter(order=pending_order).count() == 1
