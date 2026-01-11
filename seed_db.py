import sqlite3
import random
from datetime import datetime, timedelta

def seed_history():
    conn = sqlite3.connect('breatheeasy.db')
    c = conn.cursor()

    # Configuration for realistic mock data
    industries = ["HVAC", "Plumbing", "Medical", "Solar", "Law Firm", "Restoration"]
    services = {
        "HVAC": ["AC Replacement", "Duct Cleaning", "IAQ Audit"],
        "Plumbing": ["Sewer Repair", "Tankless Install", "Repiping"],
        "Medical": ["Dental Implants", "Patient Acquisition", "Clinic Branding"],
        "Solar": ["Residential Grid", "Battery Backup"],
        "Law Firm": ["Personal Injury", "Estate Planning"],
        "Restoration": ["Mold Remediation", "Water Damage"]
    }
    cities = ["Chicago", "Naperville", "Aurora", "Evanston", "Joliet", "Oak Park"]

    print("🌱 Seeding 50 mock leads into 'leads' table...")

    for i in range(50):
        # Generate a random date within the last 30 days
        random_days = random.randint(0, 30)
        date_obj = datetime.now() - timedelta(days=random_days)
        date_str = date_obj.strftime("%Y-%m-%d")

        industry = random.choice(industries)
        service = random.choice(services[industry])
        city = random.choice(cities)
        
        # Mock content summary
        content = f"### Swarm Report for {service}\nPhase 1: Research complete for {city}.\nPhase 2: 3 Ad variants generated.\nPhase 3: GBP and Reddit posts localized."

        c.execute('''INSERT INTO leads (date, user, industry, service, city, content) 
                     VALUES (?, ?, ?, ?, ?, ?)''', 
                  (date_str, 'admin', industry, service, city, content))

    # Also, let's give the admin plenty of credits for the demo
    c.execute("UPDATE users SET credits = 9999 WHERE username = 'admin'")

    conn.commit()
    conn.close()
    print("✅ Database successfully seeded. The History and Database tabs will now look full!")

if __name__ == "__main__":
    seed_history()
