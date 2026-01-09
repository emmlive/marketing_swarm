import streamlit as st
import streamlit_authenticator as stauth
import os
from openai import OpenAI
from main import marketing_crew
from docx import Document
from fpdf import FPDF
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# --- 1. CRITICAL: MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 2. THE 2026 SaaS BRANDING & SELECTORS ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_bg = "#F8F9FB"

st.markdown(f"""
    <style>
    /* Force hide all Streamlit platform indicators */
    header, footer, .stAppDeployButton, #stDecoration, 
    div[data-testid="stStatusWidget"], div[data-testid="stConnectionStatus"],
    div[data-testid="stToolbar"] {{
        visibility: hidden !important;
        display: none !important;
    }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 50px auto 0;
        width: 220px; height: 220px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    .block-container {{ padding-top: 1.5rem !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. DYNAMIC AUTHENTICATION (GSheets Connector) ---
# Map Gemini key to Google key for underlying libraries
os.environ["GOOGLE_API_KEY"] = st.secrets.get("GEMINI_API_KEY", "")
os.environ["GEMINI_API_KEY"] = st.secrets.get("GEMINI_API_KEY", "")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(ttl="0") # No cache for instant user updates
    
    user_data = {}
    for _, row in df.iterrows():
        user_data[str(row['username'])] = {
            "name": str(row['name']),
            "email": str(row['email']),
            "password": str(row['password']) # Must be pre-hashed in sheet
        }
    credentials = {"usernames": user_data}
except Exception as e:
    st.error("Database Connection Failed. Check Secrets and Sheet Permissions.")
    st.stop()

# Initialize Authenticator 0.4.2
authenticator = stauth.Authenticate(
    credentials,
    st.secrets['cookie']['name'],
    st.secrets['cookie']['key'],
    float(st.secrets['cookie']['expiry_days'])
)

# --- 4. LOGIN LOGIC (v0.4.2 Syntax: Location is the 1st argument) ---
# In 0.4.2, result is returned as (name, authentication_status, username)
authenticator.login(location='main')

if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your credentials to access the launchpad')
    st.stop()

# --- 5. SaaS DASHBOARD (Access Granted) ---
if st.session_state["authentication_status"]:
    
    # Initialize OpenAI with Secret Key
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    # Helper Functions
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI Strategy', 0)
        for line in content.split('\n'):
            doc.add_paragraph(line)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def create_pdf(content):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        clean = content.encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 10, txt=clean)
        return pdf.output(dest='S').encode('latin-1')

    # Sidebar Navigation & Tools
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar')
        st.divider()

        with st.expander("🛠️ Admin Tools"):
            st.caption("Generate User Hash")
            new_pw = st.text_input("Plain Text Password", type="password")
            if st.button("Generate Hash"):
                if new_pw:
                    # In 0.4.2, Hasher is used like this:
                    hashed = stauth.Hasher([new_pw]).generate()[0]
                    st.code(hashed)
                    st.info("Paste this into your Google Sheet.")

        st.divider()
        st.header("🏢 Industry Settings")
        industry_map = {
            "HVAC": ["Air Duct Cleaning", "Dryer Vent Cleaning", "AC Service"],
            "Plumbing": ["Drain Cleaning", "Water Heater"],
            "Custom": ["Manual Entry"]
        }
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_service = st.selectbox("Select Service", industry_map[main_cat]) if main_cat != "Custom" else st.text_input("Enter Service")
        city_input = st.text_input("Target City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Run Marketing Swarm")

    # Main Application View
    st.title("🌬️ BreatheEasy AI: Multi-Service Launchpad")
    
    if run_button and city_input:
        with st.spinner(f"Coordinating Crew for {target_service} in {city_input}..."):
            result = marketing_crew.kickoff(inputs={
                'city': city_input,
                'industry': main_cat,
                'service': target_service
            })
            st.session_state['generated'] = True
            # Assuming main.py creates this file locally
            try:
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['ad_copy'] = f.read()
            except:
                st.error("Strategy data file missing.")

    if st.session_state.get('generated'):
        st.success("Campaign Ready!")
        t1, t2 = st.tabs(["📝 Ad Copy", "🚀 Export"])
        with t1: st.markdown(st.session_state.get('ad_copy', ''))
        with t2:
            full_rpt = st.session_state.get('ad_copy', '')
            c1, c2 = st.columns(2)
            c1.download_button("📄 Download Word", create_word_doc(full_rpt), "Strategy.docx")
            c2.download_button("📕 Download PDF", create_pdf(full_rpt), "Strategy.pdf")
