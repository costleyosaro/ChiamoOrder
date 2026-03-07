# customers/management/commands/create_superuser.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create default superuser and reset login locks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--business-name',
            type=str,
            help='Business name for superuser (or set SUPERUSER_BUSINESS_NAME env var)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email for superuser (or set SUPERUSER_EMAIL env var)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for superuser (or set SUPERUSER_PASSWORD env var)',
        )

    def handle(self, *args, **options):
        # Reset axes lockouts
        try:
            from axes.models import AccessAttempt, AccessLog, AccessFailureLog
            AccessAttempt.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Login locks cleared!'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Could not clear locks: {e}'))
        
        # Get credentials from arguments or environment variables
        business_name = (
            options.get('business_name') or 
            os.environ.get('SUPERUSER_BUSINESS_NAME') or 
            os.environ.get('DJANGO_SUPERUSER_BUSINESS_NAME')
        )
        email = (
            options.get('email') or 
            os.environ.get('SUPERUSER_EMAIL') or 
            os.environ.get('DJANGO_SUPERUSER_EMAIL')
        )
        password = (
            options.get('password') or 
            os.environ.get('SUPERUSER_PASSWORD') or 
            os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        )
        
        # Validate credentials
        if not business_name or not email or not password:
            self.stdout.write(self.style.ERROR(
                '❌ Missing credentials!\n\n'
                'Set environment variables:\n'
                '  SUPERUSER_BUSINESS_NAME=YourAdminName\n'
                '  SUPERUSER_EMAIL=admin@example.com\n'
                '  SUPERUSER_PASSWORD=YourSecurePassword\n\n'
                'Or pass as arguments:\n'
                '  python manage.py create_superuser --business-name "Admin" --email "admin@example.com" --password "pass123"\n'
            ))
            return
        
        # Create superuser
        User = get_user_model()
        
        if User.objects.filter(business_name=business_name).exists():
            # Update existing user password
            user = User.objects.get(business_name=business_name)
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'🔄 Password reset for "{business_name}"!'))
        else:
            # Create new superuser
            user = User.objects.create_superuser(
                business_name=business_name,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Superuser "{business_name}" created!'))
        
        # Print login info (without password)
        self.stdout.write(self.style.SUCCESS(
            f'\n'
            f'╔══════════════════════════════════════════════════╗\n'
            f'║  SUPERUSER READY                                 ║\n'
            f'╠══════════════════════════════════════════════════╣\n'
            f'║  Business Name: {business_name:<30} ║\n'
            f'║  Email:         {email:<30} ║\n'
            f'║  Password:      ******** (from env)              ║\n'
            f'╚══════════════════════════════════════════════════╝\n'
        ))