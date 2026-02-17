#!/usr/bin/env python
import os
import sys
import django

# 1. Force Django to use your settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chiamo_project.settings')

# 2. Setup Django before importing any models
django.setup()

# 3. Now you can import Django stuff safely
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from orders.models import Order
from customers.models import User

# === Create Groups (Roles) ===
def create_roles():
    # Create groups if they don't exist
    invoicer_group, _ = Group.objects.get_or_create(name="InvoicerAdmin")
    logistics_group, _ = Group.objects.get_or_create(name="LogisticsAdmin")

    # Get content types
    order_ct = ContentType.objects.get_for_model(Order)
    user_ct = ContentType.objects.get_for_model(User)

    # --- InvoicerAdmin: can ONLY view and edit orders ---
    invoicer_perms = Permission.objects.filter(content_type=order_ct)
    invoicer_group.permissions.set(invoicer_perms)

    # --- LogisticsAdmin: can view/edit orders + customers ---
    logistics_perms = list(Permission.objects.filter(content_type=order_ct)) + list(
        Permission.objects.filter(content_type=user_ct)
    )
    logistics_group.permissions.set(logistics_perms)

    print("✅ Roles created successfully:")
    print(" - InvoicerAdmin (can manage Orders)")
    print(" - LogisticsAdmin (can manage Orders & Customers)")

if __name__ == "__main__":
    create_roles()
