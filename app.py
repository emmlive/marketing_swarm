import streamlit as st
import streamlit_authenticator as stauth
import os
import re
import base64
from openai import OpenAI, BadRequestError
from main import marketing_crew
from docx import Document
from fpdf import FPDF
from io import BytesIO

# --- 1. CRITICAL: PAGE CONFIG MUST BE FIRST ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 2. THE ULTIMATE SaaS GATEKEEPER CSS ---
# This hides the Toolbar (pencil), Header (GitHub/Fork/Menu), and Footer
hide_style = """
    <style>
    /* Hides the top header bar entirely (GitHub icon, Fork, 3-dots) */
    header { visibility: hidden !important; }
    
    /* Hides the 'Manage app' button and status widgets */
    div[data-testid="stStatusWidget"] { visibility: hidden !important; }
    
    /* Hides the toolbar/pencil icon */
    div[data-testid="stToolbar"] { visibility: hidden !important; }
    
    /* Hides the 'Made with Streamlit' footer */
    footer { visibility: hidden !important; }
    
    /* Removes extra padding at the top for a professional SaaS feel */
    .block-container { padding-top: 2rem !important; }
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# --- 3. AUTHENTICATION CONFIGURATION ---
credentials = dict(st.secrets['credentials'])

if 'usernames' in credentials:
    credentials['usernames'] = dict(credentials['usernames'])
    for username in credentials['usernames']:
        credentials['usernames'][username] = dict(credentials['usernames'][username])

authenticator = stauth.Authenticate(
    credentials,
    st.secrets['cookie']['name'],
    st.secrets['cookie']['key'],
    st.secrets['cookie']['expiry_days']
)

# --- 4. AUTHENTICATION UI ---
# Capture return values for v0.3.x
name, authentication_status, username = authenticator.login(location='main')

if authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    # Optional: Registration/Forgot Password only visible when not logged in
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
            user_forgot, email_forgot, new_pw = authenticator.forgot_password(location='main')
            if user_forgot:
                st.success('Temporary password generated. Please contact admin.')
        except Exception as e:
            st.error(f"Reset Error: {e}")

    # Stop execution here if not logged in
    st.stop()

# --- 5. THE PROTECTED APP DASHBOARD ---
if authentication_status:
    # --- SECURE API KEY INITIALIZATION ---
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # --- SIDEBAR: LOGOUT & CONNECTION STATUS ---
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        st.caption("🟢 System Status: OpenAI Connected")
            
        st.divider()
        st.header("🏢 Business Category")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "Heating Repair", "AC Installation"],
            "Plumbing": ["Drain Cleaning", "Water Heater Service", "Emergency Leak Repair", "Pipe Bursting"],
            "Electrical": ["Panel Upgrades", "EV Charger Installation", "Wiring Inspection"],
            "Landscaping": ["Lawn Maintenance", "Sprinkler Repair", "Seasonal Cleanup"],
            "Custom": ["Manual Entry"]
        }
        
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        
        if main_cat == "Custom":
            target_industry = st.text_input("Enter Industry (e.g., Solar)")
            target_service = st.text_input("Enter Specific Service")
        else:
            target_industry = main_cat
            target_service = st.selectbox("Select Specific Service", industry_map[main_cat])

        st.header("📍 Target Location")
        city_input = st.text_input("Enter City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Generate Local Swarm")

    st.title("🌬️ BreatheEasy AI: Multi-Service Home Launchpad")

    # (Helper functions for create_word_doc, create_pdf, generate_ad_image, analyze_inspection_photo remain here)
    # [
