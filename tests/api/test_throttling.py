"""Rate limiting: strict shared budget on auth endpoints, global anon limit."""
import pytest

pytestmark = pytest.mark.django_db

AUTH_LIMIT = 10   # 'auth' scope, shared by login + register
ANON_LIMIT = 60   # global anon rate


def login_attempt(client):
    return client.post('/api/auth/login/', {
        'email': 'whoever@example.com', 'password': 'wrong',
    }, format='json')


def test_login_throttled_after_limit(api_client):
    for _ in range(AUTH_LIMIT):
        assert login_attempt(api_client).status_code == 400
    res = login_attempt(api_client)
    assert res.status_code == 429
    assert 'Retry-After' in res.headers


def test_login_and_register_share_the_auth_budget(api_client):
    for _ in range(AUTH_LIMIT):
        login_attempt(api_client)
    res = api_client.post('/api/auth/register/', {
        'email': 'new@example.com', 'password': 'correct-horse-battery',
    }, format='json')
    assert res.status_code == 429


def test_successful_logins_count_against_the_budget(api_client, user):
    for _ in range(AUTH_LIMIT):
        res = api_client.post('/api/auth/login/', {
            'email': user.email, 'password': 'sturdy-password-1',
        }, format='json')
        assert res.status_code == 200
    res = login_attempt(api_client)
    assert res.status_code == 429


def test_anon_browsing_throttled_after_limit(api_client):
    for _ in range(ANON_LIMIT):
        assert api_client.get('/api/products/').status_code == 200
    assert api_client.get('/api/products/').status_code == 429


def test_authenticated_user_not_bound_by_anon_limit(auth_client):
    for _ in range(ANON_LIMIT + 1):
        assert auth_client.get('/api/products/').status_code == 200
