from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.contrib.auth import authenticate, get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError

import requests
import os
import datetime

from .models import User, Address, PinAuditLog
from .serializers import (
    UserSerializer,
    ResetPinSerializer,
    SetPinSerializer,
    ValidatePinSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    VerifyOtpSerializer,
    ProfileUpdateSerializer,
    AddressSerializer,
)

# ✅ User model reference
User = get_user_model()


# ✅ Helper functions for PIN security
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


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
        # Don't fail the main operation if logging fails
        print(f"Failed to log PIN activity: {e}")


# ==========================
# REGISTER VIEW
# ==========================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    authentication_classes = []     

    def perform_create(self, serializer):
        user = serializer.save()

        # =========================
        # ✅ SEND WELCOME EMAIL
        # =========================
        try:
            subject = "🎉 Welcome to ChiamoOrder!"
            site_url = getattr(settings, "SITE_URL", "https://chiamo-frontend.vercel.app")

            context = {
                "user": user,
                "domain": site_url,
                "login_url": f"{site_url}/login",
                "dashboard_url": f"{site_url}/home",
                "year": datetime.datetime.now().year,
            }

            html_message = render_to_string("emails/welcome_email.html", context)
            plain_message = strip_tags(html_message)

            email = EmailMultiAlternatives(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
            email.attach_alternative(html_message, "text/html")
            email.send()

            print(f"📩 Welcome email sent to {user.email}")

        except Exception as e:
            print("❌ Email sending failed:", str(e))

        # =========================
        # ✅ SEND WELCOME SMS (TERMII)
        # =========================
        try:
            TERMII_API_KEY = os.getenv("TERMII_API_KEY")
            TERMII_SENDER_ID = os.getenv("TERMII_SENDER_ID", "ChiamoOrder")

            if TERMII_API_KEY:
                sms_payload = {
                    "to": user.phone,
                    "from": TERMII_SENDER_ID,
                    "sms": f"Hi {user.name}, welcome to ChiamoOrder 🎉. "
                           f"Your business '{user.business_name}' has been registered successfully.",
                    "type": "plain",
                    "channel": "generic",
                    "api_key": TERMII_API_KEY,
                }

                response = requests.post(
                    "https://api.ng.termii.com/api/sms/send",
                    json=sms_payload,
                    timeout=10
                )

                print("📲 Termii SMS response:", response.json())
            else:
                print("⚠️ TERMII_API_KEY not set. SMS skipped.")

        except Exception as e:
            print("❌ SMS sending failed:", str(e))

# ==========================
# ✅ ENHANCED TRANSACTION PIN VIEWS (FINTECH-GRADE)
# ==========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_transaction_pin(request):
    """Set user's transaction PIN with fintech-grade security validation"""
    pin = request.data.get('pin')
    
    if not pin:
        return Response({'error': 'PIN is required'}, status=400)
    
    try:
        request.user.set_transaction_pin(pin)
        
        # Log successful PIN creation
        log_pin_activity(request.user, 'SET', request, {
            'success': True,
            'pin_length': len(pin)
        })
        
        return Response({
            'message': 'Transaction PIN set successfully',
            'pin_status': request.user.get_pin_status()
        })
        
    except ValidationError as e:
        # Log failed PIN creation attempt
        log_pin_activity(request.user, 'SET', request, {
            'success': False,
            'error': str(e),
            'pin_length': len(pin) if pin else 0
        })
        
        return Response({'error': str(e)}, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_transaction_pin(request):
    """Validate user's transaction PIN with security logging"""
    pin = request.data.get('pin')
    
    if not pin:
        return Response({'error': 'PIN is required'}, status=400)
    
    try:
        is_valid = request.user.validate_transaction_pin(pin)
        
        # Log successful validation
        log_pin_activity(request.user, 'VALIDATE_SUCCESS', request, {
            'attempts_before': request.user.pin_attempts
        })
        
        return Response({
            'valid': True, 
            'message': 'PIN validated successfully',
            'pin_status': request.user.get_pin_status()
        })
        
    except ValidationError as e:
        error_message = str(e)
        
        # Determine if account was locked
        action = 'ACCOUNT_LOCKED' if 'locked' in error_message.lower() else 'VALIDATE_FAIL'
        
        # Log failed validation
        log_pin_activity(request.user, action, request, {
            'error': error_message,
            'attempts_after': request.user.pin_attempts,
            'locked_until': request.user.pin_locked_until.isoformat() if request.user.pin_locked_until else None
        })
        
        return Response({
            'valid': False, 
            'error': error_message,
            'pin_status': request.user.get_pin_status()
        }, status=400)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_transaction_pin(request):
    """Change user's transaction PIN"""
    old_pin = request.data.get('old_pin')
    new_pin = request.data.get('new_pin')
    
    if not old_pin or not new_pin:
        return Response({'error': 'Both old and new PIN are required'}, status=400)
    
    try:
        request.user.change_transaction_pin(old_pin, new_pin)
        
        # Log successful PIN change
        log_pin_activity(request.user, 'CHANGE', request, {
            'success': True
        })
        
        return Response({
            'message': 'Transaction PIN changed successfully',
            'pin_status': request.user.get_pin_status()
        })
        
    except ValidationError as e:
        # Log failed PIN change
        log_pin_activity(request.user, 'CHANGE', request, {
            'success': False,
            'error': str(e)
        })
        
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pin_status(request):
    """Get comprehensive PIN status"""
    return Response({
        'pin_status': request.user.get_pin_status()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_pin_attempts(request):
    """Reset PIN attempts (for admin or support)"""
    # Add additional authorization check here if needed
    if not request.user.is_staff:
        return Response({'error': 'Unauthorized - Admin access required'}, status=403)
    
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'User ID is required'}, status=400)
    
    try:
        target_user = User.objects.get(id=user_id)
        target_user.reset_pin_attempts()
        
        # Log admin action
        log_pin_activity(target_user, 'RESET', request, {
            'admin_user': request.user.business_name,
            'reset_by_admin': True
        })
        
        return Response({
            'message': f'PIN attempts reset for user {target_user.business_name}',
            'pin_status': target_user.get_pin_status()
        })
        
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)


# ==========================
# ✅ LEGACY PIN VIEWS (BACKWARD COMPATIBILITY)
# ==========================
class HasTransactionPinView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk=None):
        try:
            # If pk is provided, check that user (admin only)
            if pk and request.user.is_staff:
                user = User.objects.get(id=pk)
            else:
                user = request.user
                
            return Response({
                "has_pin": user.has_pin,
                "pin_status": user.get_pin_status()
            })
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class SetPinView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Use the new secure endpoint
        return set_transaction_pin(request)


class ValidatePinView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Use the new secure endpoint
        return validate_transaction_pin(request)


class ResetPinView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        old_pin = request.data.get("old_pin")
        password = request.data.get("password")
        new_pin = request.data.get("new_pin")

        if not new_pin:
            return Response({"error": "New PIN is required"}, status=400)

        try:
            # If old PIN provided, use change PIN method
            if old_pin:
                request.user.change_transaction_pin(old_pin, new_pin)
                log_pin_activity(request.user, 'CHANGE', request, {'method': 'old_pin'})
                return Response({"message": "PIN reset successfully"}, status=200)

            # If password provided, verify and set new PIN
            if password and request.user.check_password(password):
                request.user.set_transaction_pin(new_pin)
                log_pin_activity(request.user, 'RESET', request, {'method': 'password'})
                return Response({"message": "PIN reset successfully"}, status=200)

            return Response({"error": "Either old PIN or password is required for authorization"}, status=400)

        except ValidationError as e:
            log_pin_activity(request.user, 'RESET', request, {
                'success': False,
                'error': str(e),
                'method': 'old_pin' if old_pin else 'password'
            })
            return Response({"error": str(e)}, status=400)


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
                "has_pin": user.has_pin,
                "pin_status": user.get_pin_status()
            }
        }, status=200)

# ==========================
# PASSWORD RESET VIEWS
# ==========================
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            serializer = ForgotPasswordSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=400)

            email = serializer.validated_data["email"]
            
            # ✅ Handle case where user doesn't exist
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Return success anyway for security (don't reveal if email exists)
                return Response(
                    {"message": "If an account with this email exists, a password reset link has been sent."}, 
                    status=200
                )

            # ✅ Generate reset token
            token = default_token_generator.make_token(user)
            reset_link = f"{settings.SITE_URL}/reset-password/{user.pk}/{token}/"

            # ✅ Simple email content (no template needed)
            subject = "Reset Your Password - ChiamoOrder"
            message = f"""
            Hi {user.business_name or user.email},

            You requested a password reset for your ChiamoOrder account.

            Click the link below to reset your password:
            {reset_link}

            If you didn't request this, please ignore this email.

            Best regards,
            ChiamoOrder Team
            """

            # ✅ Send simple text email
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as email_error:
                # ✅ Log email error but still return success
                print(f"Email sending failed: {email_error}")
                # For development, you might want to return the reset link
                if settings.DEBUG:
                    return Response({
                        "message": "Password reset email sent successfully 📩",
                        "debug_reset_link": reset_link  # Remove this in production
                    }, status=200)

            return Response({"message": "Password reset email sent successfully 📩"}, status=200)

        except Exception as e:
            # ✅ Catch any other errors
            print(f"Forgot password error: {str(e)}")
            return Response(
                {"error": "Something went wrong. Please try again later."}, 
                status=500
            )



# ==========================
# PROFILE VIEW
# ==========================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user)
        data = serializer.data
        
        # ✅ Add PIN status to profile response
        data['pin_status'] = user.get_pin_status()
        
        return Response(data, status=200)

    def patch(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            
            # ✅ Include PIN status in response
            response_data = serializer.data
            response_data['pin_status'] = user.get_pin_status()
            
            return Response(response_data, status=200)
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


# ==========================
# ✅ ADDRESS MANAGEMENT VIEWS
# ==========================
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


# ==========================
# ✅ PIN AUDIT AND ADMIN VIEWS
# ==========================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pin_audit_logs(request):
    """Get PIN audit logs for current user or all users (admin only)"""
    if request.user.is_staff:
        # Admin can see all logs
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
        # Regular users can only see their own logs
        logs = PinAuditLog.objects.filter(user=request.user)[:20]
    
    logs_data = []
    for log in logs:
        logs_data.append({
            'id': log.id,
            'user': log.user.business_name,
            'action': log.action,
            'timestamp': log.timestamp,
            'ip_address': log.ip_address,
            'details': log.details
        })
    
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
        
        # Log admin unlock action
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
    """Get security dashboard data (admin only)"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=403)
    
    from django.db.models import Count, Q
    from datetime import timedelta
    
    # Get statistics
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    stats = {
        'total_users': User.objects.count(),
        'users_with_pin': User.objects.filter(has_pin=True).count(),
        'locked_accounts': User.objects.filter(
            pin_locked_until__gt=now
        ).count(),
        'failed_attempts_24h': PinAuditLog.objects.filter(
            action='VALIDATE_FAIL',
            timestamp__gte=last_24h
        ).count(),
        'successful_validations_24h': PinAuditLog.objects.filter(
            action='VALIDATE_SUCCESS',
            timestamp__gte=last_24h
        ).count(),
        'pins_set_7d': PinAuditLog.objects.filter(
            action='SET',
            timestamp__gte=last_7d
        ).count(),
        'pins_changed_7d': PinAuditLog.objects.filter(
            action='CHANGE',
            timestamp__gte=last_7d
        ).count(),
    }
    
    # Get recent security events
    recent_events = PinAuditLog.objects.filter(
        action__in=['ACCOUNT_LOCKED', 'VALIDATE_FAIL', 'SET', 'CHANGE']
    ).order_by('-timestamp')[:20]
    
    events_data = []
    for event in recent_events:
        events_data.append({
            'user': event.user.business_name,
            'action': event.action,
            'timestamp': event.timestamp,
            'ip_address': event.ip_address,
            'details': event.details
        })
    
    return Response({
        'stats': stats,
        'recent_events': events_data
    })


# ==========================
# ✅ UTILITY VIEWS
# ==========================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_pin_uniqueness(request):
    """Check if a PIN is unique (for frontend validation)"""
    pin = request.data.get('pin')
    
    if not pin or len(pin) != 4 or not pin.isdigit():
        return Response({'error': 'Invalid PIN format'}, status=400)
    
    # Check weak PINs
    weak_pins = [
        '0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999',
        '1234', '4321', '1122', '2211', '1212', '2121', '0123', '3210',
        '1357', '2468', '9876', '6789'
    ]
    
    if pin in weak_pins:
        return Response({
            'unique': False,
            'reason': 'weak',
            'message': 'Please choose a stronger PIN. Avoid common patterns.'
        })
    
    # Check uniqueness
    from django.contrib.auth.hashers import check_password
    
    existing_users = User.objects.exclude(id=request.user.id).filter(
        transaction_pin__isnull=False,
        has_pin=True
    )
    
    for user in existing_users:
        if user.transaction_pin and check_password(pin, user.transaction_pin):
            return Response({
                'unique': False,
                'reason': 'duplicate',
                'message': 'This PIN is already in use. Please choose a different PIN.'
            })
    
    return Response({
        'unique': True,
        'message': 'PIN is available and secure.'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_security_summary(request):
    """Get security summary for current user"""
    user = request.user
    
    # Get recent PIN activities
    recent_activities = PinAuditLog.objects.filter(
        user=user
    ).order_by('-timestamp')[:10]
    
    activities_data = []
    for activity in recent_activities:
        activities_data.append({
            'action': activity.action,
            'timestamp': activity.timestamp,
            'ip_address': activity.ip_address,
            'success': activity.details.get('success', True) if activity.details else True
        })
    
    return Response({
        'pin_status': user.get_pin_status(),
        'recent_activities': activities_data,
        'security_score': calculate_security_score(user)
    })


def calculate_security_score(user):
    """Calculate user security score (0-100)"""
    score = 0
    
    # Has PIN set (30 points)
    if user.has_pin:
        score += 30
    
    # PIN is not expired (20 points)
    if user.has_pin and not user.is_pin_expired():
        score += 20
    
    # No recent failed attempts (20 points)
    recent_fails = PinAuditLog.objects.filter(
        user=user,
        action='VALIDATE_FAIL',
        timestamp__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    if recent_fails == 0:
        score += 20
    elif recent_fails <= 2:
        score += 10
    
    # Account not locked (15 points)
    if not user.pin_locked_until or timezone.now() > user.pin_locked_until:
        score += 15
    
    # Recent PIN activity (15 points)
    recent_activity = PinAuditLog.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(days=30)
    ).exists()
    
    if recent_activity:
        score += 15
    
    return min(score, 100)


# ==========================
# ✅ HEALTH CHECK VIEW
# ==========================
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now(),
        'version': '1.0.0',
        'features': {
            'pin_security': True,
            'audit_logging': True,
            'progressive_lockout': True,
            'pin_uniqueness': True
        }
    })


# ==========================
# ✅ EMAIL UTILITY FUNCTION
# ==========================
def send_password_reset_email(user, reset_link):
    """Send password reset email"""
    from django.conf import settings
    
    subject = "Reset Your Password - ChiamoOrder"
    context = {
        "user": user,
        "reset_link": reset_link,
        "domain": getattr(settings, 'SITE_URL', 'https://chiamo-frontend.vercel.app/'),  # ✅ Use frontend URL
        "frontend_url": getattr(settings, 'FRONTEND_URL', 'https://chiamo-frontend.vercel.app/'),  # ✅ Frontend URL
        "backend_url": getattr(settings, 'BACKEND_URL', 'https://web-production-04707.up.railway.app'),  # ✅ Backend URL
        "login_url": f"{getattr(settings, 'SITE_URL', 'https://chiamo-frontend.vercel.app/')}/login",  # ✅ Login page
        "support_url": f"{getattr(settings, 'SITE_URL', 'https://chiamo-frontend.vercel.app/')}/support",  # ✅ Support page
        "year": datetime.datetime.now().year,
    }

    html_message = render_to_string("emails/reset_password_email.html", context)
    plain_message = strip_tags(html_message)

    email = EmailMultiAlternatives(
        subject, plain_message, settings.DEFAULT_FROM_EMAIL, [user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send()



# ==========================
# RESET PASSWORD (function-based)
# ==========================
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
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
        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK
        )
    except User.DoesNotExist:
        return Response(
            {"error": "User not found."},
            status=status.HTTP_404_NOT_FOUND
        )


# ==========================
# HAS TRANSACTION PIN VIEW
# ==========================
class HasTransactionPinView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            has_pin = bool(user.transaction_pin)
            return Response({"has_pin": has_pin}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )


# ==========================
# ADDRESSES (function-based)
# ==========================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == 'GET':
        # Return user's addresses
        return Response(
            {"addresses": []},
            status=status.HTTP_200_OK
        )
    
    elif request.method == 'POST':
        # Create new address
        return Response(
            {"message": "Address created successfully."},
            status=status.HTTP_201_CREATED
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def address_detail(request, pk):
    if request.method == 'GET':
        return Response(
            {"message": "Address detail."},
            status=status.HTTP_200_OK
        )
    
    elif request.method == 'PUT':
        return Response(
            {"message": "Address updated."},
            status=status.HTTP_200_OK
        )
    
    elif request.method == 'DELETE':
        return Response(
            {"message": "Address deleted."},
            status=status.HTTP_204_NO_CONTENT
        )