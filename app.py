import streamlit as st
import streamlit_authenticator as stauth
import os, sqlite3, pandas as pd
from datetime import datetime
from main import run_marketing_swarm 
from docx import Document
from fpdf import FPDF
from io import BytesIO

# --- CONFIG & DB ---
st.set_page_config(page_title="BreatheEasy AI Enterprise", page_icon="🌬️", layout="wide")

def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, role TEXT, package TEXT, credits INTEGER, logo_path TEXT, last_login TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, user TEXT, industry TEXT, service TEXT, city TEXT, content TEXT)''')
    c.execute("SELECT username FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin','admin@ai.com','Admin',?,'admin','Unlimited',9999,NULL,NULL)", (hashed_pw,))
    conn.commit(); conn.close()

init_db()

# --- AUTH & REGISTRATION ---
def get_creds():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM users", conn); conn.close()
    return {'usernames': {row['username']: {'email': row['email'], 'name': row['name'], 'password': row['password'], 'package': row['package'], 'credits': row['credits'], 'logo_path': row['logo_path']} for _, row in df.iterrows()}}

authenticator = stauth.Authenticate(get_creds(), st.secrets['cookie']['name'], st.secrets['cookie']['key'], st.secrets['cookie']['expiry_days'])

if not st.session_state.get("authentication_status"):
    st.markdown("<h1 style='text-align:center;'>🌬️ BreatheEasy AI</h1>", unsafe_allow_html=True)
    tab_log, tab_reg = st.tabs(["🔑 Login", "🆕 Register Account"])
    with tab_log: authenticator.login(location='main')
    with tab_reg:
        res = authenticator.register_user(location='main', pre_authorization=False)
        if res:
            e, u, n = res
            pw = stauth.Hasher.hash(authenticator.credentials['usernames'][u]['password'])
            conn = sqlite3.connect('breatheeasy.db')
            conn.cursor().execute("INSERT INTO users VALUES (?,?,?,?,'member','Basic',5,NULL,?)", (u, e, n, pw, datetime.now().strftime("%Y-%m-%d")))
            conn.commit(); conn.close(); st.success("Registered! Go to Login.")
    st.stop()

# --- DASHBOARD LOGIC ---
username = st.session_state["username"]
user_info = get_creds()['usernames'].get(username, {})
credits = user_info['credits']

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state['name']} <span style='font-size:10px; background:#0056b3; color:white; padding:2px 8px; border-radius:10px;'>{user_info['package']}</span>", unsafe_allow_html=True)
    st.metric("Available Credits", credits)
    authenticator.logout('Sign Out', 'sidebar')
    st.divider()
    main_cat = st.selectbox("Industry", ["HVAC", "Plumbing", "Solar", "Custom"])
    target_service = st.selectbox("Service", ["Installation", "Repair", "Audit"]) if main_cat != "Custom" else st.text_input("Service")
    city = st.text_input("City")
    run_btn = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

# --- TABS ---
tabs = st.tabs(["🔥 Launchpad", "📊 Database", "📱 Preview", "👁️ Visual Inspector", "💎 Pricing"])

with tabs[0]: # LAUNCHPAD
    if run_btn and city:
        if credits > 0:
            with st.status("🐝 Swarm Processing...", expanded=True) as status:
                res = run_marketing_swarm({'city': city, 'industry': main_cat, 'service': target_service})
                st.session_state['copy'] = res
                st.session_state['gen'] = True
                conn = sqlite3.connect('breatheeasy.db')
                conn.cursor().execute("UPDATE users SET credits = credits - 1 WHERE username = ?", (username,))
                conn.cursor().execute("INSERT INTO leads (date, user, industry, service, city, content) VALUES (?,?,?,?,?,?)", (datetime.now().strftime("%Y-%m-%d"), username, main_cat, target_service, city, str(res)))
                conn.commit(); conn.close(); st.rerun()
        else: st.error("Out of Credits!")

    if st.session_state.get('gen'):
        st.subheader("📥 Download Deliverables")
        col1, col2 = st.columns(2)
        col1.download_button("📄 Word Doc", str(st.session_state['copy']).encode('utf-8'), f"{city}_Report.docx", use_container_width=True)
        col2.download_button("📕 PDF Report", str(st.session_state['copy']).encode('latin-1', 'ignore'), f"{city}_Report.pdf", use_container_width=True)
        st.markdown(st.session_state['copy'])

with tabs[3]: # VISUAL INSPECTOR
    st.subheader("👁️ Visual Identity Agent")
    up = st.file_uploader("Upload on-site photos", type=['jpg','png'])
    if up: st.image(up, caption="Processing for trust-building prompts...")

with tabs[4]: # PRICING
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div style='border:1px solid #ddd; padding:20px; text-align:center;'><h3>Basic</h3><h1>$0</h1><p>5 Credits</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div style='border:2px solid #0056b3; padding:20px; text-align:center;'><h3>Pro</h3><h1>$49</h1><p>50 Credits</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div style='border:1px solid #ddd; padding:20px; text-align:center;'><h3>Unlimited</h3><h1>$99</h1><p>Unlimited</p></div>", unsafe_allow_html=True)
