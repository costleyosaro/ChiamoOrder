from django.db import models
from django.contrib.auth.models import User
from products.models import Product
from django.conf import settings




class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart of {self.user.business_name}"

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    def total_price(self):
        return self.product.price * self.quantity


import uuid
from django.db import models
from django.conf import settings
from datetime import datetime
from products.models import Product  # ✅ ensure this import is correct


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    SOURCE_CHOICES = [
        ("cart", "Cart"),
        ("smartlist", "Smart List"),
        ("manual", "Manual"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=40, unique=True, editable=False, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    progress = models.IntegerField(default=1)  # ✅ “Order Confirmed” step by default
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["-created_at"]  # ✅ newest orders appear first

    def save(self, *args, **kwargs):
        """
        ✅ Auto-generate a professional, unique Order ID once.
        Example: ORD-2025-A9F23Z7Q
        - Uses first letter of user's business name
        - Includes year + random short code
        - Guaranteed unique & doesn’t change
        """
        if not self.order_id:
            year = datetime.now().year
            first_letter = (
                self.user.business_name[0].upper()
                if hasattr(self.user, "business_name") and self.user.business_name
                else "X"
            )
            random_code = uuid.uuid4().hex[:7].upper()  # shorter unique code
            self.order_id = f"ORD-{year}-{first_letter}{random_code}"

        # ✅ Ensure progress starts at 1 when the order is newly created
        if self._state.adding and self.progress == 0:
            self.progress = 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} by {self.user.business_name or self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        product_name = self.product.name if self.product else "Deleted Product"
        return f"{self.quantity} × {product_name}"


# orders/models.py
from django.conf import settings
from django.db import models
from products.models import Product  # adjust path if needed

class SmartList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="smartlists")
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.email})"


class SmartListItem(models.Model):
    smartlist = models.ForeignKey(SmartList, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} × {self.product.name} in {self.smartlist.name}"


class SupportMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


# orders/models.py

# orders/models.py
from django.conf import settings
from django.db import models

class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(
        max_length=50,
        choices=[
            ("order", "Order"),
            ("payment", "Payment"),
            ("delivery", "Delivery"),
            ("support", "Support"),
            ("system", "System"),
            ("promo", "Promo"),
        ],
        default="system"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.title}"
