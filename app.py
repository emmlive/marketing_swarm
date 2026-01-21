import os
import re
import unicodedata
import sqlite3
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from docx import Document
from fpdf import FPDF
import fpdf

from main import run_marketing_swarm


# ============================================================
# 0) CONFIG
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")


# ============================================================
# 1) DATABASE: SCHEMA + ADMIN SEED (ONE TIME)
# ============================================================
DB_PATH = "breatheeasy.db"

def ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str):
    """Adds a column if it doesn't exist."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()

    # USERS: single, consistent schema (username PRIMARY KEY)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'user',
            plan TEXT DEFAULT 'Basic',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001'
        )
    """)

    # LEADS: for Team Intel
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            city TEXT,
            service TEXT,
            status TEXT DEFAULT 'Discovery',
            team_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # AUDIT LOGS: admin forensics
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user TEXT,
            action_type TEXT,
            target_biz TEXT,
            location TEXT,
            status TEXT
        )
    """)

    # Migrations / safety
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'user'")
    ensure_column(conn, "users", "plan", "TEXT DEFAULT 'Basic'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "verified", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'HQ_001'")

    ensure_column(conn, "leads", "team_id", "TEXT")
    ensure_column(conn, "leads", "timestamp", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    # Seed/refresh admin record
    admin_pw = stauth.Hasher.hash("admin123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, plan, credits, verified, team_id)
        VALUES
        ('admin', 'admin@tech.ai', 'System Admin', ?, 'admin', 'Unlimited', 9999, 1, 'HQ_001')
    """, (admin_pw,))

    conn.commit()
    conn.close()

init_db()


# ============================================================
# 2) FPDF HARDENING (KEEP YOUR PATCH)
# ============================================================
_original_putpages = fpdf.fpdf.FPDF._putpages

def _patched_putpages(self):
    pages = self.pages
    self.pages = {}
    for k, v in pages.items():
        if isinstance(v, str):
            v = v.encode("latin-1", "ignore").decode("latin-1", "ignore")
        self.pages[k] = v
    _original_putpages(self)

fpdf.fpdf.FPDF._putpages = _patched_putpages

def nuclear_ascii(text):
    if text is None:
        return ""
    text = str(text)
    text = unicodedata.normalize("NFKD", text)
    text = (
        text.replace("\u200b", "")
            .replace("\u200c", "")
            .replace("\u200d", "")
            .replace("\ufeff", "")
    )
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text

def export_pdf(content, title):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font("Arial", "B", 16)
        safe_title = nuclear_ascii(title)
        pdf.cell(0, 10, f"Intelligence Brief: {safe_title}", ln=True, align="C")

        pdf.set_font("Arial", size=10)
        safe_body = nuclear_ascii(content).replace("\r", "")
        safe_body = "\n".join(line[:900] for line in safe_body.split("\n"))
        pdf.multi_cell(0, 7, safe_body)

        return pdf.output(dest="S").encode("latin-1")

    except Exception:
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Arial", size=12)
        fallback.multi_cell(0, 10, "PDF GENERATION FAILED\n\nContent was sanitized.\nError was handled safely.")
        return fallback.output(dest="S").encode("latin-1")

def export_word(content, title):
    doc = Document()
    doc.add_heading(f"Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# 3) AUTHENTICATION (SINGLE FLOW)
# ============================================================
def get_db_creds():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users", conn)
        return {
            "usernames": {
                r["username"]: {
                    "email": r.get("email", ""),
                    "name": r.get("name", r["username"]),
                    "password": r["password"],
                }
                for _, r in df.iterrows()
            }
        }
    finally:
        conn.close()

if "authenticator" not in st.session_state:
    # Requires Streamlit secrets cookie keys
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(),
        st.secrets["cookie"]["name"],
        st.secrets["cookie"]["key"],
        30
    )

authenticator = st.session_state.authenticator

if not st.session_state.get("authentication_status"):
    st.image("Logo1.jpeg", width=220)
    st.title("🚀 Marketing Swarm Intelligence")
    st.markdown("---")

    auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])

    with auth_tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            st.rerun()

    with auth_tabs[1]:
        st.subheader("Select Your Swarm Package")
        p1, p2, p3 = st.columns(3)

        with p1:
            st.markdown("""
            <div style="border:1px solid #E5E7EB; padding:20px; border-radius:10px; text-align:center;">
                <h3>🥉 LITE</h3>
                <h2 style="color:#2563EB;">$99<small>/mo</small></h2>
                <p><i>The "Solopreneur" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li>3 Specialized Agents</li>
                    <li>Standard PDF Reports</li>
                    <li>Single User Access</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Lite", key="p_lite", use_container_width=True):
                st.session_state.selected_tier = "lite"

        with p2:
            st.markdown("""
            <div style="border:2px solid #2563EB; padding:20px; border-radius:10px; text-align:center; background-color:#F8FAFC;">
                <span style="background-color:#2563EB; color:white; padding:2px 10px; border-radius:5px; font-size:12px;">MOST POPULAR</span>
                <h3>🥈 PRO</h3>
                <h2 style="color:#2563EB;">$299<small>/mo</small></h2>
                <p><i>The "Growth" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li><b>All 8 AI Agents</b></li>
                    <li>White-label Word/PDF</li>
                    <li>Team Kanban Pipeline</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Pro", key="p_pro", use_container_width=True):
                st.session_state.selected_tier = "pro"

        with p3:
            st.markdown("""
            <div style="border:1px solid #E5E7EB; padding:20px; border-radius:10px; text-align:center;">
                <h3>🥇 ENTERPRISE</h3>
                <h2 style="color:#2563EB;">$999<small>/mo</small></h2>
                <p><i>The "Global" Swarm</i></p>
                <ul style="text-align:left; font-size:14px;">
                    <li>Unlimited Swarms</li>
                    <li>Admin Forensics Hub</li>
                    <li>API & Custom Training</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                st.session_state.selected_tier = "enterprise"

        if st.session_state.get("selected_tier"):
            st.info(f"✨ You've selected **{st.session_state.selected_tier.upper()}**. Complete registration below:")
            try:
                if authenticator.register_user(location="main"):
                    st.success("Account created! Switch to Login tab.")
            except Exception as e:
                st.error(f"Registration error: {e}")

    with auth_tabs[2]:
        st.subheader("🤝 Request Enterprise Team Access")
        with st.form("team_request_form"):
            team_id_req = st.text_input("Enterprise Team ID", placeholder="e.g., HQ_NORTH_2026")
            reason = st.text_area("Purpose of Access", placeholder="e.g., Regional Marketing Analyst")
            if st.form_submit_button("Submit Access Request", use_container_width=True):
                st.success(f"Request for Team {team_id_req} logged. Status: PENDING.")

    with auth_tabs[3]:
        authenticator.forgot_password(location="main")

    st.stop()


# ============================================================
# 4) LOAD USER CONTEXT (AFTER AUTH)
# ============================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
user_row = pd.read_sql_query(
    "SELECT * FROM users WHERE username = ?",
    conn,
    params=(st.session_state["username"],)
).iloc[0]
conn.close()

role = str(user_row.get("role", "")).strip().lower()
is_admin = role == "admin"


# ============================================================
# 5) SIDEBAR CONTROLS
# ============================================================
@st.cache_data(ttl=3600)
def get_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

with st.sidebar:
    st.success("Authenticated")
    st.image("Logo1.jpeg", width=120)
    st.subheader(f"Welcome, {user_row.get('name','User')}")

    current_tier = user_row.get("plan", "Basic")
    current_credits = int(user_row.get("credits", 0))

    st.metric(f"{current_tier} Plan", f"{current_credits} Credits")
    st.divider()

    tier_limits = {"Basic": 3, "Pro": 5, "Enterprise": 8, "Unlimited": 8}
    agent_limit = 8 if is_admin else tier_limits.get(current_tier, 3)

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    custom_logo = None
    if current_tier == "Basic" and not is_admin:
        st.info("💡 Basic Plan: System branding active. Upgrade for custom logos.")
    else:
        custom_logo = st.file_uploader("📤 Custom Brand Logo (Pro+)", type=["png", "jpg", "jpeg"])

    geo_dict = get_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo_dict.keys()))
    selected_city = st.selectbox("🏙️ Target City", sorted(geo_dict[selected_state]))
    full_loc = f"{selected_city}, {selected_state}"

    st.divider()

    agent_info = st.text_area(
        "✍️ Strategic Directives",
        placeholder="Injected into all agent prompts...",
        help="Define specific goals like 'luxury focus' or 'emergency speed'."
    )

    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Status: {current_tier} | Max: {agent_limit} Agents")

        agent_map = [
            ("🕵️ Analyst", "analyst"),
            ("📺 Ads", "ads"),
            ("🎨 Creative", "creative"),
            ("👔 Strategist", "strategist"),
            ("📱 Social", "social"),
            ("📍 GEO", "geo"),
            ("🌐 Auditor", "audit"),
            ("✍ SEO", "seo"),
        ]

        toggles = {}
        active_count = sum(1 for _, k in agent_map if st.session_state.get(f"tg_{k}", False))

        for title, key in agent_map:
            disable_toggle = (not is_admin) and active_count >= agent_limit and not st.session_state.get(f"tg_{key}", False)
            default_val = True if key in ["analyst", "audit", "seo"] and active_count < 3 else st.session_state.get(f"tg_{key}", False)
            toggles[key] = st.toggle(title, value=default_val, disabled=disable_toggle, key=f"tg_{key}")

        if not is_admin and sum(1 for v in toggles.values() if v) >= agent_limit:
            st.warning(f"Agent limit reached for {current_tier} plan.")

    st.divider()

    run_btn = False
    if int(user_row.get("verified", 0)) == 1:
        if current_credits > 0:
            run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
        else:
            st.error("💳 Out of Credits")
    else:
        st.error("🛡️ Verification Required")
        if st.button("🔓 One-Click Verify"):
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (user_row["username"],))
            conn.commit()
            conn.close()
            st.rerun()

    authenticator.logout("🔒 Sign Out", "sidebar")


# ============================================================
# 6) RUN SWARM
# ============================================================
if run_btn:
    if not biz_name:
        st.error("🚨 Please enter a Brand Name before launching.")
    else:
        active_agents = [k for k, v in toggles.items() if v]

        with st.status("🚀 Initializing Swarm Intelligence...", expanded=True) as status:
            st.write(f"📡 Dispatching {len(active_agents)} agents for {biz_name}...")

            report = run_marketing_swarm({
                "city": full_loc,
                "biz_name": biz_name,
                "active_swarm": active_agents,
                "package": current_tier,
                "custom_logo": custom_logo,
                "directives": agent_info
            })

            st.session_state.report = report
            st.session_state.gen = True

            status.update(label="✅ Swarm Coordination Complete!", state="complete", expanded=False)

        st.rerun()


# ============================================================
# 7) DASHBOARD: TABS (ONE AND ONLY ONE)
# ============================================================
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: Scans competitors and identifies price-gaps.",
    "ads": "📺 **Ads Architect**: Generates high-converting copy for Meta/Google.",
    "creative": "🎨 **Creative Director**: Provides high-fidelity image prompts.",
    "strategist": "📝 **Swarm Strategist**: Builds a 30-day CEO-level ROI roadmap.",
    "social": "📱 **Social Engineer**: Crafts engagement-driven posts.",
    "geo": "📍 **Geo-Fencer**: Optimizes local map rankings.",
    "audit": "🔍 **Technical Auditor**: Finds site 'leaks' and speed issues.",
    "seo": "📝 **SEO Architect**: Builds content clusters for SGE ranking."
}

DEPLOY_GUIDES = {
    "analyst": "Identify price-gaps to undercut rivals.",
    "ads": "Translate platform hooks into ad headlines and angles.",
    "creative": "Use prompts for Midjourney/Canva conversion assets.",
    "strategist": "30-day CEO roadmap. Start with Phase 1 quick wins.",
    "social": "Deploy viral hooks and community engagement posts.",
    "geo": "Update citations and optimize for 'near me' search intent.",
    "audit": "Patch technical leaks to improve speed and conversions.",
    "seo": "Publish for SGE and optimize for zero-click answers."
}

def show_deploy_guide(title: str, key: str):
    st.markdown(
        f"""
        <div style="background-color:#f0f2f6; padding:14px; border-radius:10px;
                    border-left: 5px solid #2563EB; margin-bottom: 14px;">
            <b style="color:#0f172a;">🚀 {title.upper()} DEPLOYMENT GUIDE:</b><br>
            <span style="color:#334155;">{DEPLOY_GUIDES.get(key, "Intelligence Gathering")}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: {st.session_state.get('biz_name', 'Global Mission')}")
    st.subheader("Agent Specializations")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)
    st.markdown("---")
    st.markdown("### 🛡️ Swarm Execution Protocol")
    st.write("1) Launch from the sidebar\n2) Edit inside the Agent Seat\n3) Export using Word/PDF buttons")

def render_agent_seat(title: str, key: str):
    st.subheader(f"🚀 {title} Seat")
    show_deploy_guide(title, key)

    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report:
        content = report.get(key)
        if content:
            edited = st.text_area("Refine Intel", value=str(content), height=400, key=f"ed_{key}")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📄 Download Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}")
            with c2:
                st.download_button("📕 Download PDF", export_pdf(edited, title), file_name=f"{key}.pdf", key=f"p_{key}")
        else:
            st.warning("Agent not selected for this run.")
    else:
        st.info("System Standby. Launch from sidebar.")

def render_vision():
    st.header("👁️ Visual Intelligence")
    st.write("Visual audits and image analysis results appear here.")

def render_veo():
    st.header("🎬 Veo Video Studio")
    st.write("AI video generation assets appear here.")

def render_team_intel():
    st.header("🤝 Global Team Pipeline")
    try:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            if is_admin:
                team_df = pd.read_sql_query("SELECT * FROM leads ORDER BY id DESC", conn)
            else:
                team_df = pd.read_sql_query(
                    "SELECT * FROM leads WHERE team_id = ? ORDER BY id DESC",
                    conn,
                    params=(user_row.get("team_id"),)
                )

        if team_df.empty:
            st.info("Pipeline currently empty.")
        else:
            st.dataframe(team_df, use_container_width=True)
    except Exception as e:
        st.error(f"Team Intel Error: {e}")

def render_admin():
    st.header("⚙️ Admin Forensics")
    admin_sub1, admin_sub2, admin_sub3 = st.tabs(["📊 Logs", "👥 Users", "🔐 Security"])

    with admin_sub1:
        st.subheader("Global Activity Audit")
        try:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                audit_df = pd.read_sql_query("SELECT * FROM master_audit_logs ORDER BY id DESC LIMIT 50", conn)
            st.dataframe(audit_df, use_container_width=True)
        except Exception as e:
            st.info(f"No audit logs found yet (or table missing). Details: {e}")

    with admin_sub2:
        st.subheader("Subscriber Management")
        try:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                users_df = pd.read_sql_query("SELECT username, name, email, plan, role, credits, verified, team_id FROM users", conn)
            st.dataframe(users_df, use_container_width=True)
        except Exception as e:
            st.error(f"User Manager Error: {e}")

    with admin_sub3:
        st.subheader("Credential Overrides")
        try:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                users_list_df = pd.read_sql_query("SELECT username FROM users", conn)

            if users_list_df.empty:
                st.info("No users available to reset.")
                return

            target_p = st.selectbox("Reset Password For:", users_list_df["username"].tolist(), key="p_mgr")
            new_p = st.text_input("New Secure Password", type="password")

            if st.button("🛠️ Reset & Hash Credentials"):
                if not new_p:
                    st.error("Enter a new password first.")
                else:
                    hashed_p = stauth.Hasher.hash(new_p)
                    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                        conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_p, target_p))
                        conn.commit()
                    st.success(f"Password reset for {target_p}!")

        except Exception as e:
            st.error(f"Security Tab Error: {e}")


# ---- Build tab labels (includes Team Intel + Admin) ----
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_admin:
    tab_labels.append("⚙ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (title, key) in agent_map:
    with TAB[title]:
        render_agent_seat(title, key)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "⚙ Admin" in TAB:
    with TAB["⚙ Admin"]:
        render_admin()
