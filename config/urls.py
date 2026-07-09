from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from orders.views import CouponValidateView, OrderViewSet
from products.views import CategoryViewSet, ProductViewSet, ReviewViewSet

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('categories', CategoryViewSet)
router.register('reviews', ReviewViewSet, basename='review')
router.register('orders', OrderViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/coupons/validate/', CouponValidateView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
