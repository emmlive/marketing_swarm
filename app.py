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

# --- 2. THE ULTIMATE "ZERO-BRANDING" CSS GATEKEEPER ---
# This targets the top-right tools, bottom-right icons, and all deployment badges.
hide_style = """
    <style>
    /* Hides the top header entirely (GitHub/Fork/3-dots) */
    header { visibility: hidden !important; height: 0 !important; }
    
    /* Hides the entire bottom-right status area and 'Hosted with Streamlit' badge */
    /* Targetting stStatusWidget, ConnectionStatus, and any Streamlit-linked buttons */
    div[data-testid="stStatusWidget"], 
    div[data-testid="stConnectionStatus"],
    .stAppDeployButton,
    div[class*="stDeployButton"],
    a[href*="streamlit.io"],
    #stDecoration { 
        display: none !important; 
        visibility: hidden !important; 
    }
    
    /* Hides the toolbar/pencil icon at the top right */
    div[data-testid="stToolbar"] { visibility: hidden !important; height: 0 !important; }
    
    /* Hides the 'Made with Streamlit' footer at bottom-center */
    footer { visibility: hidden !important; }
    
    /* Reclaims the space at the top and hides the hamburger menu icon */
    .block-container { padding-top: 1.5rem !important; }
    #MainMenu { visibility: hidden !important; }
    
    /* Hides the 'Running...' or 'Casting...' indicator that floats in the top right */
    [data-testid="stStatusWidget"] { display: none !important; }
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
# Check status using the new session state logic
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Please enter your username and password')
    
    # Registration & Reset Options
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

    # CRITICAL: Prevent the rest of the app from loading
    st.stop()

# --- 5. PROTECTED SaaS DASHBOARD ---
if st.session_state.get("authentication_status"):
    
    # Initialize API Client
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        st.caption("🟢 System Status: Active")
        
        # --- Industry Selection ---
        st.header("🏢 Business Category")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "Heating Repair", "AC Installation"],
            "Plumbing": ["Drain Cleaning", "Water Heater Service", "Emergency Leak Repair", "Pipe Bursting"],
            "Electrical": ["Panel Upgrade", "EV Charger Installation", "Wiring Inspection"],
            "Landscaping": ["Lawn Maintenance", "Sprinkler Repair", "Seasonal Cleanup"],
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

    # (Helper functions for create_word_doc, create_pdf remain as they are...)

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
                st.error("Strategy files not found. Check CrewAI output names.")

    # --- DASHBOARD DISPLAY ---
    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🚀 Download"])
        
        with tabs[0]: st.markdown(st.session_state.get('ad_copy', 'No copy found.'))
        with tabs[1]:
            full_rpt = f"# {target_service} Report: {city_input}\n\n" + st.session_state.get('ad_copy', '')
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", "create_word_doc(full_rpt)", "Report.docx")
            c2.download_button("📕 PDF", "create_pdf(full_rpt)", "Report.pdf")
