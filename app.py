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
APP_LOGO_PATH = "Logo1.jpeg"  # ensure exists in repo


# ============================================================
# 1) DATABASE: SaaS CORE SCHEMA (ONE TIME)
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

    # --- CORE USERS (RBAC) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',              -- admin | editor | viewer
            is_active INTEGER DEFAULT 1,             -- 1 active, 0 disabled
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001',
            sso_provider TEXT DEFAULT '',            -- placeholder
            mfa_enabled INTEGER DEFAULT 0,           -- placeholder
            last_login TEXT DEFAULT ''               -- ISO string
        )
    """)

    # --- TEAM LEADS (pipeline) ---
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

    # --- AUDIT / ACTIVITY LOGS (security + compliance) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            actor TEXT,
            action_type TEXT,
            object_type TEXT,
            object_id TEXT,
            details TEXT,
            team_id TEXT
        )
    """)

    # --- MARKETING: CAMPAIGNS ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            channel TEXT,          -- email | social | ads | seo | geo | other
            status TEXT,           -- draft | scheduled | live | paused | complete
            start_date TEXT,
            end_date TEXT,
            budget REAL DEFAULT 0,
            owner TEXT,
            team_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            notes TEXT
        )
    """)

    # --- MARKETING: CONTENT / ASSET LIBRARY ---
    # NOTE: Cloud filesystem is ephemeral. Store small files (<=1-2MB) if needed.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            asset_type TEXT,       -- image | template | copy | other
            mime_type TEXT,
            size_bytes INTEGER,
            content BLOB,          -- optional
            owner TEXT,
            team_id TEXT,
            created_at TEXT,
            tags TEXT
        )
    """)

    # --- WORKFLOW AUTOMATION (simple sequences) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            trigger TEXT,
            steps_json TEXT,
            is_enabled INTEGER DEFAULT 1,
            owner TEXT,
            team_id TEXT,
            created_at TEXT
        )
    """)

    # --- INTEGRATIONS (CRM/Analytics/Social) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,             -- Salesforce | HubSpot | GA | Meta | etc
            status TEXT,           -- disconnected | connected | error
            details TEXT,
            team_id TEXT,
            updated_at TEXT
        )
    """)

    # --- BILLING / SUBSCRIPTIONS (simple placeholder) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            plan TEXT,
            seats INTEGER DEFAULT 1,
            renewal_date TEXT,
            status TEXT,           -- active | past_due | canceled
            updated_at TEXT
        )
    """)

    # Migrations / safety (future-proof)
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")
    ensure_column(conn, "users", "is_active", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "sso_provider", "TEXT DEFAULT ''")
    ensure_column(conn, "users", "mfa_enabled", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "last_login", "TEXT DEFAULT ''")

    ensure_column(conn, "leads", "team_id", "TEXT")
    ensure_column(conn, "leads", "timestamp", "DATETIME DEFAULT CURRENT_TIMESTAMP")

    # Seed admin
    admin_pw = stauth.Hasher.hash("admin123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, is_active, plan, credits, verified, team_id, mfa_enabled)
        VALUES
        ('admin', 'admin@tech.ai', 'System Admin', ?, 'admin', 1, 'Unlimited', 9999, 1, 'HQ_001', 0)
    """, (admin_pw,))

    conn.commit()
    conn.close()


def log_event(actor: str, action_type: str, object_type: str = "", object_id: str = "", details: str = "", team_id: str = ""):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("""
            INSERT INTO activity_logs (timestamp, actor, action_type, object_type, object_id, details, team_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), actor, action_type, object_type, str(object_id), details, team_id))
        conn.commit()
        conn.close()
    except Exception:
        # don't crash app on logging failures
        pass


init_db()


# ============================================================
# 2) EXPORTS (EXEC-READY + LITE LOGO HEADER)
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
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        if _should_use_lite_logo() and os.path.exists(APP_LOGO_PATH):
            try:
                pdf.image(APP_LOGO_PATH, x=60, y=10, w=90)
                pdf.ln(30)
            except Exception:
                pass

        pdf.set_font("Arial", "B", 16)
        safe_title = nuclear_ascii(title)
        pdf.cell(0, 10, f"Executive Intelligence Brief: {safe_title}", ln=True, align="C")

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
    if _should_use_lite_logo() and os.path.exists(APP_LOGO_PATH):
        try:
            doc.add_picture(APP_LOGO_PATH, width=Inches(2.5))
        except Exception:
            pass
    doc.add_heading(f"Executive Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# 3) AUTHENTICATION
# ============================================================
def get_db_creds():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users WHERE is_active = 1", conn)
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


# --- Centered, professional auth screen ---
def _centered_auth_shell(title: str, subtitle: str):
    st.markdown("""
    <style>
      .auth-wrap { max-width: 980px; margin: 0 auto; }
      .auth-card {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 16px;
        padding: 22px;
        background: white;
        box-shadow: 0 10px 30px rgba(0,0,0,0.06);
      }
      @media (prefers-color-scheme: dark) {
        .auth-card { background: #0b1220; border-color: rgba(255,255,255,0.10); }
      }
      .auth-title { font-size: 30px; font-weight: 800; margin: 8px 0 2px 0; }
      .auth-sub { opacity: 0.85; margin-bottom: 18px; }
      .tier-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
      @media (max-width: 900px) { .tier-grid { grid-template-columns: 1fr; } }
      .tier { border: 1px solid rgba(0,0,0,0.08); border-radius: 14px; padding: 16px; }
      @media (prefers-color-scheme: dark) { .tier { border-color: rgba(255,255,255,0.10);} }
      .pill { display:inline-block; font-size:12px; padding: 2px 10px; border-radius: 999px; background:#2563EB; color:white; }
      .price { font-size: 28px; font-weight: 900; margin: 0; }
    </style>
    """, unsafe_allow_html=True)

    c = st.columns([1, 2, 1])
    with c[1]:
        st.markdown('<div class="auth-wrap"><div class="auth-card">', unsafe_allow_html=True)
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=160)
        st.markdown(f'<div class="auth-title">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="auth-sub">{subtitle}</div>', unsafe_allow_html=True)
        return True


def _auth_shell_end():
    st.markdown("</div></div>", unsafe_allow_html=True)


if not st.session_state.get("authentication_status"):
    _centered_auth_shell(
        "Marketing Swarm Intelligence",
        "Secure login to launch agents, manage teams, and export executive-ready reports."
    )

    auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])

    with auth_tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            st.rerun()

    with auth_tabs[1]:
        st.markdown("### Choose a plan")
        st.markdown('<div class="tier-grid">', unsafe_allow_html=True)
        a, b, c = st.columns(3)

        with a:
            st.markdown("#### 🥉 LITE")
            st.markdown("<p class='price'>$99 <span style='font-size:14px;font-weight:600'>/mo</span></p>", unsafe_allow_html=True)
            st.write("- 3 seats\n- Standard exports\n- **System logo included**")
            if st.button("Choose Lite", key="p_lite", use_container_width=True):
                st.session_state.selected_tier = "Lite"

        with b:
            st.markdown("#### 🥈 PRO  <span class='pill'>MOST POPULAR</span>", unsafe_allow_html=True)
            st.markdown("<p class='price'>$299 <span style='font-size:14px;font-weight:600'>/mo</span></p>", unsafe_allow_html=True)
            st.write("- 8 seats\n- Custom logo\n- Team pipeline")
            if st.button("Choose Pro", key="p_pro", use_container_width=True):
                st.session_state.selected_tier = "Pro"

        with c:
            st.markdown("#### 🥇 ENTERPRISE")
            st.markdown("<p class='price'>$999 <span style='font-size:14px;font-weight:600'>/mo</span></p>", unsafe_allow_html=True)
            st.write("- Unlimited\n- Admin forensics\n- Integrations")
            if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                st.session_state.selected_tier = "Enterprise"

        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("selected_tier"):
            st.info(f"Selected: **{st.session_state.selected_tier}** — complete registration below.")
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

    _auth_shell_end()
    st.stop()


# ============================================================
# 4) LOAD USER CONTEXT + RBAC
# ============================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
user_row = pd.read_sql_query(
    "SELECT * FROM users WHERE username = ?",
    conn,
    params=(st.session_state["username"],)
).iloc[0]
conn.close()

current_user = user_row.get("username", "")
current_role = str(user_row.get("role", "viewer")).strip().lower()
current_tier = user_row.get("plan", "Lite")
st.session_state["current_tier"] = current_tier
team_id = user_row.get("team_id", "HQ_001")

# Update last login (best-effort)
try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (datetime.utcnow().isoformat(), current_user))
    conn.commit()
    conn.close()
except Exception:
    pass

# RBAC permissions
PERMS = {
    "admin": {"*"},
    "editor": {
        "campaign.create", "campaign.edit", "campaign.view",
        "asset.upload", "asset.view",
        "workflow.manage", "integration.manage",
        "export.data", "view.analytics", "view.team_intel",
        "user.view"
    },
    "viewer": {
        "campaign.view", "asset.view", "view.analytics"
    }
}

def can(perm: str) -> bool:
    perms = PERMS.get(current_role, set())
    return ("*" in perms) or (perm in perms)


# ============================================================
# 5) SIDEBAR (DYNAMIC GEO + ROLE DISPLAY)
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

def get_geo_data_with_custom():
    base = get_geo_data()
    custom = st.session_state.get("custom_geo", {})
    merged = dict(base)
    for st_name, cities in custom.items():
        merged.setdefault(st_name, [])
        for c in cities:
            if c not in merged[st_name]:
                merged[st_name].append(c)
    return merged

with st.sidebar:
    st.success("Authenticated")
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=120)

    st.subheader(f"Welcome, {user_row.get('name','User')}")
    st.caption(f"Role: **{current_role.upper()}** | Team: **{team_id}**")

    current_credits = int(user_row.get("credits", 0))
    st.metric(f"{current_tier} Plan", f"{current_credits} Credits")
    st.divider()

    tier_limits = {"Lite": 3, "Pro": 8, "Enterprise": 8, "Unlimited": 8}
    agent_limit = 8 if current_role == "admin" else tier_limits.get(str(current_tier), 3)

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    custom_logo = None
    if str(current_tier).strip().lower() == "lite" and current_role != "admin":
        st.info("🪪 LITE: System logo is used for executive exports.")
    else:
        custom_logo = st.file_uploader("📤 Custom Brand Logo (Pro+)", type=["png", "jpg", "jpeg"])

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
        st.caption(f"Plan cap: {agent_limit} agents")

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
        for title, key in agent_map:
            toggles[key] = st.toggle(title, value=st.session_state.get(f"tg_{key}", False), key=f"tg_{key}")

        if current_role != "admin" and sum(1 for v in toggles.values() if v) > agent_limit:
            st.warning(f"Selected more than {agent_limit}. Turn some off.")

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
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (current_user,))
            conn.commit()
            conn.close()
            log_event(current_user, "user.verify", "user", current_user, "One-click verify", team_id)
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
            base_payload = {
                "city": full_loc,
                "biz_name": biz_name,
                "package": str(current_tier),
                "custom_logo": custom_logo,
                "directives": agent_info,
            }

            with st.status("🚀 Initializing Swarm Intelligence...", expanded=True) as status:
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
                    log_event(current_user, "swarm.launch", "swarm", "", f"agents={active_agents}", team_id)
                    status.update(label="✅ Swarm Coordination Complete!", state="complete", expanded=False)
                    st.rerun()
                except Exception as e:
                    st.session_state.report = {}
                    st.session_state.gen = False
                    log_event(current_user, "swarm.error", "swarm", "", str(e), team_id)
                    status.update(label="❌ Swarm failed", state="error", expanded=True)
                    st.error(f"Swarm Error: {e}")


# ============================================================
# 7) DASHBOARD TABS + TEAM INTEL (SaaS CORE USER & ACCESS MGMT)
# ============================================================
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: Scans competitors and identifies price-gaps.",
    "ads": "📺 **Ads Architect**: Generates high-converting copy for Meta/Google.",
    "creative": "🎨 **Creative Director**: Provides high-fidelity prompts & creative direction.",
    "strategist": "📝 **Swarm Strategist**: Builds a 30-day CEO-level execution roadmap.",
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


def render_social_push_panel():
    st.markdown("### 🚀 Publish / Push")
    st.caption("Open platform tools to publish or deploy the generated assets.")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.link_button("Google Ads", "https://ads.google.com/home/")
        st.link_button("Google Business Profile", "https://business.google.com/")
    with c2:
        st.link_button("Meta Business Suite", "https://business.facebook.com/latest/")
        st.link_button("Facebook Ads Manager", "https://www.facebook.com/adsmanager/manage/")
    with c3:
        st.link_button("YouTube Studio", "https://studio.youtube.com/")
        st.link_button("LinkedIn Campaign Manager", "https://www.linkedin.com/campaignmanager/")


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

            if key in {"ads", "creative", "social"}:
                st.write("---")
                render_social_push_panel()

            st.write("---")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button("📄 Download Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
            with c2:
                st.download_button("📕 Download PDF", export_pdf(edited, title), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)

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


# -----------------------------
# TEAM INTEL: SaaS CORE USER & ACCESS MANAGEMENT + MARKETING OPS
# -----------------------------
def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Core user & access management + marketing operations modules (RBAC-aware).")

    # Tabs in Team Intel
    t_users, t_activity, t_campaigns, t_assets, t_workflows, t_integrations, t_analytics, t_billing = st.tabs([
        "👥 Users & RBAC",
        "🕵️ Activity Monitoring",
        "📣 Campaigns",
        "🗂️ Asset Library",
        "🤖 Workflow Automation",
        "🔌 Integrations",
        "📊 Analytics",
        "💳 Billing"
    ])

    # ---- USERS & RBAC ----
    with t_users:
        if not can("user.view"):
            st.error("You don’t have permission to view users.")
        else:
            st.subheader("Role-Based Access Control (RBAC)")
            st.write("Roles: **Admin**, **Editor**, **Viewer** — with feature permissions enforced in the UI.")

            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                users_df = pd.read_sql_query(
                    "SELECT username, name, email, role, is_active, plan, verified, team_id, mfa_enabled, sso_provider, last_login "
                    "FROM users WHERE team_id = ? ORDER BY username",
                    conn,
                    params=(team_id,)
                )

            st.dataframe(users_df, use_container_width=True)

            st.write("---")
            colA, colB = st.columns(2)

            # Provision / Deprovision
            with colA:
                st.markdown("### ➕ Provision User")
                if not (current_role in {"admin"}):
                    st.info("Only Admin can provision users.")
                else:
                    with st.form("provision_user"):
                        u_username = st.text_input("Username")
                        u_name = st.text_input("Full Name")
                        u_email = st.text_input("Email")
                        u_role = st.selectbox("Role", ["viewer", "editor", "admin"])
                        u_plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise", "Unlimited"])
                        u_active = st.checkbox("Active", value=True)
                        u_mfa = st.checkbox("MFA Enabled (placeholder)", value=False)
                        u_sso = st.selectbox("SSO Provider (placeholder)", ["", "Google", "Microsoft", "Okta"])
                        u_pw = st.text_input("Temp Password", type="password", help="User should change later.")

                        submit = st.form_submit_button("Create / Update")
                        if submit:
                            if not u_username or not u_pw:
                                st.error("Username and Temp Password are required.")
                            else:
                                hashed = stauth.Hasher.hash(u_pw)
                                with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                                    conn.execute("""
                                        INSERT INTO users (username, name, email, password, role, is_active, plan, verified, team_id, mfa_enabled, sso_provider, last_login)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, '')
                                        ON CONFLICT(username) DO UPDATE SET
                                            name=excluded.name,
                                            email=excluded.email,
                                            password=excluded.password,
                                            role=excluded.role,
                                            is_active=excluded.is_active,
                                            plan=excluded.plan,
                                            mfa_enabled=excluded.mfa_enabled,
                                            sso_provider=excluded.sso_provider,
                                            team_id=excluded.team_id
                                    """, (u_username.strip(), u_name.strip(), u_email.strip(), hashed, u_role, 1 if u_active else 0, u_plan, team_id, 1 if u_mfa else 0, u_sso))
                                    conn.commit()
                                log_event(current_user, "user.provision", "user", u_username, f"role={u_role}, active={u_active}", team_id)
                                st.success("User provisioned/updated.")
                                st.rerun()

            with colB:
                st.markdown("### 📥 Bulk Import (CSV)")
                st.caption("CSV columns: username,name,email,role,plan,is_active,temp_password")

                if current_role != "admin":
                    st.info("Only Admin can bulk import users.")
                else:
                    up = st.file_uploader("Upload CSV", type=["csv"], key="bulk_users")
                    if up is not None:
                        try:
                            df = pd.read_csv(up)
                            st.dataframe(df.head(20), use_container_width=True)
                            if st.button("Import Users"):
                                with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                                    for _, r in df.iterrows():
                                        uname = str(r.get("username", "")).strip()
                                        tpw = str(r.get("temp_password", "")).strip()
                                        if not uname or not tpw:
                                            continue
                                        hashed = stauth.Hasher.hash(tpw)
                                        role_ = str(r.get("role", "viewer")).strip().lower()
                                        if role_ not in {"admin","editor","viewer"}:
                                            role_ = "viewer"
                                        plan_ = str(r.get("plan", "Lite")).strip()
                                        is_active_ = int(r.get("is_active", 1)) if str(r.get("is_active", "1")).strip() != "" else 1
                                        conn.execute("""
                                            INSERT INTO users (username, name, email, password, role, is_active, plan, verified, team_id)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                                            ON CONFLICT(username) DO UPDATE SET
                                                name=excluded.name,
                                                email=excluded.email,
                                                password=excluded.password,
                                                role=excluded.role,
                                                is_active=excluded.is_active,
                                                plan=excluded.plan,
                                                team_id=excluded.team_id
                                        """, (
                                            uname,
                                            str(r.get("name","")).strip(),
                                            str(r.get("email","")).strip(),
                                            hashed,
                                            role_,
                                            1 if is_active_ else 0,
                                            plan_,
                                            team_id
                                        ))
                                    conn.commit()
                                log_event(current_user, "user.bulk_import", "user", "", f"rows={len(df)}", team_id)
                                st.success("Bulk import completed.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"CSV import error: {e}")

            st.write("---")
            st.markdown("### 🔐 Authentication Controls (SSO/MFA placeholders)")
            st.info("SSO and MFA are shown as configuration placeholders. Real SSO/MFA requires an identity provider integration and server-side auth flow.")

            if current_role == "admin":
                with st.expander("Configure SSO/MFA (placeholder)", expanded=False):
                    st.write("Recommended: Okta / Azure AD / Google Workspace SSO + TOTP MFA.")
                    st.write("Implementation note: Streamlit Authenticator is cookie-based; enterprise SSO requires external auth gateway.")
            else:
                st.caption("Ask an Admin to configure SSO/MFA.")

    # ---- ACTIVITY MONITORING ----
    with t_activity:
        if not can("view.team_intel") and current_role != "admin":
            st.error("You don’t have permission to view activity logs.")
        else:
            st.subheader("Activity Monitoring")
            st.caption("Tracks logins, launches, provisioning, exports, and sensitive actions.")

            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                logs_df = pd.read_sql_query(
                    "SELECT timestamp, actor, action_type, object_type, object_id, details "
                    "FROM activity_logs WHERE team_id = ? ORDER BY id DESC LIMIT 200",
                    conn,
                    params=(team_id,)
                )
            st.dataframe(logs_df, use_container_width=True)

    # ---- CAMPAIGNS ----
    with t_campaigns:
        if not can("campaign.view"):
            st.error("You don’t have permission to view campaigns.")
        else:
            st.subheader("Campaign Management")
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                camp_df = pd.read_sql_query(
                    "SELECT id, name, channel, status, start_date, end_date, budget, owner, created_at, updated_at "
                    "FROM campaigns WHERE team_id = ? ORDER BY id DESC",
                    conn,
                    params=(team_id,)
                )
            st.dataframe(camp_df, use_container_width=True)

            if can("campaign.create"):
                st.write("---")
                st.markdown("### ➕ Create Campaign")
                with st.form("create_campaign"):
                    name = st.text_input("Campaign Name")
                    channel = st.selectbox("Channel", ["email", "social", "ads", "seo", "geo", "other"])
                    status_ = st.selectbox("Status", ["draft", "scheduled", "live", "paused", "complete"])
                    start = st.text_input("Start Date (YYYY-MM-DD)", value="")
                    end = st.text_input("End Date (YYYY-MM-DD)", value="")
                    budget = st.number_input("Budget", min_value=0.0, value=0.0, step=50.0)
                    notes = st.text_area("Notes")
                    submit = st.form_submit_button("Create")
                    if submit:
                        if not name.strip():
                            st.error("Campaign name required.")
                        else:
                            now = datetime.utcnow().isoformat()
                            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                                conn.execute("""
                                    INSERT INTO campaigns (name, channel, status, start_date, end_date, budget, owner, team_id, created_at, updated_at, notes)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (name.strip(), channel, status_, start.strip(), end.strip(), float(budget), current_user, team_id, now, now, notes.strip()))
                                conn.commit()
                            log_event(current_user, "campaign.create", "campaign", "", f"name={name}, channel={channel}", team_id)
                            st.success("Campaign created.")
                            st.rerun()
            else:
                st.info("You can view campaigns, but creating/editing requires Editor or Admin role.")

    # ---- ASSET LIBRARY ----
    with t_assets:
        if not can("asset.view"):
            st.error("You don’t have permission to view assets.")
        else:
            st.subheader("Content & Asset Library")
            st.caption("Store creative assets and templates centrally. (Note: Cloud file persistence is limited.)")

            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                assets_df = pd.read_sql_query(
                    "SELECT id, name, asset_type, mime_type, size_bytes, owner, created_at, tags "
                    "FROM assets WHERE team_id = ? ORDER BY id DESC",
                    conn,
                    params=(team_id,)
                )
            st.dataframe(assets_df, use_container_width=True)

            if can("asset.upload"):
                st.write("---")
                up = st.file_uploader("Upload Asset (small files recommended)", type=None)
                col1, col2 = st.columns(2)
                with col1:
                    asset_name = st.text_input("Asset Name")
                    asset_type = st.selectbox("Asset Type", ["image", "template", "copy", "other"])
                with col2:
                    tags = st.text_input("Tags (comma-separated)")
                if up is not None and st.button("Save Asset"):
                    data = up.getvalue()
                    if len(data) > 2_000_000:
                        st.error("File too large for DB storage. Keep assets <= 2MB or store externally.")
                    else:
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute("""
                                INSERT INTO assets (name, asset_type, mime_type, size_bytes, content, owner, team_id, created_at, tags)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                asset_name.strip() or up.name,
                                asset_type,
                                up.type or "",
                                len(data),
                                data,
                                current_user,
                                team_id,
                                datetime.utcnow().isoformat(),
                                tags.strip()
                            ))
                            conn.commit()
                        log_event(current_user, "asset.upload", "asset", "", f"name={asset_name or up.name}", team_id)
                        st.success("Asset saved.")
                        st.rerun()
            else:
                st.info("Upload requires Editor or Admin role.")

    # ---- WORKFLOWS ----
    with t_workflows:
        if not can("workflow.manage") and current_role != "admin":
            st.error("You don’t have permission to manage workflows.")
        else:
            st.subheader("Workflow Automation")
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                wf_df = pd.read_sql_query(
                    "SELECT id, name, trigger, is_enabled, owner, created_at FROM workflows WHERE team_id = ? ORDER BY id DESC",
                    conn,
                    params=(team_id,)
                )
            st.dataframe(wf_df, use_container_width=True)

            st.write("---")
            st.markdown("### ➕ Create Workflow (simple)")
            with st.form("wf_create"):
                wf_name = st.text_input("Workflow Name")
                wf_trigger = st.selectbox("Trigger", ["lead_created", "campaign_scheduled", "approval_required", "manual"])
                steps = st.text_area("Steps JSON", value='["step1","step2"]')
                enabled = st.checkbox("Enabled", value=True)
                submit = st.form_submit_button("Create")
                if submit:
                    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                        conn.execute("""
                            INSERT INTO workflows (name, trigger, steps_json, is_enabled, owner, team_id, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (wf_name.strip(), wf_trigger, steps.strip(), 1 if enabled else 0, current_user, team_id, datetime.utcnow().isoformat()))
                        conn.commit()
                    log_event(current_user, "workflow.create", "workflow", "", wf_name, team_id)
                    st.success("Workflow created.")
                    st.rerun()

    # ---- INTEGRATIONS ----
    with t_integrations:
        if not can("integration.manage") and current_role != "admin":
            st.error("You don’t have permission to manage integrations.")
        else:
            st.subheader("Integrations")
            st.caption("Connect CRM/Analytics/Social tools. (Stored as placeholders; use secrets for real keys.)")

            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                int_df = pd.read_sql_query(
                    "SELECT id, name, status, details, updated_at FROM integrations WHERE team_id = ? ORDER BY id DESC",
                    conn,
                    params=(team_id,)
                )
            st.dataframe(int_df, use_container_width=True)

            st.write("---")
            with st.form("add_integration"):
                name = st.selectbox("Integration", ["Salesforce", "HubSpot", "Google Analytics", "Meta", "Mailchimp", "Other"])
                status_ = st.selectbox("Status", ["disconnected", "connected", "error"])
                details = st.text_area("Details (non-secret)", placeholder="Workspace/Account ID, notes, etc.")
                submit = st.form_submit_button("Save")
                if submit:
                    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                        conn.execute("""
                            INSERT INTO integrations (name, status, details, team_id, updated_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (name, status_, details.strip(), team_id, datetime.utcnow().isoformat()))
                        conn.commit()
                    log_event(current_user, "integration.save", "integration", "", f"{name}:{status_}", team_id)
                    st.success("Integration saved.")
                    st.rerun()

    # ---- ANALYTICS ----
    with t_analytics:
        if not can("view.analytics"):
            st.error("You don’t have permission to view analytics.")
        else:
            st.subheader("Analytics & Reporting")
            st.caption("KPIs, usage analytics, and campaign performance (basic baseline).")

            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                camps = pd.read_sql_query(
                    "SELECT status, channel, budget FROM campaigns WHERE team_id = ?",
                    conn, params=(team_id,)
                )
                logs = pd.read_sql_query(
                    "SELECT action_type FROM activity_logs WHERE team_id = ?",
                    conn, params=(team_id,)
                )

            if camps.empty:
                st.info("No campaigns yet.")
            else:
                st.markdown("#### Campaign Status Breakdown")
                st.bar_chart(camps["status"].value_counts())

                st.markdown("#### Channel Mix")
                st.bar_chart(camps["channel"].value_counts())

            if logs.empty:
                st.info("No activity yet.")
            else:
                st.markdown("#### Usage Analytics (Top actions)")
                st.bar_chart(logs["action_type"].value_counts().head(12))

    # ---- BILLING ----
    with t_billing:
        if current_role != "admin":
            st.info("Billing is visible to Admin only.")
        else:
            st.subheader("Billing Management")
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                bill_df = pd.read_sql_query(
                    "SELECT id, team_id, plan, seats, renewal_date, status, updated_at FROM billing WHERE team_id = ? ORDER BY id DESC",
                    conn, params=(team_id,)
                )
            st.dataframe(bill_df, use_container_width=True)

            st.write("---")
            with st.form("billing_save"):
                plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise", "Unlimited"])
                seats = st.number_input("Seats", min_value=1, value=3, step=1)
                renewal = st.text_input("Renewal Date (YYYY-MM-DD)", value="")
                status_ = st.selectbox("Status", ["active", "past_due", "canceled"])
                submit = st.form_submit_button("Save Billing Record")
                if submit:
                    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                        conn.execute("""
                            INSERT INTO billing (team_id, plan, seats, renewal_date, status, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (team_id, plan, int(seats), renewal.strip(), status_, datetime.utcnow().isoformat()))
                        conn.commit()
                    log_event(current_user, "billing.save", "billing", "", f"{plan}/{seats}/{status_}", team_id)
                    st.success("Billing record saved.")
                    st.rerun()


def render_admin():
    st.header("⚙️ Admin Forensics")
    a1, a2 = st.tabs(["📊 Audit Logs", "🔐 Security"])
    with a1:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT timestamp, actor, action_type, object_type, object_id, details, team_id "
                "FROM activity_logs ORDER BY id DESC LIMIT 300",
                conn
            )
        st.dataframe(df, use_container_width=True)
    with a2:
        st.info("Advanced security configuration lives in Team Intel (SSO/MFA placeholders).")


# ---- Build tab labels ----
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if current_role == "admin":
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
