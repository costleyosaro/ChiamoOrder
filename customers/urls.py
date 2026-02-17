from django.urls import path
from . import views
from .views import RegisterView, ThemeUpdateView, LoginView, SetPinView,ValidatePinView, ResetPinView, ForgotPasswordView,ProfileView
from rest_framework.views import APIView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("validate-pin/", ValidatePinView.as_view(), name="validate-pin"),
    path("set-pin/", SetPinView.as_view(), name="set-pin"),
    path("reset-pin/", ResetPinView.as_view(), name="reset-pin"),
    path("login/", LoginView.as_view(), name="login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("verify-otp/", views.verify_otp, name="verify-otp"),
    path("reset-password/", views.reset_password, name="reset-password"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("theme/", ThemeUpdateView.as_view(), name="theme-update"),
    path('has-transaction-pin/<int:pk>/', views.HasTransactionPinView.as_view(), name='has-transaction-pin'),
    path('addresses/', views.addresses, name='addresses'),
    path('addresses/<int:pk>/', views.address_detail, name='address_detail'),
    
]   

