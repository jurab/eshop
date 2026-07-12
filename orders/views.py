import uuid

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import stripe_gateway
from .models import Address, Coupon, Order, Payment
from .serializers import (AddressSerializer, CouponCheckSerializer,
                          OrderCreateSerializer, OrderSerializer)


def _mark_paid(order, provider, transaction_id):
    """Idempotently record the payment and flip the order to paid."""
    with transaction.atomic():
        Payment.objects.get_or_create(order=order, defaults={
            'provider': provider,
            'transaction_id': transaction_id,
            'amount': order.total,
        })
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.PAID
            order.save(update_fields=['status', 'updated_at'])


class OrderViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                   mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Order.objects.prefetch_related('items').select_related(
        'coupon', 'payment')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer

    def get_permissions(self):
        # guests may create and view-by-uuid; the list is yours alone
        if self.action == 'list':
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            return qs.filter(user=self.request.user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({'detail': f'cannot pay a {order.status} order'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not settings.STRIPE_SECRET_KEY:
            # fake provider: always succeeds instantly
            _mark_paid(order, 'fake', uuid.uuid4().hex)
            return Response(OrderSerializer(order,
                                            context={'request': request}).data)

        intent = stripe_gateway.payment_intent_for(order)
        return Response({
            'provider': 'stripe',
            'client_secret': intent.client_secret,
            'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        })

    @action(detail=True, methods=['post'])
    def confirm_payment(self, request, pk=None):
        """Sync fallback to the webhook: verify the intent server-side."""
        order = self.get_object()
        if order.status == Order.Status.PAID:
            return Response(OrderSerializer(order,
                                            context={'request': request}).data)
        if order.status != Order.Status.PENDING or not order.payment_intent_id:
            return Response({'detail': 'nothing to confirm'},
                            status=status.HTTP_400_BAD_REQUEST)
        intent = stripe_gateway.retrieve_intent(order.payment_intent_id)
        if intent.status != 'succeeded':
            return Response({'detail': f'payment not completed ({intent.status})'},
                            status=status.HTTP_400_BAD_REQUEST)
        _mark_paid(order, 'stripe', intent.id)
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


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class StripeWebhookView(APIView):
    """Stripe calls this; signature verification is the only auth."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def post(self, request):
        if not settings.STRIPE_WEBHOOK_SECRET:
            return Response({'detail': 'webhook secret not configured'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            event = stripe.Webhook.construct_event(
                request.body,
                request.headers.get('Stripe-Signature', ''),
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return Response({'detail': 'invalid signature'},
                            status=status.HTTP_400_BAD_REQUEST)

        if event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            order_id = (intent.get('metadata') or {}).get('order_id')
            try:
                order = Order.objects.filter(pk=order_id).first()
            except (ValidationError, ValueError):
                order = None  # metadata missing or not one of our orders
            if order is not None:
                _mark_paid(order, 'stripe', intent['id'])
        return Response({'received': True})


class CouponValidateView(APIView):
    """POST {code} -> coupon details if currently valid, 404 otherwise."""

    def post(self, request):
        code = (request.data.get('code') or '').strip()
        coupon = Coupon.objects.filter(code__iexact=code).first()
        if coupon is None or not coupon.is_valid_now():
            return Response({'detail': 'invalid or expired coupon'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(CouponCheckSerializer(coupon).data)
