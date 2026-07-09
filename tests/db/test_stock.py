"""Stock reservation: the atomic check-and-decrement and its rollback paths."""
import pytest
from rest_framework import serializers

from orders.models import Order
from orders.serializers import OrderCreateSerializer

pytestmark = pytest.mark.django_db


def place_order(checkout_fields, items):
    serializer = OrderCreateSerializer(data={
        **checkout_fields,
        'items': [{'product': p.pk, 'quantity': q} for p, q in items],
    })
    serializer.is_valid(raise_exception=True)
    return serializer.save()


def test_order_reserves_stock(make_product, checkout_fields):
    product = make_product(stock=5)
    place_order(checkout_fields, [(product, 2)])
    product.refresh_from_db()
    assert product.stock == 3


def test_insufficient_stock_rejected(make_product, checkout_fields):
    product = make_product(stock=1)
    with pytest.raises(serializers.ValidationError):
        place_order(checkout_fields, [(product, 2)])
    product.refresh_from_db()
    assert product.stock == 1
    assert Order.objects.count() == 0


def test_out_of_stock_rejected(make_product, checkout_fields):
    product = make_product(stock=0)
    with pytest.raises(serializers.ValidationError):
        place_order(checkout_fields, [(product, 1)])


def test_failed_line_rolls_back_reserved_lines(make_product, checkout_fields):
    """If the second item overdraws, the first item's reservation must not leak."""
    plentiful = make_product(name='Plentiful', stock=10)
    scarce = make_product(name='Scarce', stock=1)
    with pytest.raises(serializers.ValidationError):
        place_order(checkout_fields, [(plentiful, 3), (scarce, 5)])
    plentiful.refresh_from_db()
    scarce.refresh_from_db()
    assert plentiful.stock == 10
    assert scarce.stock == 1
    assert Order.objects.count() == 0


def test_stock_never_goes_negative(make_product, checkout_fields):
    product = make_product(stock=1)
    place_order(checkout_fields, [(product, 1)])
    with pytest.raises(serializers.ValidationError):
        place_order(checkout_fields, [(product, 1)])
    product.refresh_from_db()
    assert product.stock == 0
    assert Order.objects.count() == 1


def test_cancel_restores_stock(make_product, checkout_fields):
    product = make_product(stock=5)
    order = place_order(checkout_fields, [(product, 4)])
    order.cancel()
    product.refresh_from_db()
    assert product.stock == 5
    assert order.status == Order.Status.CANCELLED
