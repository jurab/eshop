from django.db.models import Avg, Count
from rest_framework import mixins, viewsets

from .models import Category, Product, Review
from .serializers import CategorySerializer, ProductSerializer, ReviewSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    lookup_field = 'slug'

    def get_queryset(self):
        qs = (Product.objects.filter(is_active=True)
              .select_related('category')
              .prefetch_related('images')
              .annotate(avg_rating=Avg('reviews__rating'),
                        review_count=Count('reviews')))
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)
        return qs


class ReviewViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    viewsets.GenericViewSet):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.all()
        product = self.request.query_params.get('product')
        if product:
            qs = qs.filter(product_id=product)
        return qs
