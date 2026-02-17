from rest_framework import serializers
from .models import Cart, CartItem, Order, OrderItem
from products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "price", "image"]


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "total_price"]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "user", "items", "total_price"]


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    order_id = serializers.CharField(read_only=True)
    source = serializers.CharField(read_only=True)
    progress = serializers.IntegerField(read_only=False)

    class Meta:
        model = Order
        fields = ["id", "order_id", "user", "status", "progress", "total", "source", "created_at", "items"]
        read_only_fields = ["order_id", "created_at", "items", "progress", "source"]


# orders/serializers.py
from rest_framework import serializers
from .models import SmartList, SmartListItem
from products.models import Product  # adjust if your product model is elsewhere


# --- Product Serializer (lightweight) ---
class ProductMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "price", "image"]


# --- SmartList Item Serializer ---
class SmartListItemSerializer(serializers.ModelSerializer):
    # Embed full product details
    product = ProductMiniSerializer(read_only=True)

    class Meta:
        model = SmartListItem
        fields = ["id", "product", "quantity"]


# --- SmartList Serializer ---
class SmartListSerializer(serializers.ModelSerializer):
    items = SmartListItemSerializer(many=True, read_only=True)

    class Meta:
        model = SmartList
        fields = ["id", "name", "created_at", "items"]

from rest_framework import serializers
from .models import SupportMessage

class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = '__all__'


# orders/serializers.py
from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "message", "is_read", "created_at"]
