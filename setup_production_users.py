#!/usr/bin/env python
"""
setup_production_users.py - Connect directly to Railway PostgreSQL and create users
"""

import sys
import os

if len(sys.argv) < 2:
    print("Usage: python setup_production_users.py \"your_database_url\"")
    sys.exit(1)

DATABASE_URL = sys.argv[1]

print("\n" + "=" * 60)
print("🚀 CONNECTING TO RAILWAY POSTGRESQL")
print("=" * 60)

try:
    import psycopg2
except ImportError:
    os.system("pip install psycopg2-binary")
    import psycopg2

import hashlib
import base64
import secrets

def make_password(password):
    """Create Django-compatible password hash."""
    algorithm = "pbkdf2_sha256"
    iterations = 720000
    salt = secrets.token_hex(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
    return f"{algorithm}${iterations}${salt}${hash_b64}"

try:
    print(f"\nConnecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    print("✅ Connected successfully!\n")

    # First, let's check the table structure
    print("Checking table structure...")
    cursor.execute("""
        SELECT column_name, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'customers_user'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    print("Columns in customers_user table:")
    for col in columns:
        print(f"  - {col[0]} (nullable: {col[1]}, default: {col[2]})")
    
    print("\n" + "-" * 60)

    # Staff users to create
    staff_users = [
        ("ChiamoOrder Invoicing", "invoicer@chiamoorder.com", "Invoicer@2024"),
        ("ChiamoOrder Logistics", "logistics@chiamoorder.com", "Logistics@2024"),
        ("ChiamoOrder Inventory", "inventory@chiamoorder.com", "Inventory@2024"),
        ("ChiamoOrder Support", "support@chiamoorder.com", "Support@2024"),
        ("ChiamoOrder Finance", "finance@chiamoorder.com", "Finance@2024"),
    ]

    print("\nCreating/Updating staff users...")
    print("-" * 60)

    for business_name, email, password in staff_users:
        hashed_password = make_password(password)
        
        # Check if user exists
        cursor.execute(
            "SELECT id FROM customers_user WHERE business_name = %s",
            (business_name,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing user
            cursor.execute("""
                UPDATE customers_user 
                SET password = %s, 
                    is_staff = TRUE, 
                    is_active = TRUE,
                    email = %s
                WHERE business_name = %s
            """, (hashed_password, email, business_name))
            print(f"  🔄 {business_name}: Updated")
        else:
            # Insert new user with all required fields
            cursor.execute("""
                INSERT INTO customers_user 
                (
                    business_name, 
                    email, 
                    password, 
                    is_staff, 
                    is_active, 
                    is_superuser,
                    theme,
                    has_pin,
                    pin_attempts,
                    timestamp
                )
                VALUES (%s, %s, %s, TRUE, TRUE, FALSE, 'light', FALSE, 0, NOW())
            """, (business_name, email, hashed_password))
            print(f"  ✅ {business_name}: Created")

    # Clear login locks
    print("\nClearing login locks...")
    try:
        cursor.execute("DELETE FROM axes_accessattempt")
        print("  ✅ Login locks cleared")
    except Exception as e:
        print(f"  ⚠️ Could not clear locks: {e}")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ ALL DONE!")
    print("=" * 60)
    print("""
┌─────────────────────────────┬─────────────────────┐
│ Username (Business Name)    │ Password            │
├─────────────────────────────┼─────────────────────┤
│ ChiamoOrder Invoicing       │ Invoicer@2024       │
│ ChiamoOrder Logistics       │ Logistics@2024      │
│ ChiamoOrder Inventory       │ Inventory@2024      │
│ ChiamoOrder Support         │ Support@2024        │
│ ChiamoOrder Finance         │ Finance@2024        │
└─────────────────────────────┴─────────────────────┘

Now try logging in at:
https://web-production-04707.up.railway.app/admin/
    """)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)