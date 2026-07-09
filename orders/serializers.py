from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from products.models import Product

from .models import Address, Coupon, Order, OrderItem, Payment


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'label', 'street', 'city', 'zip_code', 'country']


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2,
                                          read_only=True)

    class Meta:
        model = OrderItem
        fields = ['product', 'product_name', 'price', 'quantity', 'line_total']
        read_only_fields = ['product_name', 'price']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['provider', 'transaction_id', 'amount', 'created_at']


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True))
    quantity = serializers.IntegerField(min_value=1)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'status', 'email', 'full_name', 'street', 'city',
                  'zip_code', 'country', 'items', 'coupon_code', 'subtotal',
                  'discount_amount', 'total', 'payment', 'created_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemInputSerializer(many=True, write_only=True)
    coupon_code = serializers.CharField(write_only=True, required=False,
                                        allow_blank=True)

    class Meta:
        model = Order
        fields = ['email', 'full_name', 'street', 'city', 'zip_code',
                  'country', 'items', 'coupon_code']

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('order must contain at least one item')
        if len({i['product'].pk for i in items}) != len(items):
            raise serializers.ValidationError('duplicate products in order')
        return items

    def validate(self, attrs):
        code = attrs.pop('coupon_code', '').strip()
        attrs['coupon'] = None
        if code:
            coupon = Coupon.objects.filter(code__iexact=code).first()
            if coupon is None or not coupon.is_valid_now():
                raise serializers.ValidationError(
                    {'coupon_code': 'invalid or expired coupon'})
            attrs['coupon'] = coupon
        return attrs

    def create(self, validated_data):
        items = validated_data.pop('items')
        coupon = validated_data.pop('coupon')

        with transaction.atomic():
            # atomic check-and-decrement: the filtered update either reserves
            # stock or matches zero rows — no read-modify-write race
            for item in items:
                product = item['product']
                reserved = Product.objects.filter(
                    pk=product.pk, stock__gte=item['quantity'],
                ).update(stock=F('stock') - item['quantity'])
                if not reserved:
                    raise serializers.ValidationError(
                        {'items': f'insufficient stock for {product.name}'})

            subtotal = sum((i['product'].price * i['quantity'] for i in items))
            discount = coupon.discount_for(subtotal) if coupon else 0

            order = Order.objects.create(
                coupon=coupon,
                subtotal=subtotal,
                discount_amount=discount,
                total=subtotal - discount,
                **validated_data,
            )
            OrderItem.objects.bulk_create([
                OrderItem(order=order,
                          product=i['product'],
                          product_name=i['product'].name,
                          price=i['product'].price,
                          quantity=i['quantity'])
                for i in items
            ])
        return order

    def to_representation(self, instance):
        return OrderSerializer(instance, context=self.context).data


class CouponCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ['code', 'discount_type', 'value']
