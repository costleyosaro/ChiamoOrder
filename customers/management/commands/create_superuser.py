from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create default superuser and reset login locks'

    def handle(self, *args, **options):
        # Reset axes lockouts
        try:
            from axes.models import AccessAttempt, AccessLog, AccessFailureLog
            AccessAttempt.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Login locks cleared!'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not clear locks: {e}'))
        
        # Create superuser
        User = get_user_model()
        
        business_name = 'ChiamoAdmin'
        email = 'admin@chiamoorder.com'
        password = 'ChiamoAdmin2025!'
        
        if User.objects.filter(business_name=business_name).exists():
            # Update existing user password
            user = User.objects.get(business_name=business_name)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Password reset for "{business_name}"!'))
        else:
            # Create new superuser
            user = User.objects.create_superuser(
                business_name=business_name,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{business_name}" created!'))