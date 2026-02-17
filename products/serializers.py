# products/serializers.py
from rest_framework import serializers
from django.conf import settings
from .models import Product, Category
import os

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)  # nested
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True
    )
    image_url = serializers.SerializerMethodField()  # ✅ new field

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "name",
            "price",
            "category",
            "category_id",
            "image",
            "image_url",   # ✅ add image_url here
            "stock",
            "rating",
            "num_reviews",
            "is_new",
            "is_promo",
            "flash_sale",
            "created_at",
        ]

    def get_image_url(self, obj):
        """
        Returns a correct URL for the product image.
        Priority:
          1. If using Django's MEDIA system → return full MEDIA URL
          2. If images are actually inside React /public/assets → return frontend path
        """
        request = self.context.get("request")

        if obj.image:  # case where Product.image is a File/ImageField
            # Return absolute URL via MEDIA_URL
            return request.build_absolute_uri(obj.image.url)

        # If you're storing static images in React's public/assets
        # we can safely map category + filename
        if obj.category and obj.name:
            filename = os.path.basename(str(obj.image)) if obj.image else ""
            return f"/assets/images/categories/{obj.category.name.lower()}/{filename}"

        return None
