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


# orders/models.py (just the Order model - update this part)

import uuid
from datetime import datetime
from django.db import models
from django.conf import settings


class Order(models.Model):
    # ✅ UPDATED: Added 'out_for_delivery' status
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("out_for_delivery", "Out For Delivery"),  # ✅ NEW
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    SOURCE_CHOICES = [
        ("cart", "Cart"),
        ("smartlist", "Smart List"),
        ("manual", "Manual"),
    ]

    # ✅ Status to Progress mapping
    STATUS_TO_PROGRESS = {
        "pending": 1,
        "processing": 2,
        "shipped": 3,
        "out_for_delivery": 4,
        "delivered": 5,
        "cancelled": 0,
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=40, unique=True, editable=False, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    progress = models.IntegerField(default=1)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        """
        Auto-generate order ID and sync progress with status.
        """
        # Auto-generate a professional, unique Order ID
        if not self.order_id:
            year = datetime.now().year
            first_letter = (
                self.user.business_name[0].upper()
                if hasattr(self.user, "business_name") and self.user.business_name
                else "X"
            )
            random_code = uuid.uuid4().hex[:7].upper()
            self.order_id = f"ORD-{year}-{first_letter}{random_code}"

        # ✅ Auto-update progress based on status
        if self.status in self.STATUS_TO_PROGRESS:
            self.progress = self.STATUS_TO_PROGRESS[self.status]

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} by {getattr(self.user, 'business_name', None) or self.user.username}"
    
    @property
    def status_display_name(self):
        """Return human-readable status name."""
        return dict(self.STATUS_CHOICES).get(self.status, self.status)


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

from django.db import models
from django.conf import settings


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("order", "Order"),
        ("payment", "Payment"),
        ("delivery", "Delivery"),
        ("support", "Support"),
        ("system", "System"),
        ("promo", "Promo"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default="system",
    )
    # ✅ NEW: Optional link to an order
    order_id = models.CharField(max_length=100, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.title}"


