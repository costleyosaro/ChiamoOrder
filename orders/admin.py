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
    readonly_fields = ['product', 'quantity', 'price']
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
    - LogisticsAdmin: Can change status from 'processing' onwards (shipped, out_for_delivery, delivered)
    - SuperUser: Full access
    """

    list_display = ("order_id", "id", "user", "status", "total", "delivery_method", "created_at")
    list_filter = ("status", "delivery_method", "created_at")
    search_fields = ("order_id", "user__business_name", "user__email")
    list_editable = ("status",)  # Allow inline status editing
    ordering = ("-created_at",)
    inlines = [OrderItemInline]
    
    # Fields to show in detail view
    fieldsets = (
        ("Order Information", {
            "fields": ("order_id", "user", "status", "total")
        }),
        ("Delivery Information", {
            "fields": ("delivery_method", "delivery_address")
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make fields readonly based on user role."""
        user = request.user
        
        # Superusers can edit everything
        if user.is_superuser:
            return ["order_id", "created_at"]
        
        # Get user's groups
        user_groups = [g.name for g in user.groups.all()]
        
        # Base readonly fields for all staff
        readonly = ["order_id", "user", "total", "created_at"]
        
        # InvoicerAdmin - can only change status, everything else readonly
        if 'InvoicerAdmin' in user_groups:
            readonly.extend(["delivery_method", "delivery_address"])
            
        # LogisticsAdmin - can change status and view delivery info
        elif 'LogisticsAdmin' in user_groups:
            readonly.extend(["delivery_method"])  # Can view but not change delivery method
        
        # SupportAdmin - can change status
        elif 'SupportAdmin' in user_groups:
            readonly.extend(["delivery_method", "delivery_address"])
        
        # FinanceAdmin - readonly everything
        elif 'FinanceAdmin' in user_groups:
            readonly.extend(["status", "delivery_method", "delivery_address"])
        
        # Default - readonly
        else:
            readonly.extend(["status", "delivery_method", "delivery_address"])
        
        return readonly

    def get_list_editable(self, request):
        """Control inline editing based on role."""
        user = request.user
        
        if user.is_superuser:
            return ["status"]
        
        user_groups = [g.name for g in user.groups.all()]
        
        # Allow inline status editing for these roles
        if any(role in user_groups for role in ['InvoicerAdmin', 'LogisticsAdmin', 'SupportAdmin']):
            return ["status"]
        
        return []

    def get_changelist_instance(self, request):
        """Override to dynamically set list_editable."""
        self.list_editable = self.get_list_editable(request)
        return super().get_changelist_instance(request)

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
            # New order - just save
            super().save_model(request, obj, form, change)
            return
        
        # Check if status was changed
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
            old_status = old_order.status.lower().strip() if old_order.status else 'confirmed'
        except Order.DoesNotExist:
            old_status = 'confirmed'
        
        new_status = obj.status.lower().strip() if obj.status else 'confirmed'
        
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
            # Can ONLY change from 'confirmed' to 'processing'
            if old_status == 'confirmed' and new_status == 'processing':
                # This is allowed
                super().save_model(request, obj, form, change)
                messages.success(request, f"✅ Order status changed to 'Processing'")
                return
            else:
                # Not allowed
                messages.error(
                    request, 
                    f"❌ Invoicers can ONLY change status from 'Confirmed' to 'Processing'. "
                    f"Current status is '{old_status}'."
                )
                # Revert the status
                obj.status = old_order.status
                return
        
        # ===== LOGISTICS ADMIN RULES =====
        if 'LogisticsAdmin' in user_groups:
            # Cannot change 'confirmed' orders - must wait for invoicer
            if old_status == 'confirmed':
                messages.error(
                    request, 
                    f"❌ Cannot change 'Confirmed' orders. "
                    f"Wait for Invoicer to change it to 'Processing' first."
                )
                obj.status = old_order.status
                return
            
            # Define valid transitions for logistics
            valid_transitions = {
                'processing': ['shipped'],
                'shipped': ['out_for_delivery'],
                'out_for_delivery': ['delivered'],
            }
            
            allowed_next = valid_transitions.get(old_status, [])
            
            if new_status in allowed_next:
                # This is allowed
                super().save_model(request, obj, form, change)
                messages.success(request, f"✅ Order status changed to '{new_status.replace('_', ' ').title()}'")
                return
            else:
                # Not allowed
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
            # Support can make most changes but let's log it
            super().save_model(request, obj, form, change)
            messages.success(request, f"✅ Order status changed by Support")
            return
        
        # ===== DEFAULT - No special permissions =====
        messages.error(request, "❌ You don't have permission to change order status.")
        obj.status = old_order.status

    def get_queryset(self, request):
        """All staff can see all orders."""
        return super().get_queryset(request)
    
    class Media:
        css = {
            'all': ('admin/css/custom_order_admin.css',)
        }


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product", "quantity", "price")
    list_filter = ("order__status",)
    search_fields = ("order__order_id", "product__name")
    readonly_fields = ["order", "product", "quantity", "price"]

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