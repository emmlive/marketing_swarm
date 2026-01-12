import sqlite3
from datetime import datetime, timedelta
import random

def seed_master_data():
    conn = sqlite3.connect('breatheeasy.db')
    cursor = conn.cursor()

    # 1. Ensure tables exist (matching your app.py schema)
    cursor.execute('''CREATE TABLE IF NOT EXISTS leads 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      date TEXT, 
                      user TEXT, 
                      industry TEXT, 
                      service TEXT, 
                      city TEXT, 
                      content TEXT, 
                      team_id TEXT, 
                      status TEXT DEFAULT 'Discovery')''')

    # 2. Sample Data Configuration
    industries = ["Solar", "HVAC", "Medical", "Legal", "Dental"]
    cities = ["Austin, TX", "Miami, FL", "Denver, CO", "Phoenix, AZ", "Chicago, IL"]
    services = ["Lead Gen Swarm", "SEO Domination", "Ad Hook Optimization", "GEO Mapping"]
    
    # CRITICAL: Using the safety tag for targeted cleanup later
    test_user = "admin" 
    test_team = "DEMO_DATA_INTERNAL" 

    print(f"🚀 Seeding Master Data with Safety Tag: {test_team}...")

    # 3. Generate 10 diverse leads
    for i in range(1, 11):
        # Stagger dates over the last 30 days for visual variety
        past_date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d %H:%M:%S")
        
        ind = random.choice(industries)
        city = random.choice(cities)
        svc = random.choice(services)
        
        # Distribute statuses across the Kanban Board
        if i <= 3:
            stat = "Discovery"
        elif i <= 7:
            stat = "Execution"
        else:
            stat = "ROI Verified"

        # Mimicking the structured output format for better UI rendering
        sample_content = f"""
        ### 📊 Market Intelligence for {ind}
        - **Market Entry Gap:** High demand in {city} for specialized {svc}.
        - **Competitor Weakness:** Rivals failing on mobile UX and GEO citation velocity.
        - **Strategy:** Deploy Omni-channel hooks focusing on 'Urgency' and 'Authority'.
        """

        cursor.execute("""
            INSERT INTO leads (date, user, industry, service, city, content, team_id, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (past_date, test_user, ind, svc, city, sample_content, test_team, stat))

    conn.commit()
    conn.close()
    print("✅ Success! 10 High-Value Leads injected. Your Kanban board is now 'Investor Ready'.")

if __name__ == "__main__":
    seed_master_data()
