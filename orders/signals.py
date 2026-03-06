# orders/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, Notification


@receiver(post_save, sender=Order)
def notify_on_order_create(sender, instance, created, **kwargs):
    """
    Automatically create a notification when a new order is created.
    This ensures notifications are ALWAYS created even if frontend fails.
    """
    if created:
        Notification.objects.create(
            user=instance.user,
            title="Order Placed Successfully! 🎉",
            message=(
                f"Your order #{instance.id} has been placed "
                f"and is being processed."
            ),
            type="order",
            order_id=str(instance.id),
        )
    else:
        # Handle status changes
        status_messages = {
            "confirmed": {
                "title": "Order Confirmed! ✅",
                "message": f"Your order #{instance.id} has been confirmed.",
                "type": "order",
            },
            "shipped": {
                "title": "Order Shipped! 🚚",
                "message": f"Your order #{instance.id} is on the way!",
                "type": "delivery",
            },
            "delivered": {
                "title": "Order Delivered! 📦",
                "message": f"Your order #{instance.id} has been delivered.",
                "type": "delivery",
            },
        }

        status_key = getattr(instance, "status", "").lower()
        if status_key in status_messages:
            data = status_messages[status_key]

            # Avoid duplicate notifications
            exists = Notification.objects.filter(
                user=instance.user,
                order_id=str(instance.id),
                title=data["title"],
            ).exists()

            if not exists:
                Notification.objects.create(
                    user=instance.user,
                    title=data["title"],
                    message=data["message"],
                    type=data["type"],
                    order_id=str(instance.id),
                )