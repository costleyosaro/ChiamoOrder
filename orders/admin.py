# orders/admin.py
from django.contrib import admin
from django.contrib import messages
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
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin for viewing and managing orders with role-based permissions.
    
    Roles:
    - InvoicerAdmin: Can only change status from 'confirmed' to 'processing'
    - LogisticsAdmin: Can change status from 'processing' onwards
    - SuperUser: Full access
    """

    list_display = ("order_id", "id", "user", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_id", "user__business_name", "user__email")
    ordering = ("-created_at",)
    inlines = [OrderItemInline]

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on user role."""
        user = request.user
        
        # Superusers can edit most things
        if user.is_superuser:
            return ["order_id", "created_at"]
        
        # Get user's groups
        user_groups = [g.name for g in user.groups.all()]
        
        # Base readonly fields for all staff
        readonly = ["order_id", "user", "total", "created_at"]
        
        # FinanceAdmin - readonly everything
        if 'FinanceAdmin' in user_groups:
            readonly.append("status")
        
        return readonly

    # --- Permission Control ---
    def has_module_permission(self, request):
        """Can user see Orders in admin sidebar?"""
        if request.user.is_superuser:
            return True
        return request.user.has_perm("orders.view_order")

    def has_view_permission(self, request, obj=None):
        """Can user view orders?"""
        if request.user.is_superuser:
            return True
        return request.user.has_perm("orders.view_order")

    def has_change_permission(self, request, obj=None):
        """Can user change orders?"""
        if request.user.is_superuser:
            return True
        
        user_groups = [g.name for g in request.user.groups.all()]
        
        # These roles can change orders
        allowed_roles = ['InvoicerAdmin', 'LogisticsAdmin', 'SupportAdmin']
        if any(role in user_groups for role in allowed_roles):
            return True
        
        return request.user.has_perm("orders.change_order")

    def has_add_permission(self, request):
        """Can user add new orders? (Usually no - orders come from frontend)"""
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        """Can user delete orders? (Only superusers)"""
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        """
        Validate status changes based on user role.
        
        Rules:
        - InvoicerAdmin: Can ONLY change 'confirmed' → 'processing'
        - LogisticsAdmin: Can change 'processing' → 'shipped' → 'out_for_delivery' → 'delivered'
        - LogisticsAdmin: CANNOT change 'confirmed' orders (must wait for invoicer)
        - SuperUser: Can change anything
        """
        if not change:
            super().save_model(request, obj, form, change)
            return
        
        if 'status' not in form.changed_data:
            super().save_model(request, obj, form, change)
            return
        
        user = request.user
        
        # Superusers bypass all restrictions
        if user.is_superuser:
            super().save_model(request, obj, form, change)
            return
        
        user_groups = [g.name for g in user.groups.all()]
        
        # Get old and new status
        try:
            old_order = Order.objects.get(pk=obj.pk)
            old_status = (old_order.status or 'confirmed').lower().strip()
        except Order.DoesNotExist:
            old_status = 'confirmed'
        
        new_status = (obj.status or 'confirmed').lower().strip()
        
        # Normalize status values
        status_map = {
            'order confirmed': 'confirmed',
            'order_confirmed': 'confirmed',
            'pending': 'confirmed',
            'in transit': 'shipped',
            'in_transit': 'shipped',
            'out for delivery': 'out_for_delivery',
        }
        old_status = status_map.get(old_status, old_status)
        new_status = status_map.get(new_status, new_status)
        
        # ===== INVOICER ADMIN RULES =====
        if 'InvoicerAdmin' in user_groups:
            if old_status == 'confirmed' and new_status == 'processing':
                super().save_model(request, obj, form, change)
                messages.success(request, f"✅ Order status changed to 'Processing'")
                return
            else:
                messages.error(
                    request, 
                    f"❌ Invoicers can ONLY change status from 'Confirmed' to 'Processing'. "
                    f"Current status is '{old_status}'."
                )
                obj.status = old_order.status
                return
        
        # ===== LOGISTICS ADMIN RULES =====
        if 'LogisticsAdmin' in user_groups:
            if old_status == 'confirmed':
                messages.error(
                    request, 
                    f"❌ Cannot change 'Confirmed' orders. "
                    f"Wait for Invoicer to change it to 'Processing' first."
                )
                obj.status = old_order.status
                return
            
            valid_transitions = {
                'processing': ['shipped'],
                'shipped': ['out_for_delivery'],
                'out_for_delivery': ['delivered'],
            }
            
            allowed_next = valid_transitions.get(old_status, [])
            
            if new_status in allowed_next:
                super().save_model(request, obj, form, change)
                messages.success(request, f"✅ Order status changed to '{new_status.replace('_', ' ').title()}'")
                return
            else:
                allowed_str = ", ".join([s.replace('_', ' ').title() for s in allowed_next]) or "None"
                messages.error(
                    request, 
                    f"❌ Cannot change from '{old_status.replace('_', ' ').title()}' to "
                    f"'{new_status.replace('_', ' ').title()}'. "
                    f"Allowed next status: {allowed_str}"
                )
                obj.status = old_order.status
                return
        
        # ===== SUPPORT ADMIN RULES =====
        if 'SupportAdmin' in user_groups:
            super().save_model(request, obj, form, change)
            messages.success(request, f"✅ Order status changed by Support")
            return
        
        # ===== DEFAULT =====
        messages.error(request, "❌ You don't have permission to change order status.")
        obj.status = old_order.status


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price")
    list_filter = ("order__status",)
    search_fields = ("order__order_id", "product__name")

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


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
    search_fields = ("user__business_name", "title", "message")