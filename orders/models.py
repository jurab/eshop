import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='addresses')
    label = models.CharField(max_length=50, default='home')
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='CZ')

    class Meta:
        verbose_name_plural = 'addresses'

    def __str__(self):
        return f'{self.label}: {self.street}, {self.city}'


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Percent'
        FIXED = 'fixed', 'Fixed amount'

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.code

    def is_valid_now(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True

    def discount_for(self, subtotal):
        if self.discount_type == self.DiscountType.PERCENT:
            discount = subtotal * self.value / Decimal('100')
        else:
            discount = self.value
        return min(discount, subtotal).quantize(Decimal('0.01'))


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        SHIPPED = 'shipped', 'Shipped'
        CANCELLED = 'cancelled', 'Cancelled'

    # UUID pk so guests can be handed an order URL that isn't enumerable
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='orders')
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING)

    email = models.EmailField()
    full_name = models.CharField(max_length=200)
    # shipping address is snapshotted, not FK'd — orders are history
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='CZ')

    coupon = models.ForeignKey(Coupon, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='orders')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                          default=Decimal('0'))
    total = models.DecimalField(max_digits=10, decimal_places=2)

    # open Stripe PaymentIntent, reused across pay attempts for this order
    payment_intent_id = models.CharField(max_length=64, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {self.id} ({self.status})'

    def cancel(self):
        """Cancel the order and return reserved stock to the shelf."""
        from products.models import Product
        for item in self.items.all():
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(
                    stock=F('stock') + item.quantity)
        self.status = self.Status.CANCELLED
        self.save(update_fields=['status', 'updated_at'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', null=True,
                                on_delete=models.SET_NULL, related_name='order_items')
    # snapshots: editing/deleting a Product must never rewrite order history
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.quantity}x {self.product_name}'

    @property
    def line_total(self):
        return self.price * self.quantity


class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE,
                                 related_name='payment')
    provider = models.CharField(max_length=50, default='fake')
    transaction_id = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.provider} payment for {self.order_id}'
