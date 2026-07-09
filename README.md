# eshop

Django + DRF backend with a plain HTML/JS frontend.

Example project for the **Practical Use of AI** course.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The repo includes `db.sqlite3` with sample data and a superuser
(`admin` / `admin`), so no migrate/createsuperuser needed to get started.

## Run

```sh
# backend (API + admin) on :8000
.venv/bin/python manage.py runserver 8000

# frontend on :3000
cd frontend && python3 -m http.server 3000
```

- API: http://127.0.0.1:8000/api/
- Admin: http://127.0.0.1:8000/admin/
- Frontend: http://127.0.0.1:3000/

## Models

| App | Model | Notes |
|---|---|---|
| products | Category | flat, FK'd from Product |
| products | Product | price as Decimal, stock, is_active |
| products | ProductImage | one-to-many gallery, Pillow-backed |
| products | Review | 1–5 rating, aggregated onto Product |
| orders | Order | UUID pk, status machine, address + totals snapshotted |
| orders | OrderItem | **snapshots** product name & price — orders are history |
| orders | Coupon | percent or fixed, validity window |
| orders | Payment | fake always-succeeds provider |
| orders | Address | saved addresses for registered users |

Stock is reserved at order creation with an atomic conditional update
(`filter(stock__gte=qty).update(stock=F('stock') - qty)`) — no
read-modify-write race. Cancelling restores stock.

The cart lives in the frontend's localStorage; checkout posts the whole
thing to `POST /api/orders/`.

## API

| Endpoint | Notes |
|---|---|
| `GET /api/products/` | `?category=<slug>` filter, includes images & rating aggregates |
| `GET /api/products/<slug>/` | |
| `GET /api/categories/` | |
| `GET/POST /api/reviews/` | `?product=<id>` filter |
| `POST /api/orders/` | guest checkout: items, address, optional `coupon_code` |
| `GET /api/orders/<uuid>/` | |
| `POST /api/orders/<uuid>/pay/` | fake payment, pending → paid |
| `POST /api/orders/<uuid>/cancel/` | restores stock, → cancelled |
| `POST /api/coupons/validate/` | `{code}` → coupon details or 404 |

Seeded coupons to play with: `WELCOME10` (10 % off), `FLAT5` (5 € off),
`EXPIRED10` (deliberately expired).

## Frontend

Zero-build vanilla JS with hash routing: catalog with category filter,
product detail with reviews, localStorage cart, coupon + checkout form,
and an order page with pay/cancel actions.
