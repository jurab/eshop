import pytest
from rest_framework import serializers

from orders.serializers import OrderCreateSerializer
from products.models import Product


def test_empty_items_rejected():
    with pytest.raises(serializers.ValidationError):
        OrderCreateSerializer().validate_items([])


def test_duplicate_products_rejected():
    items = [
        {'product': Product(pk=1), 'quantity': 1},
        {'product': Product(pk=1), 'quantity': 2},
    ]
    with pytest.raises(serializers.ValidationError):
        OrderCreateSerializer().validate_items(items)


def test_distinct_products_accepted():
    items = [
        {'product': Product(pk=1), 'quantity': 1},
        {'product': Product(pk=2), 'quantity': 2},
    ]
    assert OrderCreateSerializer().validate_items(items) == items
