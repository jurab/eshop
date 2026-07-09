from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from products.models import Product


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_product(db):
    def _make(name='Widget', price='10.00', stock=5, **kwargs):
        slug = kwargs.pop('slug', name.lower().replace(' ', '-'))
        return Product.objects.create(name=name, slug=slug, price=Decimal(price),
                                      stock=stock, **kwargs)
    return _make


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        email='user@example.com', password='sturdy-password-1')


@pytest.fixture
def auth_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


@pytest.fixture
def checkout_fields():
    return {
        'email': 'buyer@example.com',
        'full_name': 'Test Buyer',
        'street': 'Kobližná 1',
        'city': 'Brno',
        'zip_code': '60200',
        'country': 'CZ',
    }
