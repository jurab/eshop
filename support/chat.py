"""Customer-service chatbot: Claude Haiku with read-only shop tools.

The browser never talks to Anthropic directly — accounts for the API key
staying server-side. Tools are deliberately read-only: chat input is
untrusted, so nothing the model can call mutates state.
"""
import json

import anthropic
from anthropic import beta_tool
from django.conf import settings
from django.core.exceptions import ValidationError

from orders.models import Coupon, Order
from products.models import Product

MODEL = 'claude-haiku-4-5'
MAX_HISTORY_MESSAGES = 30
MAX_MESSAGE_CHARS = 4000

SYSTEM_PROMPT = """\
You are the customer service assistant for "eshop", a small online \
electronics accessories store (keyboards, mice, monitors, hubs and similar).

Store policies:
- Shipping: Czech Republic only, 3-5 business days, free over 1000 CZK.
- Returns: 30 days, unused and in original packaging.
- Payment: card via Stripe; orders can be cancelled while pending or paid.

Ground rules:
- Use the tools to answer questions about orders, products, stock and \
coupons. Never invent order details, prices or stock numbers.
- Order ids are UUIDs from the customer's order confirmation. If a guest \
asks about an order, ask for that id.
- Prices are in EUR (displayed as €).
- Only help with this shop. Politely decline unrelated requests.
- Be concise and friendly. Answer in the customer's language.
"""


def get_order_status(order_id: str) -> str:
    """Look up an order by its id (uuid) and return status, items, totals
    and payment details.

    Args:
        order_id: The order's uuid, e.g. from the order confirmation page.
    """
    try:
        order = Order.objects.prefetch_related('items').select_related(
            'payment').get(pk=order_id.strip())
    except (Order.DoesNotExist, ValidationError, ValueError):
        return json.dumps({'error': 'no order with that id'})
    payment = None
    if hasattr(order, 'payment'):
        payment = {'provider': order.payment.provider,
                   'amount': str(order.payment.amount)}
    return json.dumps({
        'status': order.status,
        'created': order.created_at.date().isoformat(),
        'items': [{'product': i.product_name, 'quantity': i.quantity,
                   'price': str(i.price)} for i in order.items.all()],
        'subtotal': str(order.subtotal),
        'discount': str(order.discount_amount),
        'total': str(order.total),
        'payment': payment,
    })


def search_products(query: str) -> str:
    """Search the product catalog by name or description; returns up to 5
    matches with price, stock and category.

    Args:
        query: Free-text search terms, e.g. "keyboard".
    """
    products = Product.objects.filter(
        is_active=True).filter(
        name__icontains=query.strip()) | Product.objects.filter(
        is_active=True, description__icontains=query.strip())
    results = [{
        'name': p.name,
        'price': str(p.price),
        'in_stock': p.stock,
        'category': p.category.name if p.category else None,
    } for p in products.select_related('category').distinct()[:5]]
    return json.dumps({'results': results} if results else
                      {'results': [], 'note': 'no matching products'})


def check_coupon(code: str) -> str:
    """Check whether a coupon code is currently valid and what discount
    it gives.

    Args:
        code: The coupon code, e.g. "SUMMER10".
    """
    coupon = Coupon.objects.filter(code__iexact=code.strip()).first()
    if coupon is None or not coupon.is_valid_now():
        return json.dumps({'valid': False})
    return json.dumps({'valid': True,
                       'discount_type': coupon.discount_type,
                       'value': str(coupon.value)})


def orders_summary_for(user) -> str:
    """The data behind the list_my_orders tool; separate for testability."""
    orders = user.orders.all()[:5]
    return json.dumps({'orders': [{
        'id': str(o.id),
        'status': o.status,
        'total': str(o.total),
        'created': o.created_at.date().isoformat(),
    } for o in orders]})


def build_tools(user):
    tools = [beta_tool(get_order_status), beta_tool(search_products),
             beta_tool(check_coupon)]
    if user is not None and user.is_authenticated:
        @beta_tool
        def list_my_orders() -> str:
            """List the customer's own recent orders with id, status and
            total. Only call this for the currently logged-in customer."""
            return orders_summary_for(user)
        tools.append(list_my_orders)
    return tools


def run_chat(history, message, user=None):
    """One chat turn: returns the assistant's reply text."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY,
                                 timeout=30.0)
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=build_tools(user),
        messages=history + [{'role': 'user', 'content': message}],
    )
    last = None
    for msg in runner:
        last = msg
    return ''.join(b.text for b in last.content if b.type == 'text')
