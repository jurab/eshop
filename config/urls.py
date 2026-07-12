from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import LoginView, LogoutView, MeView, RegisterView
from orders.views import (AddressViewSet, CouponValidateView, OrderViewSet,
                          StripeWebhookView)
from products.views import CategoryViewSet, ProductViewSet, ReviewViewSet

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('categories', CategoryViewSet)
router.register('reviews', ReviewViewSet, basename='review')
router.register('orders', OrderViewSet)
router.register('addresses', AddressViewSet, basename='address')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/coupons/validate/', CouponValidateView.as_view()),
    path('api/stripe/webhook/', StripeWebhookView.as_view()),
    path('api/auth/register/', RegisterView.as_view()),
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/logout/', LogoutView.as_view()),
    path('api/auth/me/', MeView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
