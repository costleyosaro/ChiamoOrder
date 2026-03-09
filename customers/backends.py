from django.contrib.auth.backends import ModelBackend
from .models import User

class BusinessNameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, business_name=None, **kwargs):
        identifier = username or business_name
        if not identifier or not password:
            return None
        try:
            user = User.objects.get(business_name=identifier)
        except User.DoesNotExist:
            try:
                user = User.objects.get(business_name__iexact=identifier)
            except User.DoesNotExist:
                try:
                    user = User.objects.get(email__iexact=identifier)
                except User.DoesNotExist:
                    return None
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
