import streamlit as st
import streamlit_authenticator as stauth
import os
import sqlite3
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- 0. HELPER FUNCTIONS ---
def toggle_theme():
    if 'theme' not in st.session_state: st.session_state.theme = 'light'
    st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'

# --- 1. SYSTEM INITIALIZATION ---
st.set_page_config(page_title="TechInAdvance AI | Command", page_icon="Logo1.jpeg", layout="wide")

if 'gen' not in st.session_state: st.session_state.gen = False
if 'report' not in st.session_state: st.session_state.report = {}

# --- 2. EXECUTIVE UI CSS (THE LOOK & FEEL) ---
sidebar_color = "#2563EB" # Tech Blue
st.markdown(f"""
    <style>
    .stApp {{ background-color: #FDFCF0; color: #1E293B; }}
    [data-testid="stSidebar"] {{ background-color: #FFFFFF !important; border-right: 3px solid rgba(0,0,0,0.1) !important; }}
    .price-card {{ 
        background: white; padding: 25px; border-radius: 15px; border: 2px solid {sidebar_color}; 
        text-align: center; margin-bottom: 15px; box-shadow: 0px 4px 10px rgba(0,0,0,0.05); 
    }}
    .deploy-guide {{ 
        background: rgba(37, 99, 235, 0.08); padding: 18px; border-radius: 12px; 
        border-left: 6px solid {sidebar_color}; margin-bottom: 25px; 
    }}
    div.stButton > button {{ background-color: {sidebar_color}; color: white; border-radius: 8px; font-weight: 800; height: 3.2em; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('breatheeasy.db', check_same_thread=False)
    c = conn.cursor()
    # User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, email TEXT, name TEXT, password TEXT, 
                  role TEXT, plan TEXT, credits INTEGER, logo_path TEXT, 
                  team_id TEXT, verified INTEGER DEFAULT 0)''')
    # Master Audit Log
    c.execute('''CREATE TABLE IF NOT EXISTS master_audit_logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, user TEXT, 
                  action_type TEXT, target_biz TEXT, location TEXT, status TEXT)''')
    
    # Root Admin Auto-Creation
    admin_pw = stauth.Hasher.hash('admin123')
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin','admin@tech.ai','Admin',?,'admin','Unlimited',9999,'Logo1.jpeg','HQ_001',1)", (admin_pw,))
    conn.commit()
    conn.close()

init_db()

# --- 4. CORE DEFINITIONS (PREVENTS NAME-ERRORS) ---
agent_map = [
    ("🕵️ Analyst", "analyst"), ("📺 Ads", "ads"), ("🎨 Creative", "creative"), 
    ("👔 Strategist", "strategist"), ("📱 Social", "social"), ("📍 GEO", "geo"), 
    ("🌐 Auditor", "audit"), ("✍ SEO", "seo")
]

# --- 5. THE SIDEBAR SKELETON ---
with st.sidebar:
    col_h, col_t = st.columns([2, 1])
    with col_h: st.caption("🟢 **SYSTEM ONLINE**")
    with col_t: 
        if st.button("🌓"): toggle_theme()
    
    st.image("Logo1.jpeg", width=120) # Ensure this file is in your folder
    st.divider()
    
    st.subheader("Configuration")
    biz_name = st.text_input("Brand Name", placeholder="Acme Solar")
    full_loc = st.text_input("Target Location", placeholder="Miami, FL")
    
    st.divider()
    st.info("Log in to unlock Swarm Command.")

# --- 6. MAIN UI TABS (SKELETON) ---
st.title("Enterprise Swarm Command")
tab_labels = ["📖 Guide"] + [a[0] for a in agent_map] + ["🤝 Team Intel"]
tabs = st.tabs(tab_labels)

with tabs[0]:
    st.header("📖 Agent Intelligence Manual")
    st.write("Welcome to your Enterprise SaaS. Please log in to initiate market forensics.")

# ---------------------------------------------------------
# NEXT STEP: Sprint 2 (Authentication & Sign-Up Logic)
# ---------------------------------------------------------
