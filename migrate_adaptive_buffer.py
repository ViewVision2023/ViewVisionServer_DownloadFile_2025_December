#!/usr/bin/env python3
"""
Database Migration Script - Add Adaptive Buffer Support
Adds adaptive buffer columns to routes table safely
"""
import sqlite3
import sys
import os

# Support both local and production paths
if os.path.exists('/opt/srt-gateway/gateway.db'):
    DB_PATH = '/opt/srt-gateway/gateway.db'
else:
    DB_PATH = 'gateway.db'

def migrate():
    print("🔄 Starting Adaptive Buffer migration...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(routes)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'adaptive_buffer_enabled' in columns:
            print("✅ Adaptive Buffer columns already exist. No migration needed.")
            conn.close()
            return True
        
        print("📝 Adding Adaptive Buffer columns to routes table...")
        
        # Add new columns with safe defaults
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN adaptive_buffer_enabled INTEGER DEFAULT 0
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN ab_weight_loss INTEGER DEFAULT 40
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN ab_weight_buffer INTEGER DEFAULT 30
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN ab_weight_jitter INTEGER DEFAULT 20
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN ab_weight_rtt INTEGER DEFAULT 10
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN ab_max_buffer_ms INTEGER DEFAULT 2000
        """)
        
        conn.commit()
        
        # Verify columns were added
        cursor.execute("PRAGMA table_info(routes)")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = [
            'adaptive_buffer_enabled',
            'ab_weight_loss',
            'ab_weight_buffer',
            'ab_weight_jitter',
            'ab_weight_rtt',
            'ab_max_buffer_ms'
        ]
        
        for col in expected_columns:
            if col not in new_columns:
                print(f"❌ Failed to add column: {col}")
                conn.close()
                return False
        
        print("✅ Successfully added all Adaptive Buffer columns:")
        print("   - adaptive_buffer_enabled (0=disabled, 1=enabled)")
        print("   - ab_weight_loss (default: 40%)")
        print("   - ab_weight_buffer (default: 30%)")
        print("   - ab_weight_jitter (default: 20%)")
        print("   - ab_weight_rtt (default: 10%)")
        print("   - ab_max_buffer_ms (default: 2000ms)")
        
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("💡 All existing routes have AB disabled by default")
        print("💡 Users can enable AB per-route in the UI")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def rollback():
    """
    Rollback function to remove AB columns if needed
    WARNING: This will lose AB configuration data
    """
    print("⚠️  ROLLBACK: Removing Adaptive Buffer columns...")
    print("⚠️  This cannot be undone and will lose AB configuration!")
    
    response = input("Type 'yes' to confirm rollback: ")
    if response.lower() != 'yes':
        print("❌ Rollback cancelled")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # SQLite doesn't support DROP COLUMN directly
        # We need to recreate the table without AB columns
        print("📝 Recreating routes table without AB columns...")
        
        # Get current table schema (excluding AB columns)
        cursor.execute("PRAGMA table_info(routes)")
        columns = cursor.fetchall()
        
        ab_columns = [
            'adaptive_buffer_enabled',
            'ab_weight_loss',
            'ab_weight_buffer',
            'ab_weight_jitter',
            'ab_weight_rtt',
            'ab_max_buffer_ms'
        ]
        
        # Filter out AB columns
        keep_columns = [col for col in columns if col[1] not in ab_columns]
        
        if len(keep_columns) == len(columns):
            print("✅ AB columns not found, nothing to rollback")
            conn.close()
            return True
        
        # Build column definitions
        col_defs = []
        col_names = []
        for col in keep_columns:
            col_names.append(col[1])
            col_def = f"{col[1]} {col[2]}"
            if col[3]:  # NOT NULL
                col_def += " NOT NULL"
            if col[4] is not None:  # DEFAULT
                col_def += f" DEFAULT {col[4]}"
            if col[5]:  # PRIMARY KEY
                col_def += " PRIMARY KEY"
            col_defs.append(col_def)
        
        # Create new table
        cursor.execute(f"""
            CREATE TABLE routes_new (
                {', '.join(col_defs)}
            )
        """)
        
        # Copy data
        cursor.execute(f"""
            INSERT INTO routes_new ({', '.join(col_names)})
            SELECT {', '.join(col_names)} FROM routes
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE routes")
        cursor.execute("ALTER TABLE routes_new RENAME TO routes")
        
        conn.commit()
        conn.close()
        
        print("✅ Rollback completed - AB columns removed")
        return True
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        success = rollback()
    else:
        success = migrate()
    
    sys.exit(0 if success else 1)
