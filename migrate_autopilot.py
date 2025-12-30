#!/usr/bin/env python3
"""
Database Migration Script - Add Autopilot Support
Adds autopilot columns to routes table safely
"""
import sqlite3
import sys

DB_PATH = '/opt/srt-gateway/gateway.db'

def migrate():
    print("🔄 Starting autopilot migration...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(routes)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'autopilot_enabled' in columns:
            print("✅ Autopilot columns already exist. No migration needed.")
            conn.close()
            return True
        
        print("📝 Adding autopilot columns to routes table...")
        
        # Add new columns with safe defaults
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN autopilot_enabled INTEGER DEFAULT 0
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN autopilot_min_latency INTEGER DEFAULT 400
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN autopilot_max_latency INTEGER DEFAULT 2000
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN autopilot_sensitivity TEXT DEFAULT 'moderate'
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN current_active_latency INTEGER
        """)
        
        cursor.execute("""
            ALTER TABLE routes ADD COLUMN autopilot_last_adjustment TIMESTAMP
        """)
        
        conn.commit()
        
        # Verify columns were added
        cursor.execute("PRAGMA table_info(routes)")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = [
            'autopilot_enabled',
            'autopilot_min_latency',
            'autopilot_max_latency',
            'autopilot_sensitivity',
            'current_active_latency',
            'autopilot_last_adjustment'
        ]
        
        for col in expected_columns:
            if col not in new_columns:
                print(f"❌ Failed to add column: {col}")
                conn.close()
                return False
        
        print("✅ Successfully added all autopilot columns:")
        print("   - autopilot_enabled (0=disabled, 1=enabled)")
        print("   - autopilot_min_latency (minimum latency in ms)")
        print("   - autopilot_max_latency (maximum latency in ms)")
        print("   - autopilot_sensitivity (conservative/moderate/responsive)")
        print("   - current_active_latency (currently active latency)")
        print("   - autopilot_last_adjustment (timestamp of last change)")
        
        print("\n📊 Updating existing routes...")
        # Set current_active_latency to match their configured latency
        cursor.execute("""
            UPDATE routes SET current_active_latency = latency
            WHERE current_active_latency IS NULL
        """)
        conn.commit()
        
        affected = cursor.rowcount
        print(f"✅ Updated {affected} existing routes")
        
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("💡 All existing routes default to Manual mode (autopilot disabled)")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
