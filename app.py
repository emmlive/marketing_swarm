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

# --- 1. CRITICAL: PAGE CONFIG MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")

# --- 2. THE SaaS GATEKEEPER CSS ---
# This hides the GitHub/Fork icons, the 3-dots menu, the footer, and the toolbar
hide_style = """
    <style>
    /* Hides the top header bar entirely (GitHub icon, Fork, 3-dots) */
    header { visibility: hidden !important; }
    
    /* Hides the 'Manage app' button and running status widgets */
    div[data-testid="stStatusWidget"] { visibility: hidden !important; }
    
    /* Hides the toolbar/pencil icon used for developer edits */
    div[data-testid="stToolbar"] { visibility: hidden !important; }
    
    /* Hides the 'Made with Streamlit' footer */
    footer { visibility: hidden !important; }
    
    /* Removes extra padding at the top for a cleaner white-label look */
    .block-container { padding-top: 2rem !important; }
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# --- 3. AUTHENTICATION CONFIGURATION ---
# Convert Secrets to mutable dicts for processing
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

# --- 4. AUTHENTICATION UI ---
#Capture return values for v0.3.x session management
name, authentication_status, username = authenticator.login(location='main')

if authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    st.warning('Please enter your username and password')
    
    # Registration & Reset Options (Only visible to non-logged users)
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

    # STOP execution here so unauthenticated users see nothing else
    st.stop()

# --- 5. PROTECTED SaaS DASHBOARD (Only runs if status is True) ---
if authentication_status:
    # Initialize API Client only after successful login
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    with st.sidebar:
        st.header(f"Welcome, {st.session_state['name']}!")
        authenticator.logout('Logout', 'sidebar', key='unique_logout_key')
        st.divider()
        st.caption("🟢 System Status: OpenAI Connected")
        
        # --- Industry Selection Logic ---
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
            target_industry = st.text_input("Enter Industry")
            target_service = st.text_input("Enter Specific Service")
        else:
            target_industry = main_cat
            target_service = st.selectbox("Select Specific Service", industry_map[main_cat])

        st.header("📍 Target Location")
        city_input = st.text_input("Enter City", placeholder="Naperville, IL")
        run_button = st.button("🚀 Generate Local Swarm")

    # Main App Header
    st.title("🌬️ BreatheEasy AI: Multi-Service Home Launchpad")

    # --- HELPER FUNCTIONS ---
    def create_word_doc(content):
        doc = Document()
        doc.add_heading('BreatheEasy AI: Campaign Report', 0)
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

    def generate_ad_image(prompt):
        try:
            response = client.images.generate(model="dall-e-3", prompt=prompt, n=1)
            return response.data[0].url
        except Exception: return None

    # --- EXECUTION LOGIC ---
    if run_button and city_input:
        with st.spinner(f"Building {target_service} campaign for {city_input}..."):
            result = marketing_crew.kickoff(inputs={
                'city': city_input,
                'industry': target_industry,
                'service': target_service
            })
            st.session_state['generated'] = True
            
            # Simulated File Loading (Adjust based on your CrewAI output files)
            try:
                with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['ad_copy'] = f.read()
                with open("full_7day_campaign.md", "r", encoding="utf-8") as f:
                    st.session_state['schedule'] = f.read()
                with open("visual_strategy.md", "r", encoding="utf-8") as f:
                    st.session_state['vision'] = f.read()
            except FileNotFoundError:
                st.error("Report files not found. Ensure CrewAI is saving strategy files correctly.")

    # --- DISPLAY DASHBOARD ---
    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🗓️ Schedule", "🖼️ Visual Assets", "🚀 Download"])
        
        with tabs[0]: st.markdown(st.session_state.get('ad_copy', 'No copy generated.'))
        with tabs[1]: st.markdown(st.session_state.get('schedule', 'No schedule generated.'))
        with tabs[2]:
            st.header("Visual Concepts")
            prompts = re.findall(r"AI Image Prompt: (.*)", st.session_state.get('vision', ''))
            if prompts:
                for idx, p in enumerate(prompts[:3]):
                    with st.expander(f"Concept {idx+1}"):
                        st.write(p)
                        if st.button(f"Paint Ad {idx+1}", key=f"pnt_{idx}"):
                            url = generate_ad_image(p)
                            if url: st.image(url)
        
        with tabs[3]:
            st.header("Platform Payloads")
            full_rpt = f"# {target_service} Report: {city_input}\n\n" + st.session_state.get('ad_copy', '')
            c1, c2 = st.columns(2)
            c1.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx")
            c2.download_button("📕 PDF", create_pdf(full_rpt), "Report.pdf")
