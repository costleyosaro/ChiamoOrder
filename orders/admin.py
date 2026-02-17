from django.contrib import admin
from .models import (
    Cart, CartItem, Order, OrderItem,
    SmartList, SmartListItem,
    SupportMessage, Notification
)

# ------------------------------
# Cart & CartItem
# ------------------------------
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "total_price")
    inlines = [CartItemInline]


# ------------------------------
# Order & OrderItem
# ------------------------------
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin for viewing and managing orders."""

    list_display = ("id", "user", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username",)
    inlines = [OrderItemInline]

    # --- Permission Control ---
    def has_module_permission(self, request):
        return request.user.has_perm("orders.view_order")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("orders.view_order")

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("orders.change_order")

    def has_add_permission(self, request):
        return request.user.has_perm("orders.add_order")

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm("orders.delete_order")


# ------------------------------
# SmartList & SmartListItem
# ------------------------------
class SmartListItemInline(admin.TabularInline):
    model = SmartListItem
    extra = 1


@admin.register(SmartList)
class SmartListAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "created_at")
    list_filter = ("user", "created_at")
    inlines = [SmartListItemInline]


@admin.register(SmartListItem)
class SmartListItemAdmin(admin.ModelAdmin):
    list_display = ("id", "smartlist", "product", "quantity")
    list_filter = ("smartlist", "product")


# ------------------------------
# SupportMessage
# ------------------------------
@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "subject", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_filter = ("created_at",)
    ordering = ("-created_at",)


# ------------------------------
# Notification
# ------------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "type", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")
