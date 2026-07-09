"""End-to-end shop flow through the DRF stack: browse, order, pay, cancel."""
import pytest

from orders.models import Coupon, Order

pytestmark = pytest.mark.django_db


def order_payload(checkout_fields, product, quantity=1, **extra):
    return {**checkout_fields,
            'items': [{'product': product.id, 'quantity': quantity}], **extra}


def test_guest_checkout_creates_pending_order(api_client, make_product, checkout_fields):
    product = make_product(price='12.30', stock=5)
    res = api_client.post('/api/orders/', order_payload(checkout_fields, product, 2),
                          format='json')
    assert res.status_code == 201
    body = res.json()
    assert body['status'] == 'pending'
    assert body['total'] == '24.60'
    assert body['items'][0]['product_name'] == 'Widget'


def test_pay_creates_payment_and_transitions(api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product),
                               format='json').json()['id']
    res = api_client.post(f'/api/orders/{order_id}/pay/')
    assert res.status_code == 200
    body = res.json()
    assert body['status'] == 'paid'
    assert body['payment']['provider'] == 'fake'
    assert body['payment']['amount'] == body['total']


def test_double_pay_rejected(api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product),
                               format='json').json()['id']
    api_client.post(f'/api/orders/{order_id}/pay/')
    res = api_client.post(f'/api/orders/{order_id}/pay/')
    assert res.status_code == 400


def test_cancel_restores_stock_via_api(api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product, 3),
                               format='json').json()['id']
    product.refresh_from_db()
    assert product.stock == 2

    res = api_client.post(f'/api/orders/{order_id}/cancel/')
    assert res.status_code == 200
    assert res.json()['status'] == 'cancelled'
    product.refresh_from_db()
    assert product.stock == 5


def test_shipped_order_cannot_be_cancelled(api_client, make_product, checkout_fields):
    product = make_product(stock=5)
    order_id = api_client.post('/api/orders/', order_payload(checkout_fields, product),
                               format='json').json()['id']
    Order.objects.filter(pk=order_id).update(status=Order.Status.SHIPPED)
    res = api_client.post(f'/api/orders/{order_id}/cancel/')
    assert res.status_code == 400


def test_order_with_coupon(api_client, make_product, checkout_fields):
    product = make_product(price='100.00', stock=5)
    Coupon.objects.create(code='TEN', discount_type=Coupon.DiscountType.PERCENT,
                          value='10.00')
    res = api_client.post('/api/orders/',
                          order_payload(checkout_fields, product, 1, coupon_code='TEN'),
                          format='json')
    assert res.status_code == 201
    assert res.json()['total'] == '90.00'
    assert res.json()['coupon_code'] == 'TEN'


def test_coupon_validate_endpoint(api_client, db):
    Coupon.objects.create(code='TEN', discount_type=Coupon.DiscountType.FIXED,
                          value='10.00')
    ok = api_client.post('/api/coupons/validate/', {'code': 'ten'}, format='json')
    assert ok.status_code == 200
    assert ok.json()['discount_type'] == 'fixed'

    bad = api_client.post('/api/coupons/validate/', {'code': 'NOPE'}, format='json')
    assert bad.status_code == 404


def test_category_filter(api_client, make_product):
    from products.models import Category
    toys = Category.objects.create(name='Toys', slug='toys')
    make_product(name='Duck', category=toys)
    make_product(name='Cable')
    res = api_client.get('/api/products/?category=toys')
    assert [p['name'] for p in res.json()] == ['Duck']


def test_inactive_products_hidden(api_client, make_product):
    make_product(name='Ghost', is_active=False)
    res = api_client.get('/api/products/')
    assert res.json() == []


def test_review_updates_product_aggregates(api_client, make_product):
    product = make_product()
    for rating in (5, 4):
        res = api_client.post('/api/reviews/', {
            'product': product.id, 'author_name': 'Tester', 'rating': rating,
        }, format='json')
        assert res.status_code == 201

    body = api_client.get(f'/api/products/{product.slug}/').json()
    assert body['review_count'] == 2
    assert body['avg_rating'] == 4.5


def test_review_rating_bounds(api_client, make_product):
    product = make_product()
    res = api_client.post('/api/reviews/', {
        'product': product.id, 'author_name': 'Tester', 'rating': 6,
    }, format='json')
    assert res.status_code == 400
