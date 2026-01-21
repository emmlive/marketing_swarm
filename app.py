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
APP_LOGO_PATH = "Logo1.jpeg"  # ensure this exists in your repo root


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
            channel TEXT,
            status TEXT,
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            asset_type TEXT,
            mime_type TEXT,
            size_bytes INTEGER,
            content BLOB,
            owner TEXT,
            team_id TEXT,
            created_at TEXT,
            tags TEXT
        )
    """)

    # --- WORKFLOW AUTOMATION ---
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

    # --- INTEGRATIONS ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT,
            details TEXT,
            team_id TEXT,
            updated_at TEXT
        )
    """)

    # --- BILLING ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            plan TEXT,
            seats INTEGER DEFAULT 1,
            renewal_date TEXT,
            status TEXT,
            updated_at TEXT
        )
    """)

    # Migrations
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")
    ensure_column(conn, "users", "is_active", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "plan", "TEXT DEFAULT 'Lite'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "verified", "INTEGER DEFAULT 0")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'HQ_001'")
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

        # LITE: include system logo on exports
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
            doc.add_picture(APP_LOGO_PATH, width=Inches(2.4))
        except Exception:
            pass
    doc.add_heading(f"Executive Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# 3) AUTHENTICATION (CENTERED, PROFESSIONAL)
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


def render_login_screen():
    st.markdown("""
    <style>
      .bg {
        position: fixed; inset: 0;
        background:
          radial-gradient(1000px 600px at 18% 15%, rgba(37,99,235,0.20), transparent 55%),
          radial-gradient(900px 560px at 86% 28%, rgba(168,85,247,0.18), transparent 55%),
          radial-gradient(900px 560px at 50% 85%, rgba(34,197,94,0.10), transparent 60%),
          linear-gradient(180deg, #060a18, #070b18);
        z-index: -1;
      }
      .card {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 22px;
        background: rgba(255,255,255,0.06);
        box-shadow: 0 30px 90px rgba(0,0,0,0.45);
        backdrop-filter: blur(10px);
        padding: 22px;
      }
      .title {
        color: white;
        font-size: 38px;
        font-weight: 900;
        margin: 6px 0 6px;
        letter-spacing: -0.02em;
      }
      .sub {
        color: rgba(255,255,255,0.82);
        font-size: 14px;
        margin: 0 0 16px;
      }
      .chip {
        display:inline-flex; align-items:center; gap:8px;
        border: 1px solid rgba(255,255,255,0.14);
        padding: 6px 12px;
        border-radius: 999px;
        color: rgba(255,255,255,0.88);
        font-size: 12px;
      }
      .muted { color: rgba(255,255,255,0.76); font-size: 13px; }
      .kpi { display:grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-top: 14px; }
      .kpi > div { border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 12px; background: rgba(255,255,255,0.04); }
      .kpi b { color:white; }
      @media (max-width: 980px) { .kpi { grid-template-columns: 1fr; } .title{font-size:32px;} }
    </style>
    <div class="bg"></div>
    """, unsafe_allow_html=True)

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        top = st.columns([1, 3])
        with top[0]:
            if os.path.exists(APP_LOGO_PATH):
                st.image(APP_LOGO_PATH, width=120)
        with top[1]:
            st.markdown('<div class="chip">🧠 AI Marketing OS • Secure • Multi-Agent</div>', unsafe_allow_html=True)
            st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
            st.markdown('<div class="sub">A modern SaaS command center for research, creative production, governance, and executive reporting.</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="kpi">
          <div><b>RBAC</b><br><span class="muted">Admin • Editor • Viewer</span></div>
          <div><b>Audit Trails</b><br><span class="muted">Compliance-ready activity logs</span></div>
          <div><b>Exports</b><br><span class="muted">Executive Word/PDF</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")

        auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])

        with auth_tabs[0]:
            authenticator.login(location="main")
            if st.session_state.get("authentication_status"):
                st.rerun()

        with auth_tabs[1]:
            st.subheader("Plans")
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown("#### 🥉 LITE")
                st.markdown("**$99/mo**")
                st.write("- 3 agents\n- Standard exports\n- System logo on reports")
                if st.button("Choose Lite", key="p_lite", use_container_width=True):
                    st.session_state.selected_tier = "Lite"

            with c2:
                st.markdown("#### 🥈 PRO")
                st.markdown("**$299/mo**")
                st.write("- 8 agents\n- Custom logo\n- Team modules")
                if st.button("Choose Pro", key="p_pro", use_container_width=True):
                    st.session_state.selected_tier = "Pro"

            with c3:
                st.markdown("#### 🥇 ENTERPRISE")
                st.markdown("**$999/mo**")
                st.write("- Unlimited\n- Admin suite\n- Integrations")
                if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                    st.session_state.selected_tier = "Enterprise"

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

        st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.get("authentication_status"):
    render_login_screen()
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
team_id = user_row.get("team_id", "HQ_001")
st.session_state["current_tier"] = current_tier  # used by exports

# Update last login
try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (datetime.utcnow().isoformat(), current_user))
    conn.commit()
    conn.close()
    log_event(current_user, "auth.login", "user", current_user, "login_success", team_id)
except Exception:
    pass


PERMS = {
    "admin": {"*"},
    "editor": {
        "view.team_intel", "view.analytics", "export.data",
        "campaign.create", "campaign.edit", "campaign.view",
        "asset.upload", "asset.view",
        "workflow.manage", "integration.manage",
        "user.view"
    },
    "viewer": {"campaign.view", "asset.view", "view.analytics"}
}


def can(perm: str) -> bool:
    perms = PERMS.get(current_role, set())
    return ("*" in perms) or (perm in perms)


# ============================================================
# 5) SIDEBAR + DYNAMIC GEO
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
    st.metric(f"{current_tier} Plan", f"{int(user_row.get('credits', 0))} Credits")
    st.divider()

    tier_limits = {"Lite": 3, "Pro": 8, "Enterprise": 8, "Unlimited": 8}
    agent_limit = 8 if current_role == "admin" else tier_limits.get(str(current_tier), 3)

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    custom_logo = None
    if str(current_tier).strip().lower() == "lite" and current_role != "admin":
        st.info("🪪 LITE: System logo used on executive exports.")
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
                log_event(current_user, "geo.add_state", "geo", new_state.strip(), "", team_id)
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
                log_event(current_user, "geo.add_city", "geo", f"{selected_state}:{new_city.strip()}", "", team_id)
                st.rerun()
        selected_city = (geo_dict.get(selected_state) or [""])[0]

    full_loc = f"{selected_city}, {selected_state}"

    st.divider()

    agent_info = st.text_area("✍️ Strategic Directives", placeholder="Injected into all agent prompts...")

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

        # Keep prior selections
        toggles = {k: st.toggle(t, value=st.session_state.get(f"tg_{k}", False), key=f"tg_{k}") for t, k in agent_map}

        if current_role != "admin" and sum(1 for v in toggles.values() if v) > agent_limit:
            st.warning(f"Selected more than {agent_limit}. Turn some off.")

    st.divider()

    run_btn = False
    if int(user_row.get("verified", 0)) == 1:
        if int(user_row.get("credits", 0)) > 0:
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
            log_event(current_user, "user.verify", "user", current_user, "one_click_verify", team_id)
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
# 7) DASHBOARD TABS + HELPERS
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
    st.caption("Open platform consoles to publish or deploy the generated assets.")
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
    st.info(f"Command Center Active for: {st.session_state.get('biz_name', biz_name or 'Global Mission')}")
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


# ============================================================
# TEAM INTEL TAB (FIXED: now defined to prevent NameError)
# ============================================================
def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Core SaaS operations view: users, campaigns, assets, workflows, integrations, analytics snapshots.")

    # Snapshots
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        users_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM users WHERE is_active=1", conn)["c"].iloc[0]
        camp_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM campaigns", conn)["c"].iloc[0]
        asset_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM assets", conn)["c"].iloc[0]
        wf_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM workflows WHERE is_enabled=1", conn)["c"].iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active Users", int(users_cnt))
    k2.metric("Campaigns", int(camp_cnt))
    k3.metric("Assets", int(asset_cnt))
    k4.metric("Enabled Workflows", int(wf_cnt))

    st.write("---")

    t1, t2, t3 = st.tabs(["📌 Pipeline", "📣 Campaigns", "🗂️ Assets"])

    # Pipeline
    with t1:
        st.subheader("Lead / Pipeline (Team)")
        try:
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                if current_role == "admin":
                    df = pd.read_sql_query("SELECT * FROM leads ORDER BY id DESC", conn)
                else:
                    df = pd.read_sql_query(
                        "SELECT * FROM leads WHERE team_id = ? ORDER BY id DESC",
                        conn,
                        params=(team_id,)
                    )
            if df.empty:
                st.info("Pipeline currently empty.")
            else:
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Pipeline Error: {e}")

    # Campaigns
    with t2:
        st.subheader("Campaign Management")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT id, name, channel, status, start_date, end_date, budget, owner, team_id, created_at, updated_at "
                "FROM campaigns ORDER BY id DESC",
                conn
            )
        st.dataframe(df, use_container_width=True)

        if can("campaign.create") or current_role == "admin":
            with st.expander("➕ Create Campaign", expanded=False):
                with st.form("create_campaign"):
                    name = st.text_input("Campaign Name")
                    channel = st.selectbox("Channel", ["Email", "Social", "Search Ads", "Display", "Video", "Other"])
                    status = st.selectbox("Status", ["Draft", "Scheduled", "Live", "Paused", "Completed"])
                    start_date = st.text_input("Start Date (YYYY-MM-DD)", value="")
                    end_date = st.text_input("End Date (YYYY-MM-DD)", value="")
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
                                """, (name.strip(), channel, status, start_date.strip(), end_date.strip(), float(budget), current_user, team_id, now, now, notes.strip()))
                                conn.commit()
                            log_event(current_user, "campaign.create", "campaign", name.strip(), f"channel={channel}", team_id)
                            st.success("Campaign created.")
                            st.rerun()
        else:
            st.info("Upgrade role to Editor/Admin to create campaigns.")

    # Assets
    with t3:
        st.subheader("Content & Asset Library")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT id, name, asset_type, mime_type, size_bytes, owner, team_id, created_at, tags FROM assets ORDER BY id DESC",
                conn
            )
        st.dataframe(df, use_container_width=True)

        if can("asset.upload") or current_role == "admin":
            with st.expander("📤 Upload Asset", expanded=False):
                up = st.file_uploader("Upload (png/jpg/pdf/docx/txt)", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"])
                asset_type = st.selectbox("Asset Type", ["Image", "Template", "Copy", "Document", "Other"])
                tags = st.text_input("Tags (comma-separated)")
                if st.button("Save Asset"):
                    if up is None:
                        st.error("Upload a file first.")
                    else:
                        data = up.getvalue()
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute("""
                                INSERT INTO assets (name, asset_type, mime_type, size_bytes, content, owner, team_id, created_at, tags)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (up.name, asset_type, up.type or "", len(data), data, current_user, team_id, datetime.utcnow().isoformat(), tags.strip()))
                            conn.commit()
                        log_event(current_user, "asset.upload", "asset", up.name, asset_type, team_id)
                        st.success("Asset saved.")
                        st.rerun()
        else:
            st.info("Upgrade role to Editor/Admin to upload assets.")


# ============================================================
# ADMIN TAB: Full SaaS Admin Suite
# ============================================================
def render_admin():
    st.header("⚙ Admin Console")
    st.caption("Enterprise admin suite aligned with SaaS requirements.")

    if current_role != "admin":
        st.info("Admin-only view.")
        return

    a_users, a_marketing, a_analytics, a_workflows, a_security = st.tabs([
        "👥 User & Access",
        "📣 Marketing Config",
        "📊 Analytics & Reporting",
        "🤖 Automation & Workflows",
        "🔐 Security & Compliance"
    ])

    # --- USER & ACCESS MGMT ---
    with a_users:
        st.subheader("User & Access Management")
        st.write("RBAC roles: Admin, Editor, Viewer. SSO/MFA shown as placeholders.")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT username, name, email, role, is_active, plan, verified, team_id, mfa_enabled, sso_provider, last_login "
                "FROM users ORDER BY username",
                conn
            )
        st.dataframe(df, use_container_width=True)

        st.write("---")
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("### ➕ Onboarding / Provision User")
            with st.form("admin_create_user"):
                u = st.text_input("Username")
                n = st.text_input("Full Name")
                e = st.text_input("Email")
                r = st.selectbox("Role", ["viewer", "editor", "admin"])
                p = st.selectbox("Plan", ["Lite", "Pro", "Enterprise", "Unlimited"])
                active = st.checkbox("Active", value=True)
                mfa = st.checkbox("MFA Enabled (placeholder)", value=False)
                sso = st.selectbox("SSO Provider (placeholder)", ["", "Google", "Microsoft", "Okta"])
                pw = st.text_input("Temp Password", type="password")
                submit = st.form_submit_button("Create / Update")
                if submit:
                    if not u.strip() or not pw.strip():
                        st.error("Username and Temp Password required.")
                    else:
                        hashed = stauth.Hasher.hash(pw.strip())
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
                            """, (u.strip(), n.strip(), e.strip(), hashed, r, 1 if active else 0, p, team_id, 1 if mfa else 0, sso))
                            conn.commit()
                        log_event(current_user, "user.onboard", "user", u.strip(), f"role={r},active={active}", team_id)
                        st.success("User created/updated.")
                        st.rerun()

        with c2:
            st.markdown("### 📴 Offboarding / Deactivate User")
            target = st.selectbox("Select user", df["username"].tolist(), key="admin_off_user")
            if st.button("Deactivate"):
                if target == current_user:
                    st.error("You cannot deactivate yourself.")
                else:
                    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                        conn.execute("UPDATE users SET is_active = 0 WHERE username = ?", (target,))
                        conn.commit()
                    log_event(current_user, "user.offboard", "user", target, "deactivated", team_id)
                    st.success("User deactivated.")
                    st.rerun()

    # --- MARKETING CONFIG ---
    with a_marketing:
        st.subheader("Marketing Configuration")
        st.caption("Campaign setup, content, channels, and asset controls.")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            camp = pd.read_sql_query(
                "SELECT id, name, channel, status, start_date, end_date, budget, owner, team_id, created_at, updated_at FROM campaigns ORDER BY id DESC",
                conn
            )
            assets = pd.read_sql_query(
                "SELECT id, name, asset_type, mime_type, size_bytes, owner, team_id, created_at, tags FROM assets ORDER BY id DESC",
                conn
            )
        st.markdown("#### Campaigns")
        st.dataframe(camp, use_container_width=True)
        st.markdown("#### Assets")
        st.dataframe(assets, use_container_width=True)

    # --- ANALYTICS & REPORTING ---
    with a_analytics:
        st.subheader("Analytics & Reporting")
        st.caption("Performance tracking, segmentation-ready dashboards, and usage analytics.")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            logs = pd.read_sql_query("SELECT action_type FROM activity_logs ORDER BY id DESC LIMIT 2000", conn)
            camps = pd.read_sql_query("SELECT status, channel, budget FROM campaigns", conn)

        if not logs.empty:
            st.markdown("#### Usage Analytics")
            st.bar_chart(logs["action_type"].value_counts().head(12))
        else:
            st.info("No usage data yet.")

        if not camps.empty:
            st.markdown("#### Campaign Status")
            st.bar_chart(camps["status"].value_counts())
            st.markdown("#### Channel Mix")
            st.bar_chart(camps["channel"].value_counts())
        else:
            st.info("No campaigns yet.")

    # --- AUTOMATION & WORKFLOWS ---
    with a_workflows:
        st.subheader("Automation & Workflows")
        st.caption("Journeys, triggers, integrations, and approvals (baseline).")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            wf = pd.read_sql_query("SELECT id, name, trigger, is_enabled, owner, team_id, created_at FROM workflows ORDER BY id DESC", conn)
            integ = pd.read_sql_query("SELECT id, name, status, details, team_id, updated_at FROM integrations ORDER BY id DESC", conn)
        st.markdown("#### Workflows")
        st.dataframe(wf, use_container_width=True)
        st.markdown("#### Integrations")
        st.dataframe(integ, use_container_width=True)

    # --- SECURITY & COMPLIANCE ---
    with a_security:
        st.subheader("Security & Compliance")
        st.caption("Audit logs, data security posture, and usage monitoring.")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT timestamp, actor, action_type, object_type, object_id, details, team_id FROM activity_logs ORDER BY id DESC LIMIT 400",
                conn
            )
        st.dataframe(df, use_container_width=True)
        st.info("SSO/MFA are placeholders here. For production SaaS, integrate an identity provider (Okta/AzureAD/Google) and enforce MFA at the IdP.")


# ============================================================
# 8) RENDER TABS
# ============================================================
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel", "⚙ Admin"]

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

with TAB["⚙ Admin"]:
    render_admin()
