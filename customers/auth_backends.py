# customers/backends.py
from django.contrib.auth.backends import ModelBackend
from .models import User


class BusinessNameBackend(ModelBackend):
    """
    Custom authentication backend for ChiamoOrder.
    
    Handles both:
    - Django Admin login (sends 'username' parameter)
    - API login (may send 'business_name' parameter)
    """
    
    def authenticate(self, request, username=None, password=None, business_name=None, **kwargs):
        """
        Authenticate user by business_name.
        
        Django admin sends 'username', so we accept both 'username' and 'business_name'.
        """
        # Get the identifier - admin sends 'username', API might send 'business_name'
        identifier = username or business_name or kwargs.get('username')
        
        if not identifier or not password:
            return None
        
        # Try to find user by business_name (case-sensitive first)
        user = None
        
        try:
            user = User.objects.get(business_name=identifier)
        except User.DoesNotExist:
            # Try case-insensitive match
            try:
                user = User.objects.get(business_name__iexact=identifier)
            except User.DoesNotExist:
                # Try by email as fallback
                try:
                    user = User.objects.get(email__iexact=identifier)
                except User.DoesNotExist:
                    return None
        
        # Check password and user status
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
    
    def get_user(self, user_id):
        """Retrieve user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None