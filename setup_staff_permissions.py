#!/usr/bin/env python
"""
setup_staff_permissions.py - Setup proper permissions for staff users

Run AFTER setup_production_users.py:
    python setup_staff_permissions.py "your_database_url"
"""

import sys

if len(sys.argv) < 2:
    print("Usage: python setup_staff_permissions.py \"your_database_url\"")
    sys.exit(1)

DATABASE_URL = sys.argv[1]

import psycopg2

print("\n" + "=" * 60)
print("🔧 SETTING UP STAFF PERMISSIONS")
print("=" * 60)

try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cursor = conn.cursor()
    print("✅ Connected!\n")

    # ============ CREATE GROUPS/ROLES ============
    print("1️⃣ Creating permission groups...")
    
    groups = ["InvoicerAdmin", "LogisticsAdmin", "InventoryAdmin", "SupportAdmin", "FinanceAdmin"]
    
    for group_name in groups:
        cursor.execute("SELECT id FROM auth_group WHERE name = %s", (group_name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO auth_group (name) VALUES (%s)", (group_name,))
            print(f"   ✅ Created group: {group_name}")
        else:
            print(f"   🔄 Group exists: {group_name}")

    # ============ GET GROUP IDs ============
    cursor.execute("SELECT id, name FROM auth_group")
    group_ids = {row[1]: row[0] for row in cursor.fetchall()}
    print(f"\n   Groups: {group_ids}")

    # ============ GET CONTENT TYPE IDs ============
    print("\n2️⃣ Getting content types...")
    
    cursor.execute("""
        SELECT id, app_label, model 
        FROM django_content_type 
        WHERE (app_label = 'orders' AND model = 'order')
           OR (app_label = 'orders' AND model = 'orderitem')
           OR (app_label = 'customers' AND model = 'user')
           OR (app_label = 'customers' AND model = 'address')
           OR (app_label = 'products' AND model = 'product')
           OR (app_label = 'products' AND model = 'category')
    """)
    content_types = {f"{row[1]}.{row[2]}": row[0] for row in cursor.fetchall()}
    print(f"   Content types: {content_types}")

    # ============ GET PERMISSION IDs ============
    print("\n3️⃣ Getting permissions...")
    
    cursor.execute("""
        SELECT id, codename, content_type_id 
        FROM auth_permission
    """)
    all_permissions = cursor.fetchall()
    
    # Build permission lookup
    perm_lookup = {}
    for perm_id, codename, ct_id in all_permissions:
        perm_lookup[(ct_id, codename)] = perm_id

    # ============ ASSIGN PERMISSIONS TO GROUPS ============
    print("\n4️⃣ Assigning permissions to groups...")

    def add_perm_to_group(group_name, content_type_key, actions):
        """Helper function to add permission to group."""
        if content_type_key not in content_types:
            print(f"   ⚠️ Content type not found: {content_type_key}")
            return
        
        ct_id = content_types[content_type_key]
        group_id = group_ids.get(group_name)
        
        if not group_id:
            print(f"   ⚠️ Group not found: {group_name}")
            return
        
        model_name = content_type_key.split('.')[1]
        
        for action in actions:
            codename = f"{action}_{model_name}"
            perm_id = perm_lookup.get((ct_id, codename))
            
            if perm_id:
                cursor.execute("""
                    SELECT 1 FROM auth_group_permissions 
                    WHERE group_id = %s AND permission_id = %s
                """, (group_id, perm_id))
                
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO auth_group_permissions (group_id, permission_id)
                        VALUES (%s, %s)
                    """, (group_id, perm_id))

    # ===== INVOICER ADMIN =====
    add_perm_to_group("InvoicerAdmin", "orders.order", ["view", "change"])
    add_perm_to_group("InvoicerAdmin", "orders.orderitem", ["view"])
    print("   ✅ InvoicerAdmin: View/Change Orders")

    # ===== LOGISTICS ADMIN =====
    add_perm_to_group("LogisticsAdmin", "orders.order", ["view", "change"])
    add_perm_to_group("LogisticsAdmin", "orders.orderitem", ["view"])
    add_perm_to_group("LogisticsAdmin", "customers.user", ["view"])
    add_perm_to_group("LogisticsAdmin", "customers.address", ["view"])
    print("   ✅ LogisticsAdmin: View/Change Orders, View Customers/Addresses")

    # ===== INVENTORY ADMIN =====
    add_perm_to_group("InventoryAdmin", "products.product", ["view", "add", "change", "delete"])
    add_perm_to_group("InventoryAdmin", "products.category", ["view", "add", "change", "delete"])
    add_perm_to_group("InventoryAdmin", "orders.order", ["view"])
    print("   ✅ InventoryAdmin: Full Products/Categories, View Orders")

    # ===== SUPPORT ADMIN =====
    add_perm_to_group("SupportAdmin", "orders.order", ["view", "change"])
    add_perm_to_group("SupportAdmin", "orders.orderitem", ["view"])
    add_perm_to_group("SupportAdmin", "customers.user", ["view"])
    add_perm_to_group("SupportAdmin", "customers.address", ["view"])
    print("   ✅ SupportAdmin: View/Change Orders, View Customers")

    # ===== FINANCE ADMIN =====
    add_perm_to_group("FinanceAdmin", "orders.order", ["view"])
    add_perm_to_group("FinanceAdmin", "orders.orderitem", ["view"])
    add_perm_to_group("FinanceAdmin", "customers.user", ["view"])
    print("   ✅ FinanceAdmin: View Only")

    # ============ ASSIGN USERS TO GROUPS ============
    print("\n5️⃣ Assigning users to groups...")

    user_groups = {
        "ChiamoOrder Invoicing": "InvoicerAdmin",
        "ChiamoOrder Logistics": "LogisticsAdmin",
        "ChiamoOrder Inventory": "InventoryAdmin",
        "ChiamoOrder Support": "SupportAdmin",
        "ChiamoOrder Finance": "FinanceAdmin",
    }

    for business_name, group_name in user_groups.items():
        cursor.execute("SELECT id FROM customers_user WHERE business_name = %s", (business_name,))
        user_row = cursor.fetchone()
        
        if not user_row:
            print(f"   ⚠️ User not found: {business_name}")
            continue
        
        user_id = user_row[0]
        group_id = group_ids.get(group_name)
        
        if not group_id:
            continue
        
        cursor.execute("""
            SELECT 1 FROM customers_user_groups 
            WHERE user_id = %s AND group_id = %s
        """, (user_id, group_id))
        
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO customers_user_groups (user_id, group_id)
                VALUES (%s, %s)
            """, (user_id, group_id))
            print(f"   ✅ {business_name} → {group_name}")
        else:
            print(f"   🔄 {business_name} already in {group_name}")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ PERMISSIONS SETUP COMPLETE!")
    print("=" * 60)
    print("""
Staff users can now access:

┌─────────────────────────┬──────────────────────────────────────────────────────────┐
│ Role                    │ Access                                                   │
├─────────────────────────┼──────────────────────────────────────────────────────────┤
│ InvoicerAdmin           │ View Orders, Change status: confirmed → processing ONLY │
│ LogisticsAdmin          │ View Orders/Customers, Change: processing → delivered   │
│ InventoryAdmin          │ Full Products/Categories, View Orders                   │
│ SupportAdmin            │ View/Change Orders, View Customers                      │
│ FinanceAdmin            │ View Only (Reports)                                     │
└─────────────────────────┴──────────────────────────────────────────────────────────┘

Try logging in again!
    """)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()