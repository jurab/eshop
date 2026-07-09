from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from orders.models import Coupon


def percent(value):
    return Coupon(code='P', discount_type=Coupon.DiscountType.PERCENT,
                  value=Decimal(value), is_active=True)


def fixed(value):
    return Coupon(code='F', discount_type=Coupon.DiscountType.FIXED,
                  value=Decimal(value), is_active=True)


def test_percent_discount():
    assert percent('10').discount_for(Decimal('100.00')) == Decimal('10.00')


def test_percent_discount_quantizes_to_cents():
    assert percent('10').discount_for(Decimal('309.70')) == Decimal('30.97')


def test_fixed_discount():
    assert fixed('5').discount_for(Decimal('20.00')) == Decimal('5.00')


def test_fixed_discount_capped_at_subtotal():
    assert fixed('50').discount_for(Decimal('20.00')) == Decimal('20.00')


def test_hundred_percent_discount_is_full_subtotal():
    assert percent('100').discount_for(Decimal('12.34')) == Decimal('12.34')


def test_active_coupon_without_window_is_valid():
    assert percent('10').is_valid_now() is True


def test_inactive_coupon_is_invalid():
    coupon = percent('10')
    coupon.is_active = False
    assert coupon.is_valid_now() is False


def test_expired_coupon_is_invalid():
    coupon = percent('10')
    coupon.valid_to = timezone.now() - timedelta(days=1)
    assert coupon.is_valid_now() is False


def test_not_yet_started_coupon_is_invalid():
    coupon = percent('10')
    coupon.valid_from = timezone.now() + timedelta(days=1)
    assert coupon.is_valid_now() is False


def test_coupon_inside_window_is_valid():
    coupon = percent('10')
    coupon.valid_from = timezone.now() - timedelta(days=1)
    coupon.valid_to = timezone.now() + timedelta(days=1)
    assert coupon.is_valid_now() is True
