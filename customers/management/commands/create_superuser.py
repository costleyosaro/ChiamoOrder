from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create default superuser'

    def handle(self, *args, **options):
        User = get_user_model()
        
        business_name = 'costley'
        email = 'costleyosaro4@gmail.com'
        password = 'Osayi@12!'
        
        if not User.objects.filter(business_name=business_name).exists():
            User.objects.create_superuser(
                business_name=business_name,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'Superuser "{business_name}" created!'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser "{business_name}" already exists.'))