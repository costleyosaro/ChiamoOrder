# customers/views.py

import os
import threading
import datetime
import traceback
from datetime import timedelta

import requests

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, authentication_classes

from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Address, PinAuditLog
from .serializers import (
    UserSerializer,
    ProfileUpdateSerializer,
    AddressSerializer,
)

# ✅ User model reference
User = get_user_model()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


def log_pin_activity(user, action, request, details=None):
    """Log PIN-related activity for audit"""
    try:
        PinAuditLog.objects.create(
            user=user,
            action=action,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details=details or {}
        )
    except Exception as e:
        print(f"Failed to log PIN activity: {e}")


# ============================================================
# REGISTER VIEW
# ============================================================

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_view(request):
    """Registration — no authentication required"""
    print("🟢 REGISTER VIEW HIT")

    serializer = UserSerializer(data=request.data)
    if not serializer.is_valid():
        print("❌ Validation errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()

    # ✅ Send welcome email in background
    def send_welcome():
        try:
            from customers.utils import send_email
            site_url = getattr(settings, 'SITE_URL', 'https://chiamo-frontend.vercel.app')
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #4CAF50;">🎉 Welcome to ChiamoOrder!</h2>
                <p>Hi {user.name},</p>
                <p>Your business <strong>'{user.business_name}'</strong> has been registered successfully!</p>
                <p>You can now log in and start ordering:</p>
                <a href="{site_url}/login"
                   style="display: inline-block; padding: 12px 24px;
                          background-color: #4CAF50; color: white;
                          text-decoration: none; border-radius: 5px;
                          margin: 20px 0;">
                    Login Now
                </a>
                <br>
                <p>Best regards,<br>ChiamoOrder Team</p>
            </div>
            """
            send_email(to=user.email, subject="🎉 Welcome to ChiamoOrder!", html_content=html_content)
        except Exception as e:
            print(f"❌ Welcome email failed: {e}")

    # ✅ Send SMS in background
    def send_sms():
        try:
            TERMII_API_KEY = os.getenv("TERMII_API_KEY")
            if TERMII_API_KEY:
                requests.post(
                    "https://api.ng.termii.com/api/sms/send",
                    json={
                        "to": user.phone,
                        "from": os.getenv("TERMII_SENDER_ID", "ChiamoOrder"),
                        "sms": f"Hi {user.name}, welcome to ChiamoOrder 🎉.",
                        "type": "plain",
                        "channel": "generic",
                        "api_key": TERMII_API_KEY,
                    },
                    timeout=10
                )
        except Exception as e:
            print(f"❌ SMS failed: {e}")

    threading.Thread(target=send_welcome, daemon=True).start()
    threading.Thread(target=send_sms, daemon=True).start()

    return Response({
        "message": "Registration successful! 🎉",
        "user": {
            "id": user.id,
            "name": user.name,
            "business_name": user.business_name,
            "email": user.email,
        }
    }, status=status.HTTP_201_CREATED)


# ============================================================
# LOGIN VIEW
# ============================================================

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        business_name = request.data.get("business_name")
        password = request.data.get("password")

        if not business_name or not password:
            return Response(
                {"error": "Both business name and password are required."},
                status=400
            )

        user = authenticate(request, business_name=business_name, password=password)

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
                "has_pin": user.has_pin,
                "pin_status": user.get_pin_status()
            }
        }, status=200)


# ============================================================
# PASSWORD RESET VIEWS
# ============================================================

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response({"error": "Email is required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "If an account with this email exists, a reset link has been sent."},
                status=200
            )

        site_url = getattr(settings, "SITE_URL", "https://chiamo-frontend.vercel.app")
        token = default_token_generator.make_token(user)
        reset_link = f"{site_url}/reset-password/{user.pk}/{token}/"

        def send_reset_email():
            try:
                from customers.utils import send_email
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">Reset Your Password</h2>
                    <p>Hi {user.business_name or user.name or 'User'},</p>
                    <p>You requested a password reset for your ChiamoOrder account.</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_link}"
                       style="display: inline-block; padding: 12px 24px;
                              background-color: #4CAF50; color: white;
                              text-decoration: none; border-radius: 5px;
                              margin: 20px 0;">
                        Reset Password
                    </a>
                    <p>Or copy this link: {reset_link}</p>
                    <p>This link expires in 24 hours.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>ChiamoOrder Team</p>
                </div>
                """
                send_email(
                    to=user.email,
                    subject="Reset Your Password - ChiamoOrder",
                    html_content=html_content,
                    plain_text=f"Reset your password: {reset_link}"
                )
            except Exception as e:
                print(f"❌ Reset email failed: {e}")

        threading.Thread(target=send_reset_email, daemon=True).start()

        return Response(
            {"message": "Password reset link has been sent to your email 📩"},
            status=200
        )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password directly with email (no token)"""
    email = request.data.get('email')
    new_password = request.data.get('new_password')

    if not email or not new_password:
        return Response(
            {"error": "Email and new password are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()
        return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def reset_password_confirm(request):
    """Reset password using uid and token from email link"""
    uid = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')

    if not uid or not token or not new_password:
        return Response({"error": "All fields are required."}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 6:
        return Response({"error": "Password must be at least 6 characters."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        return Response({"error": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response(
            {"error": "Reset link has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(new_password)
    user.save()
    print(f"✅ Password reset successful for {user.email}")

    return Response({"message": "Password reset successfully!"}, status=status.HTTP_200_OK)


# ============================================================
# TRANSACTION PIN VIEWS
# ============================================================

class HasTransactionPinView(APIView):
    """Check if user has a transaction PIN set"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        try:
            # Always use the authenticated user (ignore pk for security)
            user = request.user
            return Response({
                "has_pin": user.has_pin,
            }, status=200)
        except Exception as e:
            print(f"❌ Has PIN check error: {e}")
            return Response({"error": "Could not check PIN status.", "has_pin": False}, status=500)


class SetPinView(APIView):
    """Set user's transaction PIN"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pin = request.data.get('pin')

        if not pin:
            return Response({'error': 'PIN is required'}, status=400)

        if len(pin) != 4 or not pin.isdigit():
            return Response({'error': 'PIN must be exactly 4 digits'}, status=400)

        try:
            user = request.user

            if user.has_pin:
                return Response(
                    {'error': 'Transaction PIN already set. Use reset PIN instead.'},
                    status=400
                )

            user.set_transaction_pin(pin)

            try:
                log_pin_activity(user, 'SET', request, {'success': True, 'pin_length': len(pin)})
            except Exception:
                pass

            return Response({
                'message': 'Transaction PIN set successfully',
                'has_pin': True
            }, status=200)

        except ValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif isinstance(e.args[0], list):
                error_msg = e.args[0][0] if e.args[0] else str(e)
            return Response({'error': error_msg}, status=400)

        except Exception as e:
            print(f"❌ Set PIN error: {e}")
            traceback.print_exc()
            return Response({'error': 'Failed to set PIN. Please try again.'}, status=500)


class ValidatePinView(APIView):
    """Validate user's transaction PIN"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pin = request.data.get('pin')

        if not pin:
            return Response({'error': 'PIN is required'}, status=400)

        try:
            user = request.user

            if not user.has_pin:
                return Response({
                    'valid': False,
                    'message': 'Transaction PIN not set',
                    'error': 'Transaction PIN not set. Please set one first.'
                }, status=400)

            is_valid = user.validate_transaction_pin(pin)

            log_pin_activity(user, 'VALIDATE_SUCCESS', request, {
                'attempts_before': user.pin_attempts
            })

            return Response({
                'valid': True,
                'message': 'PIN validated successfully'
            }, status=200)

        except ValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif isinstance(e.args[0], list):
                error_msg = e.args[0][0] if e.args[0] else str(e)

            action = 'ACCOUNT_LOCKED' if 'locked' in error_msg.lower() else 'VALIDATE_FAIL'
            try:
                log_pin_activity(request.user, action, request, {
                    'error': error_msg,
                    'attempts_after': request.user.pin_attempts,
                })
            except Exception:
                pass

            return Response({
                'valid': False,
                'error': error_msg
            }, status=400)

        except Exception as e:
            print(f"❌ PIN validation error: {e}")
            traceback.print_exc()
            return Response({
                'valid': False,
                'error': 'PIN validation failed. Please try again.'
            }, status=500)


class ResetPinView(APIView):
    """Reset user's transaction PIN"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_pin = request.data.get("old_pin")
        password = request.data.get("password")
        new_pin = request.data.get("new_pin")

        if not new_pin:
            return Response({"error": "New PIN is required"}, status=400)

        if len(new_pin) != 4 or not new_pin.isdigit():
            return Response({"error": "PIN must be exactly 4 digits"}, status=400)

        try:
            user = request.user

            # Method 1: Change PIN using old PIN
            if old_pin:
                user.change_transaction_pin(old_pin, new_pin)
                log_pin_activity(user, 'CHANGE', request, {'method': 'old_pin'})
                return Response({"message": "PIN reset successfully"}, status=200)

            # Method 2: Reset PIN using account password
            if password and user.check_password(password):
                user.set_transaction_pin(new_pin)
                log_pin_activity(user, 'RESET', request, {'method': 'password'})
                return Response({"message": "PIN reset successfully"}, status=200)

            return Response(
                {"error": "Either old PIN or password is required for authorization"},
                status=400
            )

        except ValidationError as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif isinstance(e.args[0], list):
                error_msg = e.args[0][0] if e.args[0] else str(e)

            log_pin_activity(request.user, 'RESET', request, {
                'success': False,
                'error': error_msg,
                'method': 'old_pin' if old_pin else 'password'
            })
            return Response({"error": error_msg}, status=400)

        except Exception as e:
            print(f"❌ Reset PIN error: {e}")
            traceback.print_exc()
            return Response({"error": "Failed to reset PIN."}, status=500)


# ============================================================
# PROFILE VIEW
# ============================================================

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user)
        data = serializer.data
        data['pin_status'] = user.get_pin_status()
        return Response(data, status=200)

    def patch(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            response_data = serializer.data
            response_data['pin_status'] = user.get_pin_status()
            return Response(response_data, status=200)
        return Response(serializer.errors, status=400)


# ============================================================
# THEME UPDATE VIEW
# ============================================================

class ThemeUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"theme": request.user.theme}, status=200)

    def patch(self, request):
        user = request.user
        theme = request.data.get("theme")

        if theme not in dict(User._meta.get_field("theme").choices):
            return Response({"error": "Invalid theme"}, status=400)

        user.theme = theme
        user.save()
        return Response({"message": "Theme updated successfully", "theme": user.theme}, status=200)


# ============================================================
# ADDRESS VIEWS
# ============================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == 'GET':
        user_addresses = Address.objects.filter(user=request.user)
        serializer = AddressSerializer(user_addresses, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = AddressSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):
    try:
        address = Address.objects.get(pk=pk, user=request.user)
    except Address.DoesNotExist:
        return Response({'error': 'Address not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = AddressSerializer(address)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = AddressSerializer(address, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        address.delete()
        return Response({'message': 'Address deleted'}, status=status.HTTP_204_NO_CONTENT)


# ============================================================
# ADMIN / AUDIT VIEWS
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pin_audit_logs(request):
    """Get PIN audit logs"""
    if request.user.is_staff:
        user_id = request.GET.get('user_id')
        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
                logs = PinAuditLog.objects.filter(user=target_user)[:50]
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
        else:
            logs = PinAuditLog.objects.all()[:100]
    else:
        logs = PinAuditLog.objects.filter(user=request.user)[:20]

    logs_data = [{
        'id': log.id,
        'user': log.user.business_name,
        'action': log.action,
        'timestamp': log.timestamp,
        'ip_address': log.ip_address,
        'details': log.details
    } for log in logs]

    return Response({'logs': logs_data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unlock_user_account(request):
    """Unlock a user's PIN account (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=403)

    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'User ID is required'}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
        target_user.reset_pin_attempts()
        log_pin_activity(target_user, 'ACCOUNT_UNLOCKED', request, {
            'admin_user': request.user.business_name,
            'unlocked_by_admin': True
        })
        return Response({
            'message': f'Account unlocked for user {target_user.business_name}',
            'pin_status': target_user.get_pin_status()
        })
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_security_dashboard(request):
    """Security dashboard data (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=403)

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    stats = {
        'total_users': User.objects.count(),
        'users_with_pin': User.objects.filter(has_pin=True).count(),
        'locked_accounts': User.objects.filter(pin_locked_until__gt=now).count(),
        'failed_attempts_24h': PinAuditLog.objects.filter(action='VALIDATE_FAIL', timestamp__gte=last_24h).count(),
        'successful_validations_24h': PinAuditLog.objects.filter(action='VALIDATE_SUCCESS', timestamp__gte=last_24h).count(),
        'pins_set_7d': PinAuditLog.objects.filter(action='SET', timestamp__gte=last_7d).count(),
        'pins_changed_7d': PinAuditLog.objects.filter(action='CHANGE', timestamp__gte=last_7d).count(),
    }

    recent_events = PinAuditLog.objects.filter(
        action__in=['ACCOUNT_LOCKED', 'VALIDATE_FAIL', 'SET', 'CHANGE']
    ).order_by('-timestamp')[:20]

    events_data = [{
        'user': event.user.business_name,
        'action': event.action,
        'timestamp': event.timestamp,
        'ip_address': event.ip_address,
        'details': event.details
    } for event in recent_events]

    return Response({'stats': stats, 'recent_events': events_data})


# ============================================================
# HEALTH CHECK
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now(),
        'version': '2.0.0',
    })