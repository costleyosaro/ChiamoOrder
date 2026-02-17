from django.contrib.auth.backends import ModelBackend
from .models import User

class BusinessNameBackend(ModelBackend):
    def authenticate(self, request, business_name=None, password=None, **kwargs):
        try:
            user = User.objects.get(business_name=business_name)
        except User.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None
