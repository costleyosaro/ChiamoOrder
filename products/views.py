# shop/views.py
from rest_framework import viewsets
from rest_framework.response import Response
from django.core.cache import cache
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    """
    Product ViewSet with Redis caching to improve scalability and performance.
    """
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer

    def list(self, request, *args, **kwargs):
        """
        Override the default list() to serve cached responses for 10 minutes.
        """
        cache_key = "product_list"
        cached_data = cache.get(cache_key)

        if cached_data:
            print("🟢 Products served from Redis cache")
            return Response(cached_data)

        # Fetch from DB if cache is empty
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        cache.set(cache_key, serializer.data, timeout=60 * 10)  # 10 minutes
        print("🔵 Products cached in Redis")
        return Response(serializer.data)

    def perform_create(self, serializer):
        """
        On create, clear the product cache to avoid stale data.
        """
        product = serializer.save()
        cache.delete("product_list")
        print("🟠 Product cache cleared (new product added)")
        return product

    def perform_update(self, serializer):
        """
        On update, also clear cache.
        """
        product = serializer.save()
        cache.delete("product_list")
        print("🟠 Product cache cleared (product updated)")
        return product

    def perform_destroy(self, instance):
        """
        On delete, clear cache again.
        """
        instance.delete()
        cache.delete("product_list")
        print("🟠 Product cache cleared (product deleted)")


class CategoryViewSet(viewsets.ModelViewSet):
    """
    Category ViewSet with Redis caching.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def list(self, request, *args, **kwargs):
        cache_key = "category_list"
        cached_data = cache.get(cache_key)

        if cached_data:
            print("🟢 Categories served from Redis cache")
            return Response(cached_data)

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        cache.set(cache_key, serializer.data, timeout=60 * 10)
        print("🔵 Categories cached in Redis")
        return Response(serializer.data)

    def perform_create(self, serializer):
        category = serializer.save()
        cache.delete("category_list")
        print("🟠 Category cache cleared (new category added)")
        return category

    def perform_update(self, serializer):
        category = serializer.save()
        cache.delete("category_list")
        print("🟠 Category cache cleared (category updated)")
        return category

    def perform_destroy(self, instance):
        instance.delete()
        cache.delete("category_list")
        print("🟠 Category cache cleared (category deleted)")
