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
from streamlit_gsheets import GSheetsConnection

# --- 1. CRITICAL: PAGE CONFIG MUST BE FIRST ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 2. THE TOTAL SaaS BRANDING & "NUCLEAR" CSS ---
# Your logo link from Google Drive
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_bg = "#F8F9FB" 

hide_and_brand_style = f"""
    <style>
    /* NUCLEAR HIDE: Hides top header, GitHub/Fork, footer, and bottom-right badges */
    header, footer, div[data-testid="stStatusWidget"], 
    div[data-testid="stConnectionStatus"], .stAppDeployButton,
    a[href*="streamlit.io"], #stDecoration, div[data-testid="stToolbar"],
    [data-testid="stDecoration"] {{
        visibility: hidden !important;
        display: none !important;
    }}

    /* CUSTOM SaaS BACKGROUND */
    .stApp {{
        background-color: {brand_bg};
    }}

    /* CENTERED LOGO INJECTION: Adds logo above login box */
    .stApp::before {{
        content: "";
        display: block;
        margin-left: auto;
        margin-right: auto;
        margin-top: 50px;
        width: 220px; 
        height: 220px;
        background-image: url("{logo_url}");
        background-size: contain;
        background-repeat: no-repeat;
    }}

    /* CLEAN UI: Adjust padding and hide hamburger menu */
    .block-container {{ padding-top: 1.5rem !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    
    /* Force hide the 'Running...' status widget */
    [data-testid="stStatusWidget"] {{ display: none !important; }}
    </style>
"""
st.markdown(hide_and_brand_style, unsafe_allow_html=True)

# --- 3. DYNAMIC AUTHENTICATION (Google Sheets Connection) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # ttl="0" ensures that adding a user to the sheet works immediately without caching
    df = conn.read(ttl="0")
    
    user_data = {}
    for _, row in df.iterrows():
        user_data[str(row['username'])] = {
            "name": str(row['name']),
            "email": str(row['email']),
            "password": str(row['password'])
        }
    
    credentials = {"usernames": user_data}
except Exception as e:
    st.error("Error connecting to User Database. Please check Google Sheets permissions.")
    st.stop()

authenticator = stauth.Authenticate(
    credentials,
    st.secrets['cookie']['name'],
    st.secrets['cookie']['key'],
    int(st.secrets['cookie']['expiry_days'])
)

# --- 4. AUTHENTICATION UI ---
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Welcome to BreatheEasy AI. Please enter your credentials.')
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
        clean = content.replace('✨', '').replace('🚀', '').replace('🌬️', '').encode('latin-1', 'ignore').decode('latin-1')
        for line in clean.split('\n'): pdf.multi_cell(0, 10, txt=line)
        return pdf.output(dest='S').encode('latin-1')
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()

        # --- HIDDEN ADMIN TOOL ---
        with st.expander("🛠️ Admin Tools (Internal Only)"):
            st.write("Generate password hashes for the Google Sheet:")
            new_pw = st.text_input("Enter New User Password", type="password")
            if st.button("Generate Hash"):
                if new_pw:
                    hashed_pw = stauth.Hasher([new_pw]).generate()[0]
                    st.code(hashed_pw, language="text")
                    st.success("Copy the code above and paste it into the 'password' column of your Google Sheet.")
                else:
                    st.warning("Please enter a password first.")
        
        st.divider()
        st.header("🏢 Business Category")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "Heating Repair", "AC Installation"],
            "Plumbing": ["Drain Cleaning", "Water Heater Service", "Emergency Repair"],
            "Electrical": ["Panel Upgrade", "Wiring Inspection"],
            "Landscaping": ["Lawn Maintenance", "Seasonal Cleanup"],
            "Custom": ["Manual Entry"]
        }
        
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_industry = main_cat if main_cat != "Custom" else st.text_input("Enter Industry")
        target_service = st.selectbox("Select Service", industry_map[main_cat]) if main_cat != "Custom" else st.text_input("Enter Service")

        st.header("📍 Target Location")
        city_input = st.text_input("Enter City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Generate Marketing Swarm")

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
                st.error("Strategy data file not found.")

    # --- DISPLAY ---
    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🚀 Download"])
        
        with tabs[0]: st.markdown(st.session_state.get('ad_copy', 'No copy found.'))
        with tabs[1]:
            full_rpt = f"# {target_service} Report: {city_input}\n\n" + st.session_state.get('ad_copy', '')
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx")
            c2.download_button("📕 PDF", create_pdf(full_rpt), "Report.pdf")
