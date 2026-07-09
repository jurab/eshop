"""Order history must survive product edits, deletions, and coupon changes."""
from decimal import Decimal

import pytest

from orders.models import Coupon
from tests.db.test_stock import place_order

pytestmark = pytest.mark.django_db


def test_order_item_snapshots_survive_product_edits(make_product, checkout_fields):
    product = make_product(name='Original', price='10.00', stock=5)
    order = place_order(checkout_fields, [(product, 1)])

    product.name = 'Renamed'
    product.price = Decimal('999.00')
    product.save()

    item = order.items.get()
    assert item.product_name == 'Original'
    assert item.price == Decimal('10.00')
    assert order.total == Decimal('10.00')


def test_order_survives_product_deletion(make_product, checkout_fields):
    product = make_product(name='Doomed', price='10.00', stock=5)
    order = place_order(checkout_fields, [(product, 2)])

    product.delete()

    item = order.items.get()
    assert item.product is None
    assert item.product_name == 'Doomed'
    assert item.line_total == Decimal('20.00')


def test_coupon_discount_snapshotted_on_order(make_product, checkout_fields):
    make_product(price='100.00', stock=5)
    product = make_product(name='Gadget', price='100.00', stock=5)
    Coupon.objects.create(code='TEN', discount_type=Coupon.DiscountType.PERCENT,
                          value=Decimal('10.00'))

    from orders.serializers import OrderCreateSerializer
    serializer = OrderCreateSerializer(data={
        **checkout_fields,
        'coupon_code': 'ten',  # case-insensitive lookup
        'items': [{'product': product.pk, 'quantity': 2}],
    })
    serializer.is_valid(raise_exception=True)
    order = serializer.save()

    assert order.subtotal == Decimal('200.00')
    assert order.discount_amount == Decimal('20.00')
    assert order.total == Decimal('180.00')

    # rewriting the coupon later must not touch the order
    coupon = Coupon.objects.get(code='TEN')
    coupon.value = Decimal('50.00')
    coupon.save()
    order.refresh_from_db()
    assert order.discount_amount == Decimal('20.00')


def test_invalid_coupon_rejected(make_product, checkout_fields):
    product = make_product(stock=5)
    from rest_framework import serializers as drf
    from orders.serializers import OrderCreateSerializer
    serializer = OrderCreateSerializer(data={
        **checkout_fields,
        'coupon_code': 'NO-SUCH-CODE',
        'items': [{'product': product.pk, 'quantity': 1}],
    })
    with pytest.raises(drf.ValidationError):
        serializer.is_valid(raise_exception=True)
