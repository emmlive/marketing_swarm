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

# --- 2. THE SaaS "ZERO-BRANDING" CSS & LOGO ---
# Converting your Google Drive link to a direct-load URL
LOGO_URL = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"

hide_style = f"""
    <style>
    /* HIDE ALL STREAMLIT BRANDING (TOP & BOTTOM) */
    header, footer, .stAppDeployButton, 
    div[data-testid="stStatusWidget"], 
    div[data-testid="stConnectionStatus"], 
    div[data-testid="stToolbar"],
    #MainMenu, #stDecoration {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* CUSTOM BACKGROUND COLOR (Professional Soft Gray) */
    .stApp {{
        background-color: #F8F9FA;
    }}

    /* CENTERED LOGO ABOVE LOGIN FORM */
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        display: block;
        margin: 50px auto 20px auto;
        width: 180px;
        height: 180px;
        background-image: url("{LOGO_URL}");
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
    }}

    /* PUSH LOGIN BOX DOWN SLIGHTLY FOR LOGO */
    .block-container {{
        padding-top: 2rem !important;
    }}
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

# --- 4. AUTHENTICATION UI (v0.3.0+) ---
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    # This renders the login form with your logo above it
    st.info('Welcome to BreatheEasy AI. Please sign in to access your dashboard.')
    
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
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        st.caption("🟢 System Status: Active")
        
        st.header("🏢 Business Category")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "Heating Repair", "AC Installation"],
            "Plumbing": ["Drain Cleaning", "Water Heater Service", "Emergency Leak Repair"],
            "Electrical": ["Panel Upgrade", "EV Charger Installation"],
            "Landscaping": ["Lawn Maintenance", "Sprinkler Repair"],
            "Custom": ["Manual Entry"]
        }
        
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_industry = main_cat if main_cat != "Custom" else st.text_input("Enter Industry")
        target_service = st.selectbox("Select Service", industry_map[main_cat]) if main_cat != "Custom" else st.text_input("Enter Service")

        st.header("📍 Target Location")
        city_input = st.text_input("Enter City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Generate Local Swarm")

    st.title("🌬️ BreatheEasy AI: Dashboard")

    # Helper functions for report creation
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('Campaign Report', 0)
        doc.add_paragraph(content)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    # Execution Logic
    if run_button and city_input:
        with st.spinner(f"Building campaign for {city_input}..."):
            result = marketing_crew.kickoff(inputs={'city': city_input, 'industry': target_industry, 'service': target_service})
            st.session_state['generated'] = True
            st.session_state['ad_copy'] = "Marketing Strategy Results Here..." # Replace with actual output file reading logic

    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        st.markdown(st.session_state.get('ad_copy', ''))
        st.download_button("📄 Download Report", create_word_doc(st.session_state['ad_copy']), "Report.docx")
