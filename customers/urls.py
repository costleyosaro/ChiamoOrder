# customers/urls.py

from django.urls import path
from . import views
from .views import (
    LoginView,
    ForgotPasswordView,
    ProfileView,
    ThemeUpdateView,
    HasTransactionPinView,
    SetPinView,
    ValidatePinView,
    ResetPinView,
)

urlpatterns = [
    # ✅ Auth (public)
    path("register/", views.register_view, name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", views.reset_password, name="reset-password"),
    path("reset-password/confirm/", views.reset_password_confirm, name="reset-password-confirm"),

    # ✅ PIN Management (authenticated)
    path("set-pin/", SetPinView.as_view(), name="set-pin"),
    path("validate-pin/", ValidatePinView.as_view(), name="validate-pin"),
    path("reset-pin/", ResetPinView.as_view(), name="reset-pin"),
    path("has-transaction-pin/<int:pk>/", HasTransactionPinView.as_view(), name="has-transaction-pin"),

    # ✅ Profile & Settings (authenticated)
    path("profile/", ProfileView.as_view(), name="profile"),
    path("theme/", ThemeUpdateView.as_view(), name="theme-update"),

    # ✅ Addresses (authenticated)
    path("addresses/", views.addresses, name="addresses"),
    path("addresses/<int:pk>/", views.address_detail, name="address-detail"),

    # ✅ Admin / Security
    path("pin-audit-logs/", views.get_pin_audit_logs, name="pin-audit-logs"),
    path("unlock-account/", views.unlock_user_account, name="unlock-account"),
    path("security-dashboard/", views.get_security_dashboard, name="security-dashboard"),

    # ✅ Health Check (public)
    path("health/", views.health_check, name="health-check"),
]