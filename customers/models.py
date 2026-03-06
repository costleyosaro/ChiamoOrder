# customers/models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import random
from io import BytesIO
from django.core.files import File
from django.conf import settings
import qrcode


class UserManager(BaseUserManager):
    """Custom manager for User model."""
    
    def create_user(self, business_name, email, password=None, **extra_fields):
        if not business_name:
            raise ValueError("Business name is required")
        if not email:
            raise ValueError("Email is required")
        
        email = self.normalize_email(email)
        user = self.model(business_name=business_name, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, business_name, email, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(business_name, email, password, **extra_fields)


class ThemeChoices(models.TextChoices):
    LIGHT = "light", "Light"
    DARK = "dark", "Dark"


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model for ChiamoOrder with fintech-grade PIN security."""
    
    name = models.CharField(max_length=255, blank=True, null=True)
    business_name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.TextField(blank=True, null=True)
    sales_executive = models.TextField(max_length=30, blank=True, null=True)
    latitude = models.CharField(max_length=50, blank=True, null=True)
    longitude = models.CharField(max_length=50, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    shop_photo_url = models.URLField(blank=True, null=True)
    theme = models.CharField(
        max_length=10,
        choices=ThemeChoices.choices,
        default=ThemeChoices.LIGHT,
    )
    qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)

    # ✅ Enhanced Security PIN fields (fintech-grade)
    transaction_pin = models.CharField(max_length=128, blank=True, null=True)  # Store hashed PIN
    has_pin = models.BooleanField(default=False)
    pin_attempts = models.IntegerField(default=0)  # Track failed attempts
    pin_locked_until = models.DateTimeField(blank=True, null=True)  # Account lockout
    pin_created_at = models.DateTimeField(blank=True, null=True)  # PIN creation time
    pin_last_changed = models.DateTimeField(blank=True, null=True)  # Last PIN change

    # OTP fields for password reset
    reset_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    # Required by Django
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Fix: Add related_name to avoid clashes with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='customer_users',
        related_query_name='customer_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='customer_users',
        related_query_name='customer_user',
    )

    objects = UserManager()

    USERNAME_FIELD = "business_name"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def save(self, *args, **kwargs):
        # Only generate QR code if user has been saved (has an ID)
        if self.pk:
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(f"https://yourfrontend.com/user/{self.pk}")
                qr.make(fit=True)

                img = qr.make_image(fill="black", back_color="white")
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                buffer.seek(0)
                file_name = f"qr_{self.business_name}.png"
                self.qr_code.save(file_name, File(buffer), save=False)
            except Exception:
                pass  # Don't fail if QR generation fails

        super().save(*args, **kwargs)

    def set_transaction_pin(self, raw_pin: str):
        """
        Set transaction PIN with fintech-grade security.
        Ensures PIN uniqueness across all users.
        """
        # Validate PIN format
        if not raw_pin or len(raw_pin) != 4 or not raw_pin.isdigit():
            raise ValidationError("PIN must be exactly 4 digits")
        
        # ✅ Check for PIN uniqueness across all users
        existing_users = User.objects.exclude(id=self.id).filter(
            transaction_pin__isnull=False,
            has_pin=True
        )
        
        # Check if any existing user has this PIN
        for user in existing_users:
            if user.transaction_pin and check_password(raw_pin, user.transaction_pin):
                raise ValidationError("This PIN is already in use by another user. Please choose a different PIN.")
        
        # ✅ Additional security: Prevent common/weak PINs
        weak_pins = [
            '0000', '1111', '2222', '3333', '4444', '5555', '6666', '7777', '8888', '9999',
            '1234', '4321', '1122', '2211', '1212', '2121', '0123', '3210',
            '1357', '2468', '9876', '6789'
        ]
        
        if raw_pin in weak_pins:
            raise ValidationError("Please choose a stronger PIN. Avoid common patterns like 1234, 0000, etc.")
        
        # Set the PIN
        self.transaction_pin = make_password(raw_pin)
        self.has_pin = True
        self.pin_attempts = 0
        self.pin_locked_until = None
        self.pin_created_at = timezone.now()
        self.pin_last_changed = timezone.now()
        
        self.save(update_fields=[
            'transaction_pin', 'has_pin', 'pin_attempts', 
            'pin_locked_until', 'pin_created_at', 'pin_last_changed'
        ])

    def validate_transaction_pin(self, raw_pin: str) -> bool:
        """
        Validate transaction PIN with rate limiting and account lockout.
        Fintech-grade security with attempt tracking.
        """
        # Check if account is locked
        if self.pin_locked_until and timezone.now() < self.pin_locked_until:
            time_remaining = self.pin_locked_until - timezone.now()
            minutes_remaining = int(time_remaining.total_seconds() / 60)
            raise ValidationError(f"Account temporarily locked. Try again in {minutes_remaining} minutes.")
        
        # Check if user has a PIN set
        if not self.transaction_pin or not self.has_pin:
            raise ValidationError("No transaction PIN set. Please set your PIN first.")
        
        # Validate PIN format
        if not raw_pin or len(raw_pin) != 4 or not raw_pin.isdigit():
            raise ValidationError("Invalid PIN format. PIN must be 4 digits.")
        
        # Check PIN
        if not check_password(raw_pin, self.transaction_pin):
            self.pin_attempts += 1
            
            # ✅ Progressive lockout: 3 attempts = 15 mins, 6 attempts = 1 hour, 9+ attempts = 24 hours
            if self.pin_attempts >= 9:
                self.pin_locked_until = timezone.now() + timedelta(hours=24)
                self.save(update_fields=['pin_attempts', 'pin_locked_until'])
                raise ValidationError("Too many failed attempts. Account locked for 24 hours. Contact support if needed.")
            elif self.pin_attempts >= 6:
                self.pin_locked_until = timezone.now() + timedelta(hours=1)
                self.save(update_fields=['pin_attempts', 'pin_locked_until'])
                raise ValidationError("Too many failed attempts. Account locked for 1 hour.")
            elif self.pin_attempts >= 3:
                self.pin_locked_until = timezone.now() + timedelta(minutes=15)
                self.save(update_fields=['pin_attempts', 'pin_locked_until'])
                raise ValidationError("Too many failed attempts. Account locked for 15 minutes.")
            else:
                self.save(update_fields=['pin_attempts'])
                remaining_attempts = 3 - self.pin_attempts
                raise ValidationError(f"Invalid PIN. {remaining_attempts} attempt{'s' if remaining_attempts != 1 else ''} remaining before lockout.")
        
        # ✅ Reset attempts on successful validation
        self.pin_attempts = 0
        self.pin_locked_until = None
        self.save(update_fields=['pin_attempts', 'pin_locked_until'])
        return True

    def check_transaction_pin(self, raw_pin: str) -> bool:
        """
        Legacy method for backward compatibility.
        Use validate_transaction_pin for new implementations.
        """
        try:
            return self.validate_transaction_pin(raw_pin)
        except ValidationError:
            return False

    def reset_pin_attempts(self):
        """Reset PIN attempts (admin function)"""
        self.pin_attempts = 0
        self.pin_locked_until = None
        self.save(update_fields=['pin_attempts', 'pin_locked_until'])

    def change_transaction_pin(self, old_pin: str, new_pin: str):
        """Change transaction PIN with old PIN verification"""
        # Verify old PIN first
        if not self.validate_transaction_pin(old_pin):
            raise ValidationError("Current PIN is incorrect.")
        
        # Set new PIN (this will validate uniqueness and strength)
        self.set_transaction_pin(new_pin)

    def is_pin_expired(self, days: int = 90) -> bool:
        """Check if PIN is older than specified days (for PIN rotation policy)"""
        if not self.pin_created_at:
            return True
        return timezone.now() > self.pin_created_at + timedelta(days=days)

    def generate_reset_otp(self):
        """Generate 4-digit OTP for password reset."""
        otp = str(random.randint(1000, 9999))
        self.reset_otp = otp
        self.otp_created_at = timezone.now()
        self.save(update_fields=['reset_otp', 'otp_created_at'])
        return otp

    def validate_reset_otp(self, otp: str) -> bool:
        """Check if OTP is valid and not expired (10 mins)."""
        if not self.reset_otp or not self.otp_created_at:
            return False
        if self.reset_otp != otp:
            return False
        if timezone.now() > self.otp_created_at + timedelta(minutes=10):
            return False
        return True

    def get_pin_status(self) -> dict:
        """Get comprehensive PIN status for frontend"""
        status = {
            'has_pin': self.has_pin,
            'is_locked': bool(self.pin_locked_until and timezone.now() < self.pin_locked_until),
            'attempts_remaining': max(0, 3 - self.pin_attempts) if self.pin_attempts < 3 else 0,
            'locked_until': self.pin_locked_until.isoformat() if self.pin_locked_until else None,
            'pin_age_days': (timezone.now() - self.pin_created_at).days if self.pin_created_at else None,
            'needs_pin_change': self.is_pin_expired() if self.has_pin else False
        }
        return status

    def __str__(self):
        return self.business_name


class Address(models.Model):
    """User address model."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses"
    )
    label = models.CharField(max_length=50, default='Home', blank=True)
    street = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f"{self.street}, {self.city}, {self.state or ''}"


# ✅ Add PIN audit log for compliance
class PinAuditLog(models.Model):
    """Audit log for PIN-related activities"""
    
    ACTION_CHOICES = [
        ('SET', 'PIN Set'),
        ('CHANGE', 'PIN Changed'),
        ('VALIDATE_SUCCESS', 'PIN Validation Success'),
        ('VALIDATE_FAIL', 'PIN Validation Failed'),
        ('ACCOUNT_LOCKED', 'Account Locked'),
        ('ACCOUNT_UNLOCKED', 'Account Unlocked'),
        ('RESET', 'PIN Reset by Admin'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pin_audit_logs"
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(blank=True, null=True)  # Additional context
    
    class Meta:
        verbose_name = 'PIN Audit Log'
        verbose_name_plural = 'PIN Audit Logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.business_name} - {self.action} - {self.timestamp}"