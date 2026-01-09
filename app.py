import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI | Enterprise", page_icon="🌬️", layout="wide")

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT)''')
    # NEW: Audit Logs Table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, admin_user TEXT, action TEXT, target_user TEXT, details TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                  ('admin', 'admin@breatheeasy.ai', 'System Admin', hashed_pw, 'admin', 'Unlimited'))
    conn.commit()
    conn.close()

def log_action(admin_user, action, target_user, details=""):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO audit_logs (timestamp, admin_user, action, target_user, details) VALUES (?, ?, ?, ?, ?)",
              (timestamp, admin_user, action, target_user, details))
    conn.commit()
    conn.close()

def update_user_package(username, new_package, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # Fetch old package for logging
    c.execute("SELECT package FROM users WHERE username = ?", (username,))
    old_package = c.fetchone()[0]
    
    c.execute("UPDATE users SET package = ? WHERE username = ?", (new_package, username))
    conn.commit()
    conn.close()
    log_action(admin_name, "UPDATE_TIER", username, f"Changed from {old_package} to {new_package}")

def delete_user(username, admin_name):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    log_action(admin_name, "DELETE_USER", username, "Permanently removed user account")

def get_users_from_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    user_dict = {'usernames': {}}
    for _, row in df.iterrows():
        user_dict['usernames'][row['username']] = {
            'email': row['email'], 'name': row['name'], 'password': row['password'],
            'package': row.get('package', 'Basic')
        }
    return user_dict

def save_lead_to_db(user, industry, service, city, content):
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?, ?, ?, ?, ?, ?)",
              (date_str, user, industry, service, city, content))
    conn.commit()
    conn.close()

init_db()

# --- 4. SaaS UI STYLING ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_blue = "#0056b3"
brand_bg = "#F8F9FB" 

st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"], .stAppDeployButton, footer, #stDecoration {{ display: none !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 30px auto 0; width: 140px; height: 140px;
        background-image: url("{logo_url}"); background-size: contain; background-repeat: no-repeat;
    }}
    .block-container {{ padding-top: 1.5rem !important; }}
    .tier-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; background: {brand_blue}; color: white; }}
    .pricing-card {{ border: 1px solid #ddd; padding: 20px; border-radius: 10px; text-align: center; background: white; height: 100%; }}
    .admin-card {{ border-left: 5px solid {brand_blue}; background: white; padding: 15px; border-radius: 5px; margin-bottom: 10px; }}
    </style>
""", unsafe_allow_html=True)

# --- 5. AUTHENTICATION ---
db_credentials = get_users_from_db()
authenticator = stauth.Authenticate(
    db_credentials, st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days']
)

authenticator.login(location='main')

if st.session_state["authentication_status"] is None:
    st.warning('Welcome. Please login.')
    with st.expander("New User? Register Here"):
        try:
            res = authenticator.register_user(pre_authorization=False)
            if res:
                email, username, name = res
                if email:
                    db_ready_pw = stauth.Hasher.hash(authenticator.credentials['usernames'][username]['password'])
                    # Initial package creation is NOT an admin action, so we don't log it here (or you can if you wish)
                    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
                    c = conn.cursor()
                    c.execute("INSERT INTO users (username, email, name, password, role, package) VALUES (?, ?, ?, ?, ?, ?)",
                              (username, email, name, db_ready_pw, 'member', 'Basic'))
                    conn.commit()
                    conn.close()
                    st.success('✅ Registered! Login to start your Basic plan.')
                    st.rerun()
        except Exception as e: st.error(e)
    st.stop()

# --- 6. PROTECTED DASHBOARD ---
if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    current_db_data = get_users_from_db()
    user_tier = current_db_data['usernames'][username].get('package', 'Basic')

    PACKAGE_CONFIG = {
        "Basic": {"allowed_industries": ["HVAC", "Plumbing"], "blog": False, "max_files": 1},
        "Pro": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing"], "blog": True, "max_files": 5},
        "Unlimited": {"allowed_industries": ["HVAC", "Plumbing", "Restoration", "Roofing", "Solar", "Custom"], "blog": True, "max_files": 20}
    }

    # Helper Functions
    def create_word_doc(content):
        doc = Document(); doc.add_heading('BreatheEasy AI Strategy', 0)
        for line in content.split('\n'): doc.add_paragraph(line)
        bio = BytesIO(); doc.save(bio); return bio.getvalue()

    def create_pdf(content, service, city):
        pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", 'B', 15)
        pdf.cell(0, 10, 'BreatheEasy AI Strategy Report', 0, 1, 'C')
        pdf.set_font("Arial", size=11); clean = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, txt=clean); return pdf.output(dest='S').encode('latin-1')

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        if user_tier == "Basic":
            with st.expander("🎟️ Redeem Coupon"):
                coupon_code = st.text_input("Promo Code")
                if st.button("Apply"):
                    if coupon_code == "BreatheFree2026":
                        update_user_package(username, "Pro", "SELF_REDEEM")
                        st.success("Upgraded!")
                        st.rerun()

        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["max_files"]
        uploaded_media = st.file_uploader(f"Max {max_f} assets", accept_multiple_files=True, type=['png', 'jpg', 'mp4'])
        
        st.divider()
        full_map = {
            "HVAC": ["Full System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Tankless Heaters"],
            "Restoration": ["Water Damage", "Mold Remediation"], "Roofing": ["Roof Replacement", "Storm Damage"],
            "Solar": ["Solar Grid Install"], "Custom": ["Manual Entry"]
        }
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")

        include_blog = st.toggle("📝 SEO Blog Content", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # --- MAIN TABS ---
    tab_list = ["🔥 Launchpad", "📊 Database", "📱 Social Preview", "💎 Pricing"]
    if username == "admin":
        tab_list.append("🛠️ Admin Panel")
    
    tabs = st.tabs(tab_list)

    with tabs[0]:
        if run_button and city_input:
            if len(uploaded_media) <= max_f:
                with st.spinner(f"Swarm active on {user_tier} Tier..."):
                    run_marketing_swarm({'city': city_input, 'industry': main_cat, 'service': target_service, 'premium': True, 'blog': include_blog})
                    with open("final_marketing_strategy.md", "r", encoding="utf-8") as f: content = f.read()
                    st.session_state['ad_copy'] = content
                    st.session_state['generated'] = True
                    save_lead_to_db(username, main_cat, target_service, city_input, content)
            else: st.error("Too many files.")

        if st.session_state.get('generated'):
            st.success("✨ Strategy Ready!")
            copy = st.session_state['ad_copy']
            c1, c2 = st.columns(2)
            with c1: st.download_button("📄 Word", create_word_doc(copy), f"{city_input}.docx")
            with c2: st.download_button("📕 PDF", create_pdf(copy, target_service, city_input), f"{city_input}.pdf")
            st.markdown(copy)

    with tabs[1]:
        conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
        df = pd.read_sql_query("SELECT date, user, industry, service, city FROM leads ORDER BY id DESC", conn)
        st.dataframe(df, use_container_width=True)
        conn.close()

    with tabs[3]:
        st.title("💎 Plan Comparison")
        p1, p2, p3 = st.columns(3)
        with p1: st.markdown('<div class="pricing-card"><h3>Basic</h3><h1>$0</h1><p>HVAC/Plumbing<br>1 Asset Upload<br>No Blogs</p></div>', unsafe_allow_html=True)
        with p2:
            st.markdown('<div class="pricing-card" style="border: 2px solid #0056b3;"><h3>Pro</h3><h1>$49</h1><p>4 Industries<br>5 Asset Uploads<br>SEO Blogs</p></div>', unsafe_allow_html=True)
            st.link_button("Upgrade Now", "https://buy.stripe.com/pro_link", use_container_width=True, type="primary")
        with p3:
            st.markdown('<div class="pricing-card"><h3>Unlimited</h3><h1>$99</h1><p>All Industries<br>20 Asset Uploads<br>Custom Services</p></div>', unsafe_allow_html=True)
            st.link_button("Go Unlimited", "https://buy.stripe.com/unlimited_link", use_container_width=True)

    # --- 🛠️ ADMIN PANEL (With Audit Log) ---
    if username == "admin":
        with tabs[-1]:
            admin_sub_tabs = st.tabs(["👥 User Management", "📜 Activity Log"])
            
            with admin_sub_tabs[0]:
                st.header("User Access Control")
                all_users = get_users_from_db()['usernames']
                for u_name, u_data in all_users.items():
                    if u_name == "admin": continue
                    with st.container():
                        st.markdown(f"<div class='admin-card'><strong>{u_data['name']}</strong> (@{u_name}) - {u_data['package']} Tier</div>", unsafe_allow_html=True)
                        c1, c2, c3 = st.columns([2, 1, 1])
                        with c1:
                            new_p = st.selectbox(f"Select Tier", ["Basic", "Pro", "Unlimited"], 
                                                 index=["Basic", "Pro", "Unlimited"].index(u_data['package']),
                                                 key=f"adm_{u_name}")
                        with c2:
                            if st.button(f"Update", key=f"upbtn_{u_name}"):
                                update_user_package(u_name, new_p, st.session_state['name'])
                                st.success(f"Updated {u_name}")
                                st.rerun()
                        with c3:
                            if st.button(f"🗑️ Delete", key=f"delbtn_{u_name}"):
                                st.session_state[f"confirm_del_{u_name}"] = True
                            
                            if st.session_state.get(f"confirm_del_{u_name}"):
                                if st.button(f"Confirm Delete {u_name}", key=f"real_del_{u_name}", type="primary"):
                                    delete_user(u_name, st.session_state['name'])
                                    st.success("User removed.")
                                    st.rerun()

            with admin_sub_tabs[1]:
                st.header("📜 Activity Log")
                conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
                logs_df = pd.read_sql_query("SELECT timestamp, admin_user, action, target_user, details FROM audit_logs ORDER BY id DESC", conn)
                st.dataframe(logs_df, use_container_width=True)
                if st.button("🗑️ Clear Logs"):
                    conn.cursor().execute("DELETE FROM audit_logs")
                    conn.commit()
                    st.rerun()
                conn.close()
