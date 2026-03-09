from django.core.management.base import BaseCommand
from customers.models import User


class Command(BaseCommand):
    help = "Setup staff users for production"

    def handle(self, *args, **options):
        self.stdout.write("Setting up staff users...")

        staff_users = [
            ("ChiamoOrder Invoicing", "invoicer@chiamoorder.com", "Invoicer@2024"),
            ("ChiamoOrder Logistics", "logistics@chiamoorder.com", "Logistics@2024"),
            ("ChiamoOrder Inventory", "inventory@chiamoorder.com", "Inventory@2024"),
            ("ChiamoOrder Support", "support@chiamoorder.com", "Support@2024"),
            ("ChiamoOrder Finance", "finance@chiamoorder.com", "Finance@2024"),
        ]

        for business_name, email, password in staff_users:
            user, created = User.objects.get_or_create(
                business_name=business_name,
                defaults={"email": email, "is_staff": True, "is_active": True}
            )
            user.set_password(password)
            user.is_staff = True
            user.is_active = True
            user.save()
            status = "created" if created else "updated"
            self.stdout.write(f"  {business_name}: {status}")

        try:
            from axes.models import AccessAttempt
            AccessAttempt.objects.all().delete()
            self.stdout.write("  Login locks cleared")
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("Staff users ready!"))
