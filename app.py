import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from main import run_marketing_swarm 
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from PIL import Image

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise Swarm", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, logo_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

# --- 4. CORE DATABASE FUNCTIONS ---
def log_action(admin_user, action, target_user, details=""):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.cursor().execute("INSERT INTO audit_logs (timestamp, admin_user, action, target_user, details) VALUES (?, ?, ?, ?, ?)",
                          (timestamp, admin_user, action, target_user, details))
    conn.commit(); conn.close()

def update_user_package(username, new_package, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET package = ? WHERE username = ?", (new_package, username))
    conn.commit(); conn.close()
    log_action(admin_name, "UPDATE_TIER", username, f"Changed to {new_package}")

def delete_user(username, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    conn.cursor().execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit(); conn.close()
    log_action(admin_name, "DELETE_USER", username, "Permanently removed user")

def save_lead_to_db(user, industry, service, city, content):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?, ?, ?, ?, ?, ?)",
                          (date_str, user, industry, service, city, content))
    conn.commit(); conn.close()

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    u_dict = {'usernames': {}}
    for _, row in df.iterrows():
        u_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'],
            'package': row.get('package', 'Basic'), 'logo_path': row.get('logo_path')
        }
    return u_dict

# --- 5. REPORTING & UTILITIES ---
def send_admin_alert(subject, body):
    msg = MIMEMultipart(); msg["From"] = st.secrets["EMAIL_SENDER"]; msg["To"] = st.secrets["TEAM_EMAIL"]; msg["Subject"] = f"🔔 {subject}"
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(st.secrets["EMAIL_SENDER"], st.secrets["EMAIL_PASSWORD"])
            s.sendmail(st.secrets["EMAIL_SENDER"], st.secrets["TEAM_EMAIL"], msg.as_string())
        return True
    except: return False

def create_word_doc(content, logo_path=None):
    doc = Document()
    if logo_path and os.path.exists(logo_path): doc.add_picture(logo_path, width=Inches(1.5))
    doc.add_heading('BreatheEasy AI Strategy Report', 0)
    for line in content.split('\n'): doc.add_paragraph(line)
    bio = BytesIO(); doc.save(bio); return bio.getvalue()

def create_pdf(content, service, city, logo_path=None):
    pdf = FPDF(); pdf.add_page()
    if logo_path and os.path.exists(logo_path): pdf.image(logo_path, 10, 8, 33); pdf.ln(20)
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, 'Marketing Strategy Report', 0, 1, 'C')
    pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
    pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

init_db()

# --- 6. UI STYLING & MOCKUP CSS ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_blue = "#0056b3"
st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    .stApp {{ background-color: #F8F9FB; }}
    .stApp::before {{
        content: ""; display: block; margin: 30px auto 0; width: 140px; height: 140px;
        background-image: url("{logo_url}"); background-size: contain; background-repeat: no-repeat;
    }}
    .tier-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; background: {brand_blue}; color: white; }}
    .pricing-card {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: white; }}
    .feature-card {{ background: white; padding: 25px; border-radius: 12px; border: 1px solid #e0e0e0; text-align: center; }}
    /* SOCIAL MOCKUP CSS */
    .mockup-container {{ background: white; border: 1px solid #ddd; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); max-width: 500px; margin: auto; }}
    .mockup-header {{ display: flex; align-items: center; margin-bottom: 12px; }}
    .profile-pic {{ width: 42px; height: 42px; border-radius: 50%; background: #f0f2f5; margin-right: 12px; }}
    .profile-name {{ font-weight: 700; font-size: 14px; color: #1c1e21; }}
    .mockup-text {{ font-size: 14px; color: #1c1e21; margin-bottom: 12px; line-height: 1.5; }}
    .mockup-image {{ width: 100%; height: 250px; background: #f0f2f5; border-radius: 8px; border: 1px dashed #ccc; display: flex; align-items: center; justify-content: center; color: #90949c; text-align: center; padding: 10px; }}
    .fb-btn-row {{ display: flex; justify-content: space-around; border-top: 1px solid #eee; margin-top: 10px; padding-top: 8px; color: #606770; font-size: 13px; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

# --- 7. AUTHENTICATION & LANDING ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])
authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.markdown("<h1 style='text-align: center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.markdown('<div class="feature-card"><h3>🐝 Swarm</h3><p>5 agents working in sync.</p></div>', unsafe_allow_html=True)
    col2.markdown('<div class="feature-card"><h3>📈 Niches</h3><p>HVAC, Solar, Restoration.</p></div>', unsafe_allow_html=True)
    col3.markdown('<div class="feature-card"><h3>📄 Export</h3><p>Branded PDF & Word.</p></div>', unsafe_allow_html=True)
    with st.expander("New User? Register Here"):
        res = authenticator.register_user(pre_authorization=False)
        if res:
            email, username, name = res
            if email:
                db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                                      (username, email, name, db_ready_pw, 'member', 'Basic'))
                conn.commit(); conn.close(); st.success('✅ Registered! Please login.'); st.rerun()
    st.stop()

# --- 8. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_users_from_db()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

    PACKAGE_CONFIG = {
        "Basic": {"industries": ["HVAC", "Plumbing"], "blog": False, "branding": False},
        "Pro": {"industries": ["HVAC", "Plumbing", "Restoration", "Roofing"], "blog": True, "branding": True},
        "Unlimited": {"industries": ["HVAC", "Plumbing", "Restoration", "Roofing", "Solar", "Custom"], "blog": True, "branding": True}
    }

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        if PACKAGE_CONFIG[user_tier]["branding"]:
            with st.expander("🎨 Custom Branding"):
                logo_file = st.file_uploader("Upload Logo", type=['png', 'jpg'])
                if logo_file:
                    os.makedirs("logos", exist_ok=True)
                    user_logo = f"logos/{username}.png"
                    with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                    conn.commit(); conn.close(); st.success("Logo Branded!")

        st.subheader("🎯 Settings")
        full_map = {"HVAC": ["Replacement", "IAQ"], "Plumbing": ["Sewer", "Heaters"], "Restoration": ["Mold", "Water"], "Roofing": ["Roof", "Repair"], "Solar": ["Install"], "Custom": ["Manual"]}
        allowed = PACKAGE_CONFIG[user_tier]["industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")
        include_blog = st.toggle("📝 SEO Blog", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    tabs = st.tabs(["🔥 Launchpad", "📊 History", "📱 Social Preview", "💎 Pricing", "🛠️ Admin" if username == "admin" else "ℹ️ Support"])

    with tabs[0]: # Launchpad
        if run_button and city_input:
            with st.spinner("Swarm Coordinating..."):
                run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': True, 'blog': include_blog})
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                st.session_state['ad_copy'] = content
                st.session_state['generated'] = True
                save_lead_to_db(username, main_cat, target_service, city_input, content)
        
        if st.session_state.get('generated'):
            copy = st.session_state['ad_copy']
            c1, c2 = st.columns(2)
            c1.download_button("📥 Word", create_word_doc(copy, user_logo), f"{city_input}.docx", use_container_width=True)
            c2.download_button("📕 PDF", create_pdf(copy, target_service, city_input, user_logo), f"{city_input}.pdf", use_container_width=True)
            st.markdown(copy)

    with tabs[2]: # SOCIAL PREVIEW MOCKUP
        if st.session_state.get('generated'):
            st.subheader("📱 Facebook Ad Mockup")
            st.link_button("🔵 Open Meta Business Suite", "https://business.facebook.com/latest/composer", use_container_width=True)
            st.divider()
            
            ad_content = st.session_state['ad_copy'][:400] + "..."
            
            st.markdown(f"""
                <div class="mockup-container">
                    <div class="mockup-header">
                        <div class="profile-pic"></div>
                        <div>
                            <div class="profile-name">BreatheEasy {main_cat}</div>
                            <div style="font-size: 12px; color: #65676b;">Sponsored · 🌐</div>
                        </div>
                    </div>
                    <div class="mockup-text">{ad_content}</div>
                    <div class="mockup-image">
                        <b>[AI Visual: {target_service}]</b><br>
                        High-Resolution photorealistic scene for {city_input}
                    </div>
                    <div style="padding: 10px; background: #f0f2f5; border-top: 1px solid #ddd;">
                        <div style="font-size: 12px; color: #65676b;">WWW.BREATHEEASY.AI</div>
                        <div style="font-weight: bold; font-size: 16px;">Premium {target_service} in {city_input}</div>
                    </div>
                    <div class="fb-btn-row">
                        <span>👍 Like</span><span>💬 Comment</span><span>🔗 Share</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("💡 Please generate a strategy in the Launchpad tab to view social mockups.")

    with tabs[3]: # Pricing
        p1, p2, p3 = st.columns(3)
        p1.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$0</h1><p>2 Industries<br>No Branding</p></div>', unsafe_allow_html=True)
        p2.markdown('<div class="pricing-card" style="border:2px solid #0056b3;"><h3>Pro</h3><h1>$49</h1><p>4 Industries<br>✅ Branding</p></div>', unsafe_allow_html=True)
        p3.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$99</h1><p>All Niches<br>Priority AI</p></div>', unsafe_allow_html=True)

    if username == "admin":
        with tabs[-1]:
            # Admin Management Logic
            st.write("Admin Control Panel Active")
