import sqlite3
import os
import subprocess
import sys

def revert_database():
    print("🔄 Reverting database to a clean seeded state...")
    
    # Path to the sqlite database
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(root_dir, 'backend', 'hvac_telemetry.db')
    
    if not os.path.exists(db_path):
        print(f"⚠️ Database not found at {db_path}. Assuming it's already clean.")
    else:
        try:
            # Connect and delete all rows to clear the fault data
            # Doing this directly avoids having to restart the FastAPI server!
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sensor_logs")
            conn.commit()
            conn.close()
            print("✅ Cleared all existing sensor logs.")
        except Exception as e:
            print(f"❌ Error clearing database: {e}")
            sys.exit(1)
            
    print("🌱 Re-seeding database with nominal baseline data...")
    try:
        seed_script = os.path.join(root_dir, 'backend', 'scripts', 'seed_database.py')
        subprocess.run(["py", seed_script], check=True)
        print("\n✅ Database successfully reverted and seeded!")
        print("👉 The React dashboard will automatically update on its next poll (no restart needed).")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to run seed script. Is the FastAPI backend running? ({e})")

if __name__ == "__main__":
    revert_database()
