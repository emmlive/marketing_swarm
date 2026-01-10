# --- 8. PROTECTED DASHBOARD ---
@st.dialog("🎓 Strategy Masterclass")
def video_tutorial():
    st.write("How to close $10k+ clients using these reports.")
    st.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    if st.button("Close"): st.rerun()

if st.session_state["authentication_status"]:
    username = st.session_state["username"]
    user_info = get_users_from_db()['usernames'].get(username, {})
    user_tier = user_info.get('package', 'Basic')
    user_logo = user_info.get('logo_path')

with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        if st.button("🎓 Video Tutorial"): video_tutorial()
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        if PACKAGE_CONFIG[user_tier]["branding"]:
            with st.expander("🎨 Custom Branding"):
                logo_file = st.file_uploader("Upload Company Logo", type=['png', 'jpg'])
                if logo_file:
                    os.makedirs("logos", exist_ok=True)
                    user_logo = f"logos/{username}.png"
                    with open(user_logo, "wb") as f: f.write(logo_file.getvalue())
                    conn = sqlite3.connect('breatheeasy.db')
                    conn.cursor().execute("UPDATE users SET logo_path = ? WHERE username = ?", (user_logo, username))
                    conn.commit(); conn.close(); st.success("Branding Applied!")

BREATHEEASY AI - MONTHLY PERFORMANCE REPORT
    --------------------------------------------
    📈 USER GROWTH: Total Members: {new_users}
    💰 REVENUE SUMMARY: Pro: {pro_count} | Unlimited: {unlimited_count} | EST. TOTAL: ${total_rev}
    🛠️ TOP SERVICES:
    {service_summary.to_string(index=False)}
    """
    conn.close()
    return send_admin_alert("Monthly Revenue & Usage Report", report_body)

# --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['name']} <span class='tier-badge'>{user_tier}</span>", unsafe_allow_html=True)
        authenticator.logout('Sign Out', 'sidebar')
        st.divider()

        if user_tier == "Basic":
            with st.expander("🎟️ Redeem Coupon"):
                coupon_code = st.text_input("Promo Code")
                if st.button("Apply"):
                    if coupon_code == "BreatheFree2026":
                        update_user_package(username, "Pro", "SELF_REDEEM")
                        # Alert for Coupon Usage
                        send_admin_alert("Coupon Redeemed", f"User {username} successfully used coupon 'BreatheFree2026' to upgrade to PRO.")
                        st.success("Upgraded!")
                        st.rerun()

        st.subheader("📁 Asset Manager")
        max_f = PACKAGE_CONFIG[user_tier]["max_files"]
        uploaded_media = st.file_uploader(f"Max {max_f} assets", accept_multiple_files=True, type=['png', 'jpg', 'mp4'])
        
        st.divider()
        full_map = {
            "HVAC": ["Full System Replacement", "IAQ"], "Plumbing": ["Sewer Repair", "Tankless Heaters"],
            "Restoration": ["Water Damage", "Mold Remediation"], "Roofing": ["Roof Replacement", "Storm Damage"],
            "Solar": ["Solar Grid Install"], "Custom": ["Manual Entry"]
        }
        allowed = PACKAGE_CONFIG[user_tier]["allowed_industries"]
        main_cat = st.selectbox("Industry", [i for i in full_map.keys() if i in allowed])
        target_service = st.selectbox("Service", full_map[main_cat]) if main_cat != "Custom" else st.text_input("Service")
        city_input = st.text_input("City", placeholder="Naperville, IL")

        include_blog = st.toggle("📝 SEO Blog Content", value=True) if PACKAGE_CONFIG[user_tier]["blog"] else False
        run_button = st.button("🚀 LAUNCH SWARM", type="primary", use_container_width=True)

    # --- MAIN TABS ---
    tab_list = ["🔥 Launchpad", "📊 Database", "📱 Social Preview", "💎 Pricing"]
    if username == "admin": tab_list.append("🛠️ Admin Panel")
    tabs = st.tabs(tab_list)
