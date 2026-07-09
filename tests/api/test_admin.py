"""Admin smoke tests: every registered admin page must render.

Parametrized over admin.site._registry, so newly registered models are
covered automatically. Sample rows make changelists exercise list_display,
custom columns, and __str__ — the usual admin breakage points.
"""
from decimal import Decimal

import pytest
from django.contrib import admin
from django.urls import reverse

pytestmark = pytest.mark.django_db

REGISTERED = sorted(
    (model._meta.app_label, model._meta.model_name)
    for model in admin.site._registry
)


@pytest.fixture
def sample_rows(make_product, admin_user):
    """One row of everything, so changelists render actual data."""
    from rest_framework.authtoken.models import Token

    from orders.models import Address, Coupon, Order, OrderItem, Payment
    from products.models import Category, Review

    category = Category.objects.create(name='Toys', slug='toys')
    product = make_product(category=category)
    Review.objects.create(product=product, author_name='Tester', rating=5)
    Coupon.objects.create(code='TEN', discount_type=Coupon.DiscountType.PERCENT,
                          value=Decimal('10.00'))
    Address.objects.create(user=admin_user, label='home', street='S 1',
                           city='Brno', zip_code='60200')
    order = Order.objects.create(
        email='buyer@example.com', full_name='Test Buyer', street='S 1',
        city='Brno', zip_code='60200', subtotal=Decimal('10.00'),
        total=Decimal('10.00'))
    OrderItem.objects.create(order=order, product=product,
                             product_name=product.name, price=product.price,
                             quantity=1)
    Payment.objects.create(order=order, amount=order.total, transaction_id='tx')
    Token.objects.get_or_create(user=admin_user)


def test_admin_login_page_opens(client):
    assert client.get(reverse('admin:login')).status_code == 200


def test_admin_index_opens(admin_client):
    assert admin_client.get(reverse('admin:index')).status_code == 200


@pytest.mark.parametrize('app_label,model_name', REGISTERED)
def test_changelist_opens(admin_client, sample_rows, app_label, model_name):
    url = reverse(f'admin:{app_label}_{model_name}_changelist')
    assert admin_client.get(url).status_code == 200


@pytest.mark.parametrize('app_label,model_name', REGISTERED)
def test_add_page_opens(admin_client, app_label, model_name):
    url = reverse(f'admin:{app_label}_{model_name}_add')
    assert admin_client.get(url).status_code == 200
