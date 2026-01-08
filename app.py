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

# --- 1. AUTHENTICATION CONFIGURATION (FROM SECRETS) ---
# We must convert st.secrets to a mutable dict to avoid:
# "TypeError: Secrets does not support item assignment"
credentials = dict(st.secrets['credentials'])

# Ensure nested 'usernames' is also a mutable dictionary
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

# --- 2. AUTHENTICATION UI ---
auth_status = st.session_state.get("authentication_status")

if not auth_status:
    col1, col2 = st.columns(2)
    with col1:
        try:
            # Pull preauthorized emails from secrets
            preauth_list = st.secrets.get('preauthorized', {}).get('emails', [])
            
            # New location for pre_authorized parameter in version 0.3.x
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

    authenticator.login(location='main')

# --- 3. THE PROTECTED APP DASHBOARD ---
if auth_status:
    
    # --- SECURE API KEY INITIALIZATION ---
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    st.set_page_config(page_title="BreatheEasy AI", page_icon="🌬️", layout="wide")
    
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

    # (Helper functions remain the same)
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

    def analyze_inspection_photo(image_bytes, user_prompt):
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}
                ],
                max_tokens=500,
            )
            return response.choices[0].message.content
        except Exception as e: return f"Error: {str(e)}"

    # --- EXECUTION ---
    if run_button and city_input:
        with st.spinner(f"Building {target_service} campaign for {city_input}..."):
            result = marketing_crew.kickoff(inputs={
                'city': city_input,
                'industry': target_industry,
                'service': target_service
            })
            st.session_state['generated'] = True
            st.session_state['city'] = city_input
            st.session_state['service'] = target_service
            
            with open("final_marketing_strategy.md", "r", encoding="utf-8") as f:
                st.session_state['ad_copy'] = f.read()
            with open("full_7day_campaign.md", "r", encoding="utf-8") as f:
                st.session_state['schedule'] = f.read()
            with open("visual_strategy.md", "r", encoding="utf-8") as f:
                st.session_state['vision'] = f.read()

    # --- DISPLAY DASHBOARD ---
    if st.session_state.get('generated'):
        st.success(f"✨ Campaign Ready!")
        tabs = st.tabs(["📝 Ad Copy", "🗓️ Schedule", "🖼️ Visual Assets", "🚀 Push to Ads", "🔬 Diagnostic Lab"])
        
        with tabs[0]: st.markdown(st.session_state['ad_copy'])
        with tabs[1]: st.markdown(st.session_state['schedule'])
        with tabs[2]:
            st.header("Visual Concepts")
            prompts = re.findall(r"AI Image Prompt: (.*)", st.session_state['vision'])
            if prompts:
                for idx, p in enumerate(prompts[:3]):
                    with st.expander(f"Concept {idx+1}"):
                        st.write(p)
                        if st.button(f"Paint Ad {idx+1}", key=f"pnt_{idx}"):
                            url = generate_ad_image(p)
                            if url: st.image(url)
        with tabs[3]:
            st.header("Platform Payloads")
            variations = re.split(r'### Facebook Ad Variation \d:', st.session_state['ad_copy'])
            variations = [v.strip() for v in variations if len(v.strip()) > 50]
            for i, ad_text in enumerate(variations):
                with st.expander(f"Meta Payload {i+1}"):
                    h = re.search(r"\*\*Headline:\*\*\s*(.*)", ad_text)
                    b = re.search(r"\*\*Body Copy:\*\*\s*([\s\S]*?)(?=\*\*Call to Action:|\Z)", ad_text)
                    st.code(b.group(1).strip() if b else ad_text, language="text")
                    st.code(h.group(1) if h else "Local Pro", language="text")
        with tabs[4]:
            st.header("Diagnostic Lab")
            up_file = st.file_uploader("Upload Inspection Photo", type=['jpg', 'jpeg', 'png'])
            if up_file:
                st.image(up_file, width=400)
                if st.button("🔍 Run Inspection"):
                    report = analyze_inspection_photo(up_file.getvalue(), "Analyze for debris and safety risks.")
                    st.markdown(report)

        st.divider()
        full_rpt = f"# {st.session_state['service']} Report: {st.session_state['city']}\n\n" + st.session_state['ad_copy']
        c1, c2, c3 = st.columns(3)
        c1.download_button("📄 Word", create_word_doc(full_rpt), "Report.docx", key="dl_w")
        c2.download_button("📕 PDF", create_pdf(full_rpt), "Report.pdf", key="dl_p")
        c3.download_button("📝 Markdown", full_rpt, "Report.md", key="dl_m")

elif auth_status is False:
    st.error('Username/password is incorrect')