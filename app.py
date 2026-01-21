import os
import re
import time
import base64
import unicodedata
import sqlite3
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from docx import Document
from docx.shared import Inches
from fpdf import FPDF
import fpdf

from main import run_marketing_swarm


# ============================================================
# 0) CONFIG
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")
DB_PATH = "breatheeasy.db"
APP_LOGO_PATH = "Logo1.jpeg"   # make sure this file exists in your repo


# ============================================================
# 1) DATABASE: SCHEMA + ADMIN SEED (ONE TIME)
# ============================================================
def ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")


def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'user',
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001'
        )
    """)

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

    ensure_column(conn, "users", "role", "TEXT DEFAULT 'user'")
    ensure_column(conn, "users", "plan", "TEXT DEFAULT 'Lite'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "verified", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'HQ_001'")

    ensure_column(conn, "leads", "team_id", "TEXT")
    ensure_column(conn, "leads", "timestamp", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    # Seed admin
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
# 2) FPDF HARDENING
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


def _should_use_lite_logo() -> bool:
    plan = st.session_state.get("current_tier", "") or ""
    return str(plan).strip().lower() == "lite"


def export_pdf(content, title):
    """
    Executive-ready PDF:
    - Adds Logo1.jpeg header for LITE plan
    - Sanitizes content for FPDF
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Logo for LITE
        if _should_use_lite_logo() and os.path.exists(APP_LOGO_PATH):
            try:
                pdf.image(APP_LOGO_PATH, x=60, y=10, w=90)
                pdf.ln(30)
            except Exception:
                pass

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
        fallback.multi_cell(
            0, 10,
            "PDF GENERATION FAILED\n\nContent was sanitized.\nError was handled safely."
        )
        return fallback.output(dest="S").encode("latin-1")


def export_word(content, title):
    """
    Executive-ready Word:
    - Adds Logo1.jpeg header for LITE plan
    """
    doc = Document()

    if _should_use_lite_logo() and os.path.exists(APP_LOGO_PATH):
        try:
            doc.add_picture(APP_LOGO_PATH, width=Inches(2.5))
        except Exception:
            pass

    doc.add_heading(f"Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))

    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# 3) AUTHENTICATION (SINGLE FLOW) + PRO LOOK
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
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(),
        st.secrets["cookie"]["name"],
        st.secrets["cookie"]["key"],
        30
    )

authenticator = st.session_state.authenticator


def _centered_card_start():
    st.markdown("""
    <style>
      .auth-wrap { max-width: 980px; margin: 0 auto; }
      .auth-card {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 16px;
        padding: 22px 22px;
        background: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.06);
      }
      @media (prefers-color-scheme: dark) {
        .auth-card { background: #0b1220; border-color: rgba(255,255,255,0.10); }
      }
      .auth-title { font-size: 30px; font-weight: 700; margin: 6px 0 2px 0; }
      .auth-sub { opacity: 0.8; margin-bottom: 18px; }
      .tier-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
      @media (max-width: 900px) { .tier-grid { grid-template-columns: 1fr; } }
      .tier {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 14px;
        padding: 16px 16px;
        background: rgba(255,255,255,0.6);
      }
      @media (prefers-color-scheme: dark) {
        .tier { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.10); }
      }
      .tier h3 { margin: 0 0 6px 0; }
      .tier .price { font-size: 28px; font-weight: 800; margin: 0 0 6px 0; }
      .pill { display:inline-block; font-size:12px; padding: 2px 10px; border-radius: 999px; background:#2563EB; color:white; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="auth-wrap"><div class="auth-card">', unsafe_allow_html=True)


def _centered_card_end():
    st.markdown("</div></div>", unsafe_allow_html=True)


if not st.session_state.get("authentication_status"):
    cols = st.columns([1, 2, 1])
    with cols[1]:
        _centered_card_start()

        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=160)
        st.markdown('<div class="auth-title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="auth-sub">Login to launch agents, generate executive briefs, and export client-ready reports.</div>', unsafe_allow_html=True)

        auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])

        # --- Login ---
        with auth_tabs[0]:
            authenticator.login(location="main")
            if st.session_state.get("authentication_status"):
                st.rerun()

        # --- Pricing & Sign Up ---
        with auth_tabs[1]:
            st.markdown("### Choose a plan")
            st.markdown('<div class="tier-grid">', unsafe_allow_html=True)

            cA, cB, cC = st.columns(3)

            # LITE
            with cA:
                st.markdown('<div class="tier">', unsafe_allow_html=True)
                st.markdown("#### 🥉 LITE")
                st.markdown('<div class="price">$99 <span style="font-size:14px; font-weight:600;">/mo</span></div>', unsafe_allow_html=True)
                st.write("- 3 Specialized Agents\n- Standard PDF/Word\n- Single user access\n- **Executive logo header included**")
                if st.button("Choose Lite", key="p_lite", use_container_width=True):
                    st.session_state.selected_tier = "Lite"
                st.markdown("</div>", unsafe_allow_html=True)

            # PRO
            with cB:
                st.markdown('<div class="tier">', unsafe_allow_html=True)
                st.markdown("#### 🥈 PRO  <span class='pill'>MOST POPULAR</span>", unsafe_allow_html=True)
                st.markdown('<div class="price">$299 <span style="font-size:14px; font-weight:600;">/mo</span></div>', unsafe_allow_html=True)
                st.write("- All 8 agents\n- White-label exports\n- Team pipeline\n- Custom logo allowed")
                if st.button("Choose Pro", key="p_pro", use_container_width=True):
                    st.session_state.selected_tier = "Pro"
                st.markdown("</div>", unsafe_allow_html=True)

            # ENTERPRISE
            with cC:
                st.markdown('<div class="tier">', unsafe_allow_html=True)
                st.markdown("#### 🥇 ENTERPRISE")
                st.markdown('<div class="price">$999 <span style="font-size:14px; font-weight:600;">/mo</span></div>', unsafe_allow_html=True)
                st.write("- Unlimited swarms\n- Admin forensics\n- API & custom training\n- Priority support")
                if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                    st.session_state.selected_tier = "Enterprise"
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

            if st.session_state.get("selected_tier"):
                st.info(f"Selected: **{st.session_state.selected_tier}** — complete registration below.")
                try:
                    created = authenticator.register_user(location="main")
                    if created:
                        # NOTE: streamlit_authenticator doesn't reliably expose the new username across versions.
                        # Users can log in right away; plan assignment can be handled later if needed.
                        st.success("Account created! Switch to **Login** tab to sign in.")
                except Exception as e:
                    st.error(f"Registration error: {e}")

        # --- Join Team ---
        with auth_tabs[2]:
            st.subheader("🤝 Request Enterprise Team Access")
            with st.form("team_request_form"):
                team_id_req = st.text_input("Enterprise Team ID", placeholder="e.g., HQ_NORTH_2026")
                reason = st.text_area("Purpose of Access", placeholder="e.g., Regional Marketing Analyst")
                if st.form_submit_button("Submit Access Request", use_container_width=True):
                    st.success(f"Request for Team {team_id_req} logged. Status: PENDING.")

        # --- Forgot Password ---
        with auth_tabs[3]:
            authenticator.forgot_password(location="main")

        _centered_card_end()

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

current_tier = user_row.get("plan", "Lite")
st.session_state["current_tier"] = current_tier  # used by export functions


# ============================================================
# 5) SIDEBAR CONTROLS (DYNAMIC GEO)
# ============================================================
@st.cache_data(ttl=3600)
def get_geo_data():
    # base list
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }


def get_geo_data_with_custom():
    base = get_geo_data()
    custom = st.session_state.get("custom_geo", {})
    # custom structure: {state: [cities]}
    merged = dict(base)
    for st_name, cities in custom.items():
        if st_name not in merged:
            merged[st_name] = []
        for c in cities:
            if c not in merged[st_name]:
                merged[st_name].append(c)
    return merged


with st.sidebar:
    st.success("Authenticated")
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=120)
    st.subheader(f"Welcome, {user_row.get('name','User')}")

    current_credits = int(user_row.get("credits", 0))
    st.metric(f"{current_tier} Plan", f"{current_credits} Credits")
    st.divider()

    tier_limits = {"Lite": 3, "Pro": 8, "Enterprise": 8, "Unlimited": 8}
    agent_limit = 8 if is_admin else tier_limits.get(str(current_tier), 3)

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    # Logo policy: Lite shows system logo in exports; Pro+ can upload custom
    custom_logo = None
    if str(current_tier).strip().lower() in {"lite"} and not is_admin:
        st.info("🪪 LITE: System logo + executive header will be used in exports.")
    else:
        custom_logo = st.file_uploader("📤 Custom Brand Logo (Pro+)", type=["png", "jpg", "jpeg"])

    # Dynamic GEO
    geo_dict = get_geo_data_with_custom()
    states = sorted(list(geo_dict.keys())) + ["➕ Add new state..."]
    selected_state = st.selectbox("🎯 Target State", states)

    if selected_state == "➕ Add new state...":
        new_state = st.text_input("New State Name")
        if st.button("Add State"):
            if new_state.strip():
                custom_geo = st.session_state.get("custom_geo", {})
                custom_geo.setdefault(new_state.strip(), [])
                st.session_state["custom_geo"] = custom_geo
                st.rerun()
        selected_state = sorted(get_geo_data_with_custom().keys())[0]

    cities = sorted(geo_dict.get(selected_state, [])) + ["➕ Add new city..."]
    selected_city = st.selectbox("🏙️ Target City", cities)

    if selected_city == "➕ Add new city...":
        new_city = st.text_input("New City Name")
        if st.button("Add City"):
            if new_city.strip():
                custom_geo = st.session_state.get("custom_geo", {})
                custom_geo.setdefault(selected_state, [])
                if new_city.strip() not in custom_geo[selected_state]:
                    custom_geo[selected_state].append(new_city.strip())
                st.session_state["custom_geo"] = custom_geo
                st.rerun()
        selected_city = (geo_dict.get(selected_state) or [""])[0]

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
        # use current stored toggles
        for title, key in agent_map:
            toggles[key] = st.toggle(title, value=st.session_state.get(f"tg_{key}", False), key=f"tg_{key}")

        # enforce limits for non-admin by warning only (no hard disable, so UX stays smooth)
        if not is_admin and sum(1 for v in toggles.values() if v) > agent_limit:
            st.warning(f"Selected more than {agent_limit} agents. Please turn some off.")

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
# 6) RUN SWARM (BATCHED TO AVOID 429)
# ============================================================
def run_swarm_in_batches(base_payload: dict, agents: list[str], batch_size: int = 3, pause_sec: int = 20, max_retries: int = 2):
    final_report: dict = {}
    total = len(agents)

    for start in range(0, total, batch_size):
        batch = agents[start:start + batch_size]
        st.write(f"🧩 Running batch {start+1}-{start+len(batch)} of {total}: {batch}")

        attempt = 0
        while True:
            try:
                payload = dict(base_payload)
                payload["active_swarm"] = batch
                partial = run_marketing_swarm(payload) or {}
                final_report.update(partial)
                break
            except Exception as e:
                msg = str(e)
                is_429 = ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg)
                attempt += 1

                if is_429 and attempt <= max_retries:
                    wait = pause_sec * attempt
                    st.warning(f"⚠️ Rate limited (429). Waiting {wait}s then retrying this batch...")
                    time.sleep(wait)
                    continue
                raise

        if start + batch_size < total:
            st.info(f"🧊 Cooling down {pause_sec}s before next batch...")
            time.sleep(pause_sec)

    return final_report


if run_btn:
    if not biz_name:
        st.error("🚨 Please enter a Brand Name before launching.")
    else:
        active_agents = [k for k, v in toggles.items() if v]
        if not active_agents:
            st.warning("Select at least one agent before launching.")
        else:
            # NOTE: The package name is used by main.py branding logic
            package_name = str(current_tier)

            base_payload = {
                "city": full_loc,
                "biz_name": biz_name,
                "package": package_name,
                "custom_logo": custom_logo,
                "directives": agent_info,
                # optional: if you later collect a website URL:
                # "url": website_url,
            }

            with st.status("🚀 Initializing Swarm Intelligence...", expanded=True) as status:
                st.write(f"📡 Preparing {len(active_agents)} agents for {biz_name} (batched)…")

                try:
                    report = run_swarm_in_batches(
                        base_payload=base_payload,
                        agents=active_agents,
                        batch_size=3,
                        pause_sec=20,
                        max_retries=2
                    )

                    st.session_state.report = report
                    st.session_state.gen = True

                    status.update(label="✅ Swarm Coordination Complete!", state="complete", expanded=False)
                    st.rerun()

                except Exception as e:
                    st.session_state.report = {}
                    st.session_state.gen = False
                    status.update(label="❌ Swarm failed", state="error", expanded=True)
                    st.error(f"Swarm Error: {e}")


# ============================================================
# 7) DASHBOARD: TABS + SOCIAL PUSH BUTTONS
# ============================================================
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: Scans competitors and identifies price-gaps.",
    "ads": "📺 **Ads Architect**: Generates high-converting copy for Meta/Google.",
    "creative": "🎨 **Creative Director**: Provides high-fidelity image prompts & creative direction.",
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


def render_social_push_panel(context_key: str):
    """
    Social push links (opens external platform tools).
    Shown for Ads/Creative/Social tabs after content exists.
    """
    st.markdown("### 🚀 Publish / Push")
    st.caption("Open the platform tools below to publish or deploy the generated assets.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.link_button("Google Ads", "https://ads.google.com/home/")
        st.link_button("Google Business Profile", "https://business.google.com/")
    with c2:
        st.link_button("Meta Business Suite", "https://business.facebook.com/latest/")
        st.link_button("Facebook Ads Manager", "https://www.facebook.com/adsmanager/manage/")
    with c3:
        st.link_button("Instagram (Creator)", "https://business.facebook.com/creatorstudio/")
        st.link_button("YouTube Studio", "https://studio.youtube.com/")


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
            edited = st.text_area("Refine Intel", value=str(content), height=420, key=f"ed_{key}")

            # Social push panel for certain outputs
            if key in {"ads", "creative", "social"}:
                st.write("---")
                render_social_push_panel(key)

            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "📄 Download Word",
                    export_word(edited, title),
                    file_name=f"{key}.docx",
                    key=f"w_{key}",
                    use_container_width=True
                )
            with c2:
                st.download_button(
                    "📕 Download PDF",
                    export_pdf(edited, title),
                    file_name=f"{key}.pdf",
                    key=f"p_{key}",
                    use_container_width=True
                )
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
                users_df = pd.read_sql_query(
                    "SELECT username, name, email, plan, role, credits, verified, team_id FROM users",
                    conn
                )
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


# ---- Build tab labels ----
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
