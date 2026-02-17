# your_app_name/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .validators import sanitize_input, validate_phone_number

User = get_user_model()


class SecureUserSerializer(serializers.ModelSerializer):
    """User serializer with input sanitization."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']
    
    def validate_first_name(self, value):
        return sanitize_input(value)
    
    def validate_last_name(self, value):
        return sanitize_input(value)
    
    def validate_email(self, value):
        # Normalize email
        return value.lower().strip()


class SecureProductSerializer(serializers.Serializer):
    """Product serializer with validation."""
    
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=5000, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    stock = serializers.IntegerField(min_value=0)
    
    def validate_name(self, value):
        return sanitize_input(value)
    
    def validate_description(self, value):
        if value:
            return sanitize_input(value, allow_html=True)
        return value
    
    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value


class SecureAddToCartSerializer(serializers.Serializer):
    """Add to cart with strict validation."""
    
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=100)
    
    def validate_quantity(self, value):
        if value > 100:
            raise serializers.ValidationError("Cannot add more than 100 items at once.")
        return value