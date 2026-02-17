from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate, get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.conf import settings

import requests
import os
import datetime

from .models import User
from .serializers import (
    UserSerializer,
    ResetPinSerializer,
    SetPinSerializer,
    ValidatePinSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    VerifyOtpSerializer,
    ProfileUpdateSerializer,
)

# ✅ User model reference
User = get_user_model()


# ==========================
# REGISTER VIEW
# ==========================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable JWT auth for registration

    def perform_create(self, serializer):
        user = serializer.save()

        # Send Welcome Email
        subject = "🎉 Welcome to ChiamoOrder!"
        context = {
            "user": user,
            "domain": "http://127.0.0.1:8000",
            "year": datetime.datetime.now().year,
        }

        html_message = render_to_string("emails/welcome_email.html", context)
        plain_message = strip_tags(html_message)

        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]

        try:
            email = EmailMultiAlternatives(
                subject, plain_message, from_email, recipient_list
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
            print(f"📩 Welcome email sent to {user.email}")
        except Exception as e:
            print("❌ Email sending failed:", e)

        # Send Welcome SMS (Termii)
        TERMII_API_KEY = os.getenv("TERMII_API_KEY")
        TERMII_BASE_URL = "https://api.ng.termii.com/api/sms/send"
        TERMII_SENDER_ID = os.getenv("TERMII_SENDER_ID", "ChiamoOrder")

        sms_payload = {
            "to": user.phone,
            "from": TERMII_SENDER_ID,
            "sms": f"Hi {user.name}, welcome to ChiamoOrder 🎉. "
                   f"Your business '{user.business_name}' has been registered successfully.",
            "type": "plain",
            "channel": "generic",
            "api_key": TERMII_API_KEY,
        }

        try:
            response = requests.post(TERMII_BASE_URL, json=sms_payload)
            print("📲 Termii SMS response:", response.json())
        except Exception as e:
            print("❌ SMS sending failed:", e)


# ==========================
# TRANSACTION PIN VIEWS
# ==========================
class HasTransactionPinView(APIView):
    def get(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            return Response({"has_pin": bool(user.transaction_pin)})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class SetPinView(APIView):
    def post(self, request):
        serializer = SetPinSerializer(data=request.data)
        if serializer.is_valid():
            customer_id = serializer.validated_data["customer_id"]
            pin = serializer.validated_data["pin"]

            try:
                customer = User.objects.get(id=customer_id)
                customer.set_transaction_pin(pin)
                return Response({"message": "PIN set successfully"}, status=200)
            except User.DoesNotExist:
                return Response({"error": "Customer not found"}, status=404)

        return Response(serializer.errors, status=400)


class ValidatePinView(APIView):
    def post(self, request):
        serializer = ValidatePinSerializer(data=request.data)
        if serializer.is_valid():
            customer_id = serializer.validated_data["customer_id"]
            pin = serializer.validated_data["pin"]

            try:
                customer = User.objects.get(id=customer_id)
                if customer.check_transaction_pin(pin):
                    return Response({"valid": True}, status=200)
                else:
                    return Response({"valid": False, "error": "Invalid PIN"}, status=400)
            except User.DoesNotExist:
                return Response({"error": "Customer not found"}, status=404)

        return Response(serializer.errors, status=400)


class ResetPinView(APIView):
    def post(self, request):
        serializer = ResetPinSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data["user_id"]
            old_pin = serializer.validated_data.get("old_pin")
            password = serializer.validated_data.get("password")
            new_pin = serializer.validated_data["new_pin"]

            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=404)

            if old_pin and user.check_transaction_pin(old_pin):
                user.set_transaction_pin(new_pin)
                return Response({"message": "PIN reset successfully"}, status=200)

            if password and user.check_password(password):
                user.set_transaction_pin(new_pin)
                return Response({"message": "PIN reset successfully"}, status=200)

            return Response({"error": "Authorization failed"}, status=400)

        return Response(serializer.errors, status=400)


# ==========================
# LOGIN VIEW
# ==========================
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable JWT for login

    def post(self, request):
        business_name = request.data.get("business_name")
        password = request.data.get("password")

        if not business_name or not password:
            return Response(
                {"error": "Both business name and password are required."},
                status=400
            )

        user = authenticate(
            request,
            business_name=business_name,
            password=password
        )

        if user is None:
            if not User.objects.filter(business_name=business_name).exists():
                return Response({"error": "Invalid business name ❌"}, status=400)
            return Response({"error": "Incorrect password ❌"}, status=400)

        refresh = RefreshToken.for_user(user)

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "business_name": user.business_name,
                "email": user.email,
                "phone": user.phone,
            }
        }, status=200)


# ==========================
# PASSWORD RESET VIEWS
# ==========================
class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        user = User.objects.get(email=email)

        token = default_token_generator.make_token(user)
        reset_link = f"http://127.0.0.1:8000/reset-password/{user.pk}/{token}/"

        context = {
            "user": user,
            "reset_link": reset_link,
            "year": timezone.now().year,
        }
        html_content = render_to_string("emails/reset_password_email.html", context)
        text_content = strip_tags(html_content)

        email_message = EmailMultiAlternatives(
            subject="Reset Your Password - ChiamoOrder",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        return Response({"message": "Password reset email sent successfully 📩"}, status=200)


@api_view(["POST"])
def verify_otp(request):
    serializer = VerifyOtpSerializer(data=request.data)
    if serializer.is_valid():
        return Response({"message": "OTP is valid."}, status=200)
    return Response(serializer.errors, status=400)


@api_view(["POST"])
def reset_password(user, reset_link):
    subject = "Reset Your Password - ChiamoOrder"
    context = {
        "user": user,
        "reset_link": reset_link,
        "domain": "http://127.0.0.1:8000",
        "year": datetime.datetime.now().year,
    }

    html_message = render_to_string("emails/reset_password_email.html", context)
    plain_message = strip_tags(html_message)

    email = EmailMultiAlternatives(
        subject, plain_message, "chiamoorder@gmail.com", [user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send()


# ==========================
# PROFILE VIEW
# ==========================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user)
        return Response(serializer.data, status=200)

    def patch(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=200)
        return Response(serializer.errors, status=400)


# ==========================
# THEME UPDATE VIEW
# ==========================
class ThemeUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({"theme": user.theme}, status=200)

    def patch(self, request):
        user = request.user
        theme = request.data.get("theme")

        if theme not in dict(User._meta.get_field("theme").choices):
            return Response({"error": "Invalid theme"}, status=400)

        user.theme = theme
        user.save()
        return Response({"message": "Theme updated successfully", "theme": user.theme}, status=200)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Address
from .serializers import AddressSerializer

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == 'GET':
        addresses = Address.objects.filter(user=request.user)
        serializer = AddressSerializer(addresses, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = AddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):
    try:
        address = Address.objects.get(pk=pk, user=request.user)
    except Address.DoesNotExist:
        return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PUT':
        serializer = AddressSerializer(address, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        address.delete()
        return Response({'message': 'Address deleted'}, status=status.HTTP_204_NO_CONTENT)
