import uuid

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Coupon, Order, Payment
from .serializers import (CouponCheckSerializer, OrderCreateSerializer,
                          OrderSerializer)


class OrderViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    queryset = Order.objects.prefetch_related('items').select_related(
        'coupon', 'payment')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({'detail': f'cannot pay a {order.status} order'},
                            status=status.HTTP_400_BAD_REQUEST)
        # fake provider: always succeeds
        Payment.objects.create(order=order, amount=order.total,
                               transaction_id=uuid.uuid4().hex)
        order.status = Order.Status.PAID
        order.save(update_fields=['status', 'updated_at'])
        return Response(OrderSerializer(order, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status not in (Order.Status.PENDING, Order.Status.PAID):
            return Response({'detail': f'cannot cancel a {order.status} order'},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            order.cancel()
        return Response(OrderSerializer(order, context={'request': request}).data)


class CouponValidateView(APIView):
    """POST {code} -> coupon details if currently valid, 404 otherwise."""

    def post(self, request):
        code = (request.data.get('code') or '').strip()
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if coupon is None or not coupon.is_valid_now():
            return Response({'detail': 'invalid or expired coupon'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(CouponCheckSerializer(coupon).data)
