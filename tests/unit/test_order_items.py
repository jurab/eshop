from decimal import Decimal

from orders.models import OrderItem


def test_line_total_is_price_times_quantity():
    item = OrderItem(product_name='Widget', price=Decimal('129.90'), quantity=3)
    assert item.line_total == Decimal('389.70')


def test_line_total_single_unit():
    item = OrderItem(product_name='Widget', price=Decimal('4.20'), quantity=1)
    assert item.line_total == Decimal('4.20')
