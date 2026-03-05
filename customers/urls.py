from django.urls import path
from . import views
from .views import (
    ThemeUpdateView, LoginView, SetPinView,
    ValidatePinView, ResetPinView, ForgotPasswordView, ProfileView
)

urlpatterns = [
    # ✅ Function-based register (nuclear fix)
    path("register/", views.register_view, name="register"),
    
    path("validate-pin/", ValidatePinView.as_view(), name="validate-pin"),
    path("set-pin/", SetPinView.as_view(), name="set-pin"),
    path("reset-pin/", ResetPinView.as_view(), name="reset-pin"),
    path("login/", LoginView.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", views.reset_password, name="reset-password"),
    path("reset-password/confirm/", views.reset_password_confirm, name="reset-password-confirm"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("theme/", ThemeUpdateView.as_view(), name="theme-update"),
    path('has-transaction-pin/<int:pk>/', views.HasTransactionPinView.as_view(), name='has-transaction-pin'),
    path('addresses/', views.addresses, name='addresses'),
    path('addresses/<int:pk>/', views.address_detail, name='address_detail'),
]