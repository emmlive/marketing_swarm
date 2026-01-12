import sqlite3

def cleanup_demo_data():
    conn = sqlite3.connect('breatheeasy.db')
    cursor = conn.cursor()
    
    # This must match the team_id used in seed_data.py
    target_tag = "DEMO_DATA_INTERNAL"
    
    print(f"🧹 Commencing surgical purge of tag: {target_tag}...")
    
    # 1. Check how many records exist first
    cursor.execute("SELECT COUNT(*) FROM leads WHERE team_id = ?", (target_tag,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("✅ Clean: No demo data detected. Your real leads are safe.")
    else:
        # 2. Perform the deletion
        cursor.execute("DELETE FROM leads WHERE team_id = ?", (target_tag,))
        conn.commit()
        print(f"✨ Purge complete: {count} demo records removed from the system.")
    
    conn.close()

if __name__ == "__main__":
    cleanup_demo_data()
