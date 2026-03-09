#!/usr/bin/env python
"""
create_staff_users.py - Create Staff Users for Each Role

Setup:
    1. Copy .env.example to .env
    2. Fill in your credentials in .env
    3. Run: python manage_roles.py
    4. Run: python create_staff_users.py
"""

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
from django.contrib.auth.models import Group
from customers.models import User
from django.db import transaction

# 4. Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will use os.environ directly


def get_env(key, default=None):
    """Get environment variable with optional default."""
    return os.environ.get(key, default)


def create_staff_user(business_name, email, password, name=None, phone=None, role_name=None):
    """
    Create a staff user and assign them to a role.
    """
    if not business_name or not email or not password:
        print(f"  ⚠️  Skipping: Missing required fields for {role_name or 'user'}")
        return None
    
    try:
        # Check if user already exists
        user = None
        try:
            user = User.objects.get(business_name=business_name)
            print(f"  🔄 Updating existing user: {business_name}")
        except User.DoesNotExist:
            try:
                user = User.objects.get(email=email)
                print(f"  🔄 Updating existing user (found by email): {email}")
            except User.DoesNotExist:
                pass
        
        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.phone = phone
            user.is_staff = True
            user.is_active = True
            user.set_password(password)
            user.save()
        else:
            # Create new user
            user = User.objects.create_user(
                business_name=business_name,
                email=email,
                password=password,
                name=name,
                phone=phone,
                is_staff=True,
                is_active=True,
            )
            print(f"  ✅ Created user: {business_name}")
        
        # Assign role
        if role_name:
            try:
                group = Group.objects.get(name=role_name)
                user.groups.add(group)
                print(f"     Assigned role: {role_name}")
            except Group.DoesNotExist:
                print(f"  ⚠️  Role '{role_name}' not found! Run manage_roles.py first.")
        
        return user
        
    except Exception as e:
        print(f"  ❌ Error creating {business_name}: {str(e)}")
        return None


@transaction.atomic
def create_all_staff_users():
    """Create staff users from environment variables."""
    
    print("\n" + "=" * 60)
    print("👥 ChiamoOrder - Creating Staff Users for Each Role")
    print("=" * 60 + "\n")
    
    # ============================================================
    # Staff users loaded from environment variables
    # Configure these in your .env file
    # ============================================================
    
    staff_users = [
        {
            'business_name': get_env('INVOICER_BUSINESS_NAME', 'ChiamoOrder Invoicing'),
            'email': get_env('INVOICER_EMAIL', 'invoicer@chiamoorder.com'),
            'password': get_env('INVOICER_PASSWORD'),
            'name': 'Invoice Admin',
            'role': 'InvoicerAdmin',
        },
        {
            'business_name': get_env('LOGISTICS_BUSINESS_NAME', 'ChiamoOrder Logistics'),
            'email': get_env('LOGISTICS_EMAIL', 'logistics@chiamoorder.com'),
            'password': get_env('LOGISTICS_PASSWORD'),
            'name': 'Logistics Admin',
            'role': 'LogisticsAdmin',
        },
        {
            'business_name': get_env('INVENTORY_BUSINESS_NAME', 'ChiamoOrder Inventory'),
            'email': get_env('INVENTORY_EMAIL', 'inventory@chiamoorder.com'),
            'password': get_env('INVENTORY_PASSWORD'),
            'name': 'Inventory Admin',
            'role': 'InventoryAdmin',
        },
        {
            'business_name': get_env('SUPPORT_BUSINESS_NAME', 'ChiamoOrder Support'),
            'email': get_env('SUPPORT_EMAIL', 'support@chiamoorder.com'),
            'password': get_env('SUPPORT_PASSWORD'),
            'name': 'Support Admin',
            'role': 'SupportAdmin',
        },
        {
            'business_name': get_env('FINANCE_BUSINESS_NAME', 'ChiamoOrder Finance'),
            'email': get_env('FINANCE_EMAIL', 'finance@chiamoorder.com'),
            'password': get_env('FINANCE_PASSWORD'),
            'name': 'Finance Admin',
            'role': 'FinanceAdmin',
        },
    ]
    
    # Check if passwords are configured
    missing_passwords = [u['role'] for u in staff_users if not u['password']]
    if missing_passwords:
        print("⚠️  WARNING: Some passwords are not configured in .env file!")
        print(f"   Missing: {', '.join(missing_passwords)}")
        print("\n   Please set these in your .env file:")
        print("   INVOICER_PASSWORD=YourSecurePassword")
        print("   LOGISTICS_PASSWORD=YourSecurePassword")
        print("   etc.\n")
    
    print("Creating staff users...\n")
    
    created_users = []
    for user_data in staff_users:
        if not user_data['password']:
            print(f"  ⏭️  Skipping {user_data['role']}: No password configured")
            print()
            continue
            
        user = create_staff_user(
            business_name=user_data['business_name'],
            email=user_data['email'],
            password=user_data['password'],
            name=user_data.get('name'),
            role_name=user_data['role'],
        )
        if user:
            created_users.append({
                'business_name': user_data['business_name'],
                'email': user_data['email'],
                'role': user_data['role'],
            })
        print()
    
    # Print results (without passwords!)
    print("\n" + "=" * 60)
    print("🔐 CREATED USERS")
    print("=" * 60)
    print(f"\nAdmin URL: /admin/")
    print("\n⚠️  Login with BUSINESS NAME, not email!")
    print("-" * 60)
    
    if created_users:
        for user in created_users:
            print(f"""
📧 Role: {user['role']}
   Business Name (Username): {user['business_name']}
   Email:                    {user['email']}
   Password:                 *** (from .env file)
            """)
        
        print("-" * 60)
        print(f"\n✅ Created {len(created_users)} staff user(s)")
    else:
        print("❌ No users were created. Check your .env file.")
    
    print("""
╔════════════════════════════════════════════════════════════╗
║  Passwords are stored in your .env file (not in Git!)     ║
║  Check .env for login credentials                          ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    return created_users


def create_single_staff_user():
    """Interactive mode to create a single staff user."""
    
    print("\n" + "=" * 50)
    print("👤 Create Single Staff User")
    print("=" * 50 + "\n")
    
    business_name = input("Business Name (used for login): ").strip()
    email = input("Email: ").strip()
    password = input("Password: ").strip()
    name = input("Full Name (optional): ").strip() or None
    
    print("\nAvailable roles:")
    print("  1. InvoicerAdmin   - Can manage Orders only")
    print("  2. LogisticsAdmin  - Can manage Orders & Customers")
    print("  3. InventoryAdmin  - Can manage Products & Categories")
    print("  4. SupportAdmin    - View all, change Orders")
    print("  5. FinanceAdmin    - View only (Reports)")
    print("  0. No role")
    
    role_map = {
        '1': 'InvoicerAdmin',
        '2': 'LogisticsAdmin',
        '3': 'InventoryAdmin',
        '4': 'SupportAdmin',
        '5': 'FinanceAdmin',
        '0': None,
    }
    
    role_choice = input("\nSelect role (0-5): ").strip()
    role_name = role_map.get(role_choice)
    
    user = create_staff_user(
        business_name=business_name,
        email=email,
        password=password,
        name=name,
        role_name=role_name
    )
    
    if user:
        print(f"\n✅ User created! Login at /admin/ with business name.")


def list_staff_users():
    """List all staff users."""
    
    print("\n" + "=" * 60)
    print("👥 All Staff Users")
    print("=" * 60 + "\n")
    
    staff_users = User.objects.filter(is_staff=True).order_by('business_name')
    
    if not staff_users:
        print("No staff users found.")
        return
    
    for user in staff_users:
        roles = [g.name for g in user.groups.all()]
        role_str = ", ".join(roles) if roles else "No roles"
        
        if user.is_superuser:
            role_str = "🔑 SUPERUSER"
        
        status = "✅" if user.is_active else "❌"
        
        print(f"{status} {user.business_name}")
        print(f"   Email: {user.email} | Roles: {role_str}")
        print()


def change_user_password(identifier, new_password):
    """Change password for a user."""
    try:
        try:
            user = User.objects.get(business_name=identifier)
        except User.DoesNotExist:
            user = User.objects.get(email=identifier)
        
        user.set_password(new_password)
        user.save()
        print(f"✅ Password changed for {user.business_name}")
        return True
    except User.DoesNotExist:
        print(f"❌ User not found: {identifier}")
        return False


def delete_staff_user(identifier):
    """Delete a staff user."""
    try:
        try:
            user = User.objects.get(business_name=identifier)
        except User.DoesNotExist:
            user = User.objects.get(email=identifier)
        
        if user.is_superuser:
            print(f"⚠️  Cannot delete superuser")
            return False
        
        confirm = input(f"Delete '{user.business_name}'? (yes/no): ")
        if confirm.lower() == 'yes':
            user.delete()
            print(f"✅ Deleted")
            return True
        print("Cancelled.")
        return False
        
    except User.DoesNotExist:
        print(f"❌ User not found: {identifier}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ChiamoOrder Staff User Management")
    parser.add_argument('-i', '--interactive', action='store_true', help='Create user interactively')
    parser.add_argument('-l', '--list', action='store_true', help='List staff users')
    parser.add_argument('--change-password', nargs=2, metavar=('USER', 'PASS'), help='Change password')
    parser.add_argument('--delete', metavar='USER', help='Delete user')
    
    args = parser.parse_args()
    
    if args.interactive:
        create_single_staff_user()
    elif args.list:
        list_staff_users()
    elif args.change_password:
        change_user_password(*args.change_password)
    elif args.delete:
        delete_staff_user(args.delete)
    else:
        create_all_staff_users()