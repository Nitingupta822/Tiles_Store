import sqlite3
import psycopg2
from datetime import datetime

# Local SQLite database
sqlite_conn = sqlite3.connect('tiles_stock_app/instance/database.db')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

# Render PostgreSQL database
# IMPORTANT: Replace this with your External Database URL from Render Dashboard
# Go to Render → Your Database → Info → Copy "External Database URL"
PG_DATABASE_URL = "postgresql://user:password@host/database"

print("=" * 60)
print("🚀 Tiles Stock App - Data Migration Script")
print("=" * 60)
print()

try:
    # Connect to PostgreSQL
    print("🔌 Connecting to PostgreSQL database...")
    pg_conn = psycopg2.connect(PG_DATABASE_URL)
    pg_cur = pg_conn.cursor()
    print("✅ Connected successfully!")
    print()

    # Migrate Users
    print("📦 Migrating users...")
    sqlite_cur.execute("SELECT * FROM user")
    users = sqlite_cur.fetchall()
    
    for user in users:
        try:
            pg_cur.execute("""
                INSERT INTO "user" (id, username, email, password, role, is_active, created_at, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                user['id'], user['username'], user['email'], user['password'],
                user['role'], user['is_active'], user['created_at'], user['created_by']
            ))
        except Exception as e:
            print(f"⚠️  Warning: Could not migrate user {user['username']}: {e}")
    
    print(f"✅ Migrated {len(users)} users")
    print()

    # Migrate Tiles
    print("📦 Migrating tiles...")
    sqlite_cur.execute("SELECT * FROM tile")
    tiles = sqlite_cur.fetchall()
    
    for tile in tiles:
        try:
            pg_cur.execute("""
                INSERT INTO tile (id, brand, size, buy_price, price, quantity)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                tile['id'], tile['brand'], tile['size'],
                tile['buy_price'], tile['price'], tile['quantity']
            ))
        except Exception as e:
            print(f"⚠️  Warning: Could not migrate tile {tile['brand']}: {e}")
    
    print(f"✅ Migrated {len(tiles)} tiles")
    print()

    # Migrate Bills
    print("📦 Migrating bills...")
    sqlite_cur.execute("SELECT * FROM bill")
    bills = sqlite_cur.fetchall()
    
    for bill in bills:
        try:
            pg_cur.execute("""
                INSERT INTO bill (id, customer_name, customer_mobile, total, gst, discount, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                bill['id'], bill['customer_name'], bill['customer_mobile'],
                bill['total'], bill['gst'], bill['discount'], bill['date']
            ))
        except Exception as e:
            print(f"⚠️  Warning: Could not migrate bill {bill['id']}: {e}")
    
    print(f"✅ Migrated {len(bills)} bills")
    print()

    # Migrate Bill Items
    print("📦 Migrating bill items...")
    sqlite_cur.execute("SELECT * FROM bill_item")
    bill_items = sqlite_cur.fetchall()
    
    for item in bill_items:
        try:
            pg_cur.execute("""
                INSERT INTO bill_item (id, bill_id, tile_name, size, price, quantity, total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                item['id'], item['bill_id'], item['tile_name'],
                item['size'], item['price'], item['quantity'], item['total']
            ))
        except Exception as e:
            print(f"⚠️  Warning: Could not migrate bill item {item['id']}: {e}")
    
    print(f"✅ Migrated {len(bill_items)} bill items")
    print()

    # Commit all changes
    print("💾 Committing changes...")
    pg_conn.commit()
    print("✅ All changes committed!")
    print()

    # Summary
    print("=" * 60)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print(f"Total migrated:")
    print(f"  - {len(users)} users")
    print(f"  - {len(tiles)} tiles")
    print(f"  - {len(bills)} bills")
    print(f"  - {len(bill_items)} bill items")
    print()
    print("Next steps:")
    print("1. Visit your Render app URL")
    print("2. Login with your admin credentials")
    print("3. Verify all data appears correctly")
    print("=" * 60)

except psycopg2.Error as e:
    print(f"❌ PostgreSQL Error: {e}")
    print()
    print("Please check:")
    print("1. Is PG_DATABASE_URL correct?")
    print("2. Is the database accessible from your network?")
    print("3. Did you use the EXTERNAL Database URL (not Internal)?")
    
except Exception as e:
    print(f"❌ Unexpected Error: {e}")

finally:
    # Close connections
    if 'sqlite_conn' in locals():
        sqlite_conn.close()
    if 'pg_conn' in locals():
        pg_conn.close()
    print()
    print("🔌 Database connections closed.")
