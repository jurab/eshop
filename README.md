# eshop

Django + DRF backend with a plain HTML/JS frontend.

Example project for the **Practical Use of AI** course.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
```

## Run

```sh
# backend (API + admin) on :8000
.venv/bin/python manage.py runserver 8000

# frontend on :3000
cd frontend && python3 -m http.server 3000
```

- API: http://127.0.0.1:8000/api/products/
- Admin: http://127.0.0.1:8000/admin/
- Frontend: http://127.0.0.1:3000/
