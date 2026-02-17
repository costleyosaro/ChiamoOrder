# customers/models.py

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password
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
    """Custom User model for ChiamoOrder."""
    
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

    # Security PIN fields
    transaction_pin = models.CharField(max_length=255, blank=True, null=True)
    has_pin = models.BooleanField(default=False)

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
        """Set transaction PIN."""
        self.transaction_pin = make_password(raw_pin)
        self.has_pin = True
        self.save(update_fields=['transaction_pin', 'has_pin'])

    def check_transaction_pin(self, raw_pin: str) -> bool:
        """Check transaction PIN."""
        if not self.transaction_pin:
            return False
        return check_password(raw_pin, self.transaction_pin)

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

    def __str__(self):
        return self.business_name


class Address(models.Model):
    """User address model."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses"
    )
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