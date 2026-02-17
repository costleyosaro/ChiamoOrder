from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Enhanced UserAdmin:
    - Includes your original field layout and filters
    - Adds permission-based access control (view/change/add/delete)
    """

    # Fields to display in the admin list
    list_display = ("id", "business_name", "email", "phone", "has_pin", "timestamp")
    list_filter = ("has_pin", "timestamp")
    search_fields = ("business_name", "email", "phone")
    ordering = ("-timestamp",)

    # Fields shown in the edit form
    fieldsets = (
        (None, {"fields": ("business_name", "password")}),
        ("Personal Info", {
            "fields": ("email", "phone", "location", "latitude", "longitude", "shop_photo_url")
        }),
        ("Security", {"fields": ("transaction_pin", "has_pin")}),
        ("QR Code", {"fields": ("qr_code",)}),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
    )

    # Fields shown when creating a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("business_name", "email", "password1", "password2"),
        }),
    )

    filter_horizontal = ("groups", "user_permissions")

    # --- Permission Control ---
    def has_module_permission(self, request):
        """Can this user see the 'Customers' section in admin?"""
        return request.user.has_perm("customers.view_user")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("customers.view_user")

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("customers.change_user")

    def has_add_permission(self, request):
        return request.user.has_perm("customers.add_user")

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm("customers.delete_user")


# ------------------------------
# Address Admin (unchanged)
# ------------------------------
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin configuration for managing user addresses."""

    list_display = (
        'id', 'user', 'street', 'city', 'state',
        'latitude', 'longitude', 'is_default', 'created_at',
    )
    list_filter = ('state', 'is_default', 'created_at')
    search_fields = ('street', 'city', 'state', 'user__business_name', 'user__email')
    ordering = ('-created_at',)
    readonly_fields = ('latitude', 'longitude', 'created_at', 'updated_at')

    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Address Details', {'fields': ('street', 'city', 'state')}),
        ('Geolocation', {'fields': ('latitude', 'longitude')}),
        ('Settings', {'fields': ('is_default',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
