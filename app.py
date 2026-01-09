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

# SMTP Libraries for Gmail
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
    .block-container {{ padding-top: 1.5rem !important; }}
    #MainMenu {{ visibility: hidden !important; }}
    </style>
""", unsafe_allow_html=True)

# --- 4. AUTHENTICATION CONFIGURATION ---
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

# --- 5. AUTHENTICATION UI ---
authenticator.login(location='main')

if st.session_state.get("authentication_status") is False:
    st.error('Username/password is incorrect')
elif st.session_state.get("authentication_status") is None:
    st.warning('Welcome to BreatheEasy AI. Please login to continue.')
    st.stop()

# --- 6. PROTECTED SaaS DASHBOARD ---
if st.session_state.get("authentication_status"):
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # --- HELPER FUNCTIONS FOR EXPORT & EMAIL ---
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

    def send_email_via_smtp(content, target_city):
        sender_email = st.secrets["EMAIL_SENDER"]
        sender_password = st.secrets["EMAIL_PASSWORD"]
        receiver_email = st.secrets["TEAM_EMAIL"]
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = f"🚀 New Marketing Report: {target_city}"
        body = f"The AI Swarm has completed the report for {target_city}. See attached."
        message.attach(MIMEText(body, "plain"))
        
        # Attach Word Doc
        word_data = create_word_doc(content)
        part = MIMEBase("application", "octet-stream")
        part.set_payload(word_data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=Report_{target_city}.docx")
        message.attach(part)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, receiver_email, message.as_string())
            return True
        except Exception as e:
            st.error(f"Email Failed: {e}")
            return False

    # --- SIDEBAR ---
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        
        with st.expander("🛠️ Admin Tools"):
            new_pw = st.text_input("New Member Password", type="password")
            if st.button("Generate Team Hash"):
                st.code(stauth.Hasher([new_pw]).generate()[0])

        st.divider()
        st.header("🎯 Targeting")
        industry_map = {
            "HVAC": ["Full System Replacement", "IAQ & Filtration", "Emergency Repair", "Commercial Maintenance"],
            "Plumbing": ["Water Heater Service", "Emergency Repair", "Sewer Replacement"],
            "Custom": ["Manual Entry"]
        }
        main_cat = st.selectbox("Select Industry", list(industry_map.keys()))
        target_service = st.selectbox("Select Service", industry_map[main_cat]) if main_cat != "Custom" else st.text_input("Enter Service")
        city_input = st.text_input("Target City", placeholder="e.g. Naperville, IL")
        
        st.divider()
        high_ticket = st.toggle("Focus on Premium Leads", value=True)
        include_blog = st.checkbox("Generate SEO Blog Content", value=True)
        run_button = st.button("🚀 Run AI Swarm")

    # --- MAIN VIEW ---
    st.title("🌬️ BreatheEasy AI Launchpad")

    if run_button and city_input:
        with st.spinner(f"Analyzing {target_service} leads in {city_input}..."):
            result = marketing_crew.kickoff(inputs={
                'city': city_input, 
                'industry': main_cat, 
                'service': target_service,
                'premium_focus': high_ticket,
                'blog': include_blog
            })
            st.session_state['generated'] = True
            try:
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['ad_copy'] = f.read()
            except:
                st.error("Strategy file error.")

    # --- RESULTS & EXPORTS ---
    if st.session_state.get('generated'):
        st.success("✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy & Blog", "🚀 Download & Email"])
        full_rpt = st.session_state.get('ad_copy', '')
        
        with tabs[0]: 
            st.markdown(full_rpt)
        
        with tabs[1]:
            st.subheader("Export Options")
            report_title = f"# {target_service} Report: {city_input}\n\n"
            final_content = report_title + full_rpt
            
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📄 Word", create_word_doc(final_content), "Report.docx")
            with c2:
                st.download_button("📕 PDF", create_pdf(final_content), "Report.pdf")
            
            st.divider()
            if st.button("📧 Email Full Report to Team"):
                with st.spinner("Connecting to Gmail..."):
                    if send_email_via_smtp(full_rpt, city_input):
                        st.success(f"Report sent to {st.secrets['TEAM_EMAIL']}!")
