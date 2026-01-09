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

# --- 1. PRE-IMPORT KEY MAPPING ---
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# --- 2. PAGE CONFIGURATION ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 3. SaaS WHITE-LABEL UI ---
logo_url = "https://drive.google.com/uc?export=view&id=1Jw7XreUO4yAQxUgKAZPK4sRi4mzjw_yU"
brand_bg = "#F8F9FB" 

st.markdown(f"""
    <style>
    header {{ visibility: hidden !important; }}
    div[data-testid="stStatusWidget"], div[data-testid="stConnectionStatus"],
    .stAppDeployButton, a[href*="streamlit.io"], div[data-testid="stToolbar"], 
    footer, #stDecoration {{ display: none !important; visibility: hidden !important; }}
    .stApp {{ background-color: {brand_bg}; }}
    .stApp::before {{
        content: ""; display: block; margin: 40px auto 0;
        width: 180px; height: 180px;
        background-image: url("{logo_url}");
        background-size: contain; background-repeat: no-repeat;
    }}
    /* Style the download buttons */
    .stDownloadButton button {{
        width: 100%;
        border-radius: 8px;
        border: 1px solid #dcdcdc;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 4. AUTHENTICATION ---
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

authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Welcome to BreatheEasy AI. Please login.')
    st.stop()

# --- 5. PROTECTED DASHBOARD ---
if st.session_state.get("authentication_status"):
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    
    # --- EXPORT HELPERS ---
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI: Marketing Strategy', 0)
        for line in content.split('\n'):
            doc.add_paragraph(line)
        bio = BytesIO()
        doc.save(bio)
        return bio.getvalue()

    def create_pdf(content):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        clean = content.encode('latin-1', 'ignore').decode('latin-1')
        for line in clean.split('\n'):
            pdf.multi_cell(0, 10, txt=line)
        return pdf.output(dest='S').encode('latin-1')
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        
        # Team Sharing Option
        with st.expander("👥 Team Access"):
            st.write("Share this account with teammates or generate a new user hash below.")
            st.info("Your current plan allows for 3 team members.")
            new_pw = st.text_input("New Member Password", type="password")
            if st.button("Generate Team Hash"):
                st.code(stauth.Hasher([new_pw]).generate()[0])

        st.divider()
        st.header("🎯 Targeting")
        industry_map = {"HVAC": ["Full System Replacement", "IAQ"], "Plumbing": ["Sewer Repair"]}
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_service = st.selectbox("Select Service", industry_map[main_cat])
        city_input = st.text_input("Target City", placeholder="e.g. Naperville, IL")
        
        run_button = st.button("🚀 Run AI Swarm")

    st.title("🌬️ BreatheEasy AI Launchpad")

    if run_button and city_input:
        with st.spinner(f"Analyzing {target_service} leads..."):
            result = marketing_crew.kickoff(inputs={'city': city_input, 'industry': main_cat, 'service': target_service})
            st.session_state['generated'] = True
            try:
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['ad_copy'] = f.read()
            except:
                st.error("Strategy file error.")

    # --- RESULTS & EXPORT SECTION ---
    if st.session_state.get('generated'):
        st.success("✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🚀 Download & Share"])
        
        full_rpt = st.session_state.get('ad_copy', 'No copy found.')
        
        with tabs[0]: 
            st.markdown(full_rpt)
        
        with tabs[1]:
            st.subheader("Export & Share with Team")
            
            # The specific Word download button you requested:
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx")
            with c2:
                st.download_button("📕 PDF", create_pdf(full_rpt), "Report.pdf")
            
            st.divider()
            # Shareable Link Logic
            st.write("🔗 **Internal Share Link**")
            current_url = "https://breathe-easy-ai.streamlit.app" # Replace with your real URL
            st.text_input("Copy this link to share the app with your team:", value=current_url)
            if st.button("📧 Email Report to Team"):
                st.success("Report link prepared! (Integration with SendGrid/SMTP recommended for auto-emailing)")
