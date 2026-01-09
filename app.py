import streamlit as st
import streamlit_authenticator as stauth
import os
import re
import base64
from openai import OpenAI
from main import marketing_crew
from docx import Document
from fpdf import FPDF
from io import BytesIO

# --- 1. CRITICAL: PAGE CONFIG MUST BE FIRST ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 2. THE ULTIMATE "ZERO-BRANDING" & LOGO CSS ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_bg = "#F8F9FB" 

hide_style = f"""
    <style>
    /* Hides top header, GitHub/Fork icons, footer, and bottom-right badges */
    header, footer, div[data-testid="stStatusWidget"], 
    div[data-testid="stConnectionStatus"], .stAppDeployButton,
    a[href*="streamlit.io"], #stDecoration, div[data-testid="stToolbar"] {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* Custom Background */
    .stApp {{
        background-color: {brand_bg};
    }}

    /* Centered Logo above the login box */
    .stApp::before {{
        content: "";
        display: block;
        margin-left: auto;
        margin-right: auto;
        margin-top: 50px;
        width: 180px; 
        height: 180px;
        background-image: url("{logo_url}");
        background-size: contain;
        background-repeat: no-repeat;
    }}

    /* Reclaims space at the top */
    .block-container {{ padding-top: 1.5rem !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# --- 3. AUTHENTICATION CONFIGURATION ---
credentials = dict(st.secrets['credentials'])
if 'usernames' in credentials:
    credentials['usernames'] = dict(credentials['usernames'])
    for user in credentials['usernames']:
        credentials['usernames'][user] = dict(credentials['usernames'][user])

authenticator = stauth.Authenticate(
    credentials,
    st.secrets['cookie']['name'],
    st.secrets['cookie']['key'],
    st.secrets['cookie']['expiry_days']
)

# --- 4. AUTHENTICATION UI (v0.3.0+ Fix) ---
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Please enter your username and password')
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        try:
            preauth_list = st.secrets.get('preauthorized', {}).get('emails', [])
            if authenticator.register_user(location='main', pre_authorized=preauth_list):
                st.success('Registration successful! Please contact admin to finalize.')
        except Exception as e:
            st.error(f"Registration Error: {e}")
    with col2:
        try:
            if authenticator.forgot_password(location='main')[0]:
                st.success('Temporary password generated. Please contact admin.')
        except Exception as e:
            st.error(f"Reset Error: {e}")

    st.stop()

# --- 5. PROTECTED DASHBOARD ---
if st.session_state.get("authentication_status"):
    
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    # --- HELPER FUNCTIONS ---
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI Report', 0)
        for line in content.split('\n'):
            if line.startswith('###'): doc.add_heading(line.replace('###', '').strip(), level=2)
            elif line.startswith('##'): doc.add_heading(line.replace('##', '').strip(), level=1)
            else: doc.add_paragraph(line)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def create_pdf(content):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        # Clean text for PDF compatibility
        clean = content.replace('✨', '').replace('🚀', '').replace('🌬️', '').encode('latin-1', 'ignore').decode('latin-1')
        for line in clean.split('\n'): pdf.multi_cell(0, 10, txt=line)
        return pdf.output(dest='S').encode('latin-1')
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        st.caption("🟢 System Status: Active")
        
        st.header("🏢 Business Category")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "Heating Repair", "AC Installation"],
            "Plumbing": ["Drain Cleaning", "Water Heater Service", "Emergency Leak Repair"],
            "Electrical": ["Panel Upgrade", "Wiring Inspection"],
            "Landscaping": ["Lawn Maintenance", "Seasonal Cleanup"],
            "Custom": ["Manual Entry"]
        }
        
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        
        if main_cat == "Custom":
            target_industry = st.text_input("Enter Industry")
            target_service = st.text_input("Enter Specific Service")
        else:
            target_industry = main_cat
            target_service = st.selectbox("Select Specific Service", industry_map[main_cat])

        st.header("📍 Target Location")
        city_input = st.text_input("Enter City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Generate Local Swarm")

    st.title("🌬️ BreatheEasy AI: Multi-Service Home Launchpad")

    # --- EXECUTION LOGIC ---
    if run_button and city_input:
        with st.spinner(f"Building {target_service} campaign for {city_input}..."):
            result = marketing_crew.kickoff(inputs={
                'city': city_input,
                'industry': target_industry,
                'service': target_service
            })
            st.session_state['generated'] = True
            
            try:
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['ad_copy'] = f.read()
            except FileNotFoundError:
                st.error("Strategy files not found.")

    # --- DASHBOARD DISPLAY ---
    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🚀 Download"])
        
        with tabs[0]: st.markdown(st.session_state.get('ad_copy', 'No copy found.'))
        with tabs[1]:
            full_rpt = f"# {target_service} Report: {city_input}\n\n" + st.session_state.get('ad_copy', '')
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx")
            c2.download_button("📕 PDF", create_pdf(full_rpt), "Report.pdf")
