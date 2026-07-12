"""Support chatbot: endpoint contract (SDK mocked) and shop tools (real db).
The Anthropic key is blanked under pytest, so tests opt in per-case."""
import json
from unittest import mock

import anthropic
import pytest
from django.test import override_settings

from orders.models import Coupon, Order
from support.chat import (check_coupon, get_order_status, orders_summary_for,
                          search_products)
from tests.api.test_shop_flow import order_payload

pytestmark = pytest.mark.django_db

CHAT_ON = dict(ANTHROPIC_API_KEY='sk-ant-test')


def post_chat(client, message='hi', history=None):
    return client.post('/api/support/chat/',
                       {'message': message, 'history': history or []},
                       format='json')


def test_chat_unconfigured_returns_503(api_client):
    assert post_chat(api_client).status_code == 503


@override_settings(**CHAT_ON)
@mock.patch('support.views.run_chat', return_value='hello from haiku')
def test_chat_roundtrip(run_chat, api_client):
    res = post_chat(api_client, 'do you sell keyboards?')
    assert res.status_code == 200
    body = res.json()
    assert body['reply'] == 'hello from haiku'
    assert body['history'][-2:] == [
        {'role': 'user', 'content': 'do you sell keyboards?'},
        {'role': 'assistant', 'content': 'hello from haiku'},
    ]
    assert run_chat.call_args.args == ([], 'do you sell keyboards?')


@override_settings(**CHAT_ON)
def test_chat_rejects_bad_input(api_client):
    assert post_chat(api_client, message='  ').status_code == 400
    assert post_chat(api_client, history=[{'role': 'system', 'content': 'x'}]
                     ).status_code == 400
    too_long = [{'role': 'user', 'content': 'x'}] * 31
    assert post_chat(api_client, history=too_long).status_code == 400


@override_settings(**CHAT_ON)
@mock.patch('support.views.run_chat')
def test_chat_maps_api_errors(run_chat, api_client):
    run_chat.side_effect = anthropic.APIConnectionError(request=mock.Mock())
    assert post_chat(api_client).status_code == 502


@override_settings(**CHAT_ON)
@mock.patch('support.views.run_chat', return_value='ok')
def test_chat_throttled_after_limit(run_chat, api_client):
    for _ in range(20):
        assert post_chat(api_client).status_code == 200
    assert post_chat(api_client).status_code == 429


# --- shop tools against the real db ---

def test_get_order_status_tool(api_client, make_product, checkout_fields):
    product = make_product(name='Ergo Mouse', stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product, 2),
                               format='json').json()['id']
    data = json.loads(get_order_status(order_id))
    assert data['status'] == 'pending'
    assert data['items'] == [{'product': 'Ergo Mouse', 'quantity': 2,
                              'price': '10.00'}]
    assert data['payment'] is None


def test_get_order_status_tool_unknown_id():
    assert json.loads(get_order_status('not-a-uuid')) == {'error': 'no order with that id'}
    assert json.loads(get_order_status('3abb4c99-1a74-44af-8be6-de143a9cc0d9')
                      ) == {'error': 'no order with that id'}


def test_search_products_tool(make_product):
    make_product(name='Mechanical Keyboard', price='129.90', stock=3)
    make_product(name='Sold Out Keyboard', slug='sold-out', stock=0, is_active=False)
    data = json.loads(search_products('keyboard'))
    assert [r['name'] for r in data['results']] == ['Mechanical Keyboard']
    assert data['results'][0]['in_stock'] == 3


def test_check_coupon_tool(db):
    Coupon.objects.create(code='TEN', discount_type=Coupon.DiscountType.PERCENT,
                          value='10.00')
    assert json.loads(check_coupon('ten'))['valid'] is True
    assert json.loads(check_coupon('NOPE')) == {'valid': False}


def test_orders_summary_tool(user, api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product),
                               format='json').json()['id']
    Order.objects.filter(pk=order_id).update(user=user)
    data = json.loads(orders_summary_for(user))
    assert [o['id'] for o in data['orders']] == [order_id]
