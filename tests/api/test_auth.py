"""Auth endpoints and per-user data isolation."""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


def client_for(email):
    user = User.objects.create_user(email=email, password='sturdy-password-1')
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


def test_register_returns_token(api_client):
    res = api_client.post('/api/auth/register/', {
        'email': 'new@example.com', 'password': 'correct-horse-battery',
    }, format='json')
    assert res.status_code == 201
    assert 'token' in res.json()
    assert res.json()['user']['email'] == 'new@example.com'


def test_register_rejects_weak_password(api_client):
    res = api_client.post('/api/auth/register/', {
        'email': 'new@example.com', 'password': '1234',
    }, format='json')
    assert res.status_code == 400
    assert 'password' in res.json()


def test_register_rejects_duplicate_email(api_client, user):
    res = api_client.post('/api/auth/register/', {
        'email': user.email, 'password': 'correct-horse-battery',
    }, format='json')
    assert res.status_code == 400


def test_login_roundtrip(api_client, user):
    res = api_client.post('/api/auth/login/', {
        'email': user.email, 'password': 'sturdy-password-1',
    }, format='json')
    assert res.status_code == 200
    token = res.json()['token']

    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    assert api_client.get('/api/auth/me/').json()['email'] == user.email


def test_login_wrong_password(api_client, user):
    res = api_client.post('/api/auth/login/', {
        'email': user.email, 'password': 'wrong',
    }, format='json')
    assert res.status_code == 400


def test_me_requires_auth(api_client):
    assert api_client.get('/api/auth/me/').status_code == 401


def test_logout_kills_token(auth_client):
    assert auth_client.post('/api/auth/logout/').status_code == 204
    assert auth_client.get('/api/auth/me/').status_code == 401


def test_order_list_requires_auth(api_client):
    assert api_client.get('/api/orders/').status_code == 401


def test_order_list_shows_only_own_orders(make_product, checkout_fields):
    product = make_product(stock=50)
    alice = client_for('alice@example.com')
    bob = client_for('bob@example.com')
    guest = APIClient()

    payload = {**checkout_fields, 'items': [{'product': product.id, 'quantity': 1}]}
    alice.post('/api/orders/', payload, format='json')
    bob.post('/api/orders/', payload, format='json')
    guest.post('/api/orders/', payload, format='json')

    assert len(alice.get('/api/orders/').json()) == 1
    assert len(bob.get('/api/orders/').json()) == 1


def test_addresses_scoped_to_owner(db):
    alice = client_for('alice@example.com')
    bob = client_for('bob@example.com')

    address = {'label': 'home', 'street': 'S 1', 'city': 'C', 'zip_code': '1',
               'country': 'CZ'}
    created = alice.post('/api/addresses/', address, format='json')
    assert created.status_code == 201

    assert len(alice.get('/api/addresses/').json()) == 1
    assert bob.get('/api/addresses/').json() == []
    # bob cannot fetch or delete alice's address either
    assert bob.get(f"/api/addresses/{created.json()['id']}/").status_code == 404
    assert bob.delete(f"/api/addresses/{created.json()['id']}/").status_code == 404


def test_addresses_require_auth(api_client):
    assert api_client.get('/api/addresses/').status_code == 401


def test_authed_order_attaches_user(make_product, checkout_fields):
    product = make_product(stock=5)
    alice = client_for('alice@example.com')
    res = alice.post('/api/orders/', {
        **checkout_fields, 'items': [{'product': product.id, 'quantity': 1}],
    }, format='json')
    assert res.status_code == 201

    from orders.models import Order
    order = Order.objects.get(pk=res.json()['id'])
    assert order.user.email == 'alice@example.com'
