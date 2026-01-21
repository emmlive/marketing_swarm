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
# 3) AUTHENTICATION (FUTURISTIC MAXIMIZED UI)
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
      .ms-bg {
        position: fixed; inset: 0;
        background: radial-gradient(1200px 800px at 20% 20%, rgba(37,99,235,0.25), transparent 55%),
                    radial-gradient(1200px 800px at 80% 30%, rgba(168,85,247,0.22), transparent 55%),
                    radial-gradient(1200px 800px at 50% 80%, rgba(34,197,94,0.12), transparent 55%),
                    linear-gradient(180deg, rgba(2,6,23,1), rgba(3,7,18,1));
        z-index: -1;
      }
      .ms-shell { max-width: 1080px; margin: 0 auto; padding: 44px 18px; }
      .ms-hero {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 22px;
        padding: 28px;
        background: rgba(255,255,255,0.06);
        backdrop-filter: blur(10px);
        box-shadow: 0 25px 70px rgba(0,0,0,0.35);
      }
      .ms-title { font-size: 44px; font-weight: 900; letter-spacing: -0.02em; color: #fff; margin: 10px 0 6px; }
      .ms-sub { color: rgba(255,255,255,0.82); font-size: 16px; margin: 0 0 18px; }
      .ms-chip { display:inline-flex; align-items:center; gap:8px; padding:6px 12px; border-radius:999px;
                 border:1px solid rgba(255,255,255,0.14); color: rgba(255,255,255,0.90); font-size: 12px; }
      .ms-grid { display:grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; margin-top: 16px; }
      @media (max-width: 980px) { .ms-grid { grid-template-columns: 1fr; } .ms-title{font-size:36px;} }
      .ms-panel {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 18px;
        background: rgba(255,255,255,0.05);
      }
      .ms-kpi { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }
      @media (max-width: 980px) { .ms-kpi { grid-template-columns: 1fr; } }
      .ms-kpi-card {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        padding: 12px;
        background: rgba(255,255,255,0.04);
      }
      .ms-kpi-card b { color:#fff; }
      .ms-kpi-card span { color: rgba(255,255,255,0.72); font-size: 12px; }
      .ms-muted { color: rgba(255,255,255,0.72); }
      .stTabs [data-baseweb="tab"] { color: rgba(255,255,255,0.86) !important; }
    </style>
    <div class="ms-bg"></div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ms-shell"><div class="ms-hero">', unsafe_allow_html=True)

    top = st.columns([1, 3])
    with top[0]:
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=140)
    with top[1]:
        st.markdown('<div class="ms-chip">🧠 AI Marketing OS • Secure • Multi-Agent</div>', unsafe_allow_html=True)
        st.markdown('<div class="ms-title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="ms-sub">A state-of-the-art SaaS command center for multi-agent marketing research, creative production, governance, and executive reporting.</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="ms-kpi">
      <div class="ms-kpi-card"><b>RBAC</b><br><span>Admin • Editor • Viewer</span></div>
      <div class="ms-kpi-card"><b>Audit Trails</b><br><span>Compliance-ready activity logging</span></div>
      <div class="ms-kpi-card"><b>Exports</b><br><span>Executive-ready Word/PDF</span></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ms-grid">', unsafe_allow_html=True)
    st.markdown('<div class="ms-panel">', unsafe_allow_html=True)

    auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "🤝 Join Team", "❓ Forget Password"])

    with auth_tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            st.rerun()

    with auth_tabs[1]:
        st.markdown("### Plans")
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("#### 🥉 LITE")
            st.markdown("**$99/mo**")
            st.write("- 3 seats\n- Standard exports\n- System logo on reports")
            if st.button("Choose Lite", key="p_lite", use_container_width=True):
                st.session_state.selected_tier = "Lite"

        with c2:
            st.markdown("#### 🥈 PRO")
            st.markdown("**$299/mo**")
            st.write("- 8 seats\n- Custom logo\n- Team modules")
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

    st.markdown('</div>', unsafe_allow_html=True)  # panel

    # Right panel: “future look” feature list
    st.markdown("""
    <div class="ms-panel">
      <h3 style="margin-top:0;color:#fff;">What you get</h3>
      <div class="ms-muted">
        <ul>
          <li><b>Multi-agent Swarm</b> for market research, creative, SEO, GEO, audit.</li>
          <li><b>Governance</b> with RBAC, audit logs, and compliance controls.</li>
          <li><b>Marketing Ops</b> campaigns, assets, workflows, integrations.</li>
          <li><b>Analytics</b> adoption, performance tracking, segmentation-ready.</li>
        </ul>
      </div>
      <hr style="border:0;border-top:1px solid rgba(255,255,255,0.12);margin:14px 0;">
      <div class="ms-muted" style="font-size:12px;">
        Tip: Use <b>Lite</b> for quick wins. Upgrade to unlock custom branding and advanced controls.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('</div></div></div>', unsafe_allow_html=True)  # grid/hero/shell


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
st.session_state["current_tier"] = current_tier
team_id = user_row.get("team_id", "HQ_001")

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
        "campaign.create", "campaign.edit", "campaign.view",
        "asset.upload", "asset.view",
        "workflow.manage", "integration.manage",
        "export.data", "view.analytics", "view.team_intel",
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
        st.info("🪪 LITE: System logo used for executive exports.")
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
            log_event(current_user, "user.verify", "user", current_user, "One-click verify", team_id)
            st.rerun()

    authenticator.logout("🔒 Sign Out", "sidebar")


# ============================================================
# 6) RUN SWARM (BATCHED)
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
# 7) DASHBOARD TABS
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


# ============================================================
# ADMIN TAB: Full SaaS Admin Suite (as requested)
# ============================================================
def render_admin():
    st.header("⚙ Admin Console")
    st.caption("Enterprise admin suite aligned with SaaS requirements.")

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
        if current_role != "admin":
            st.info("Admin-only view.")
        else:
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
                "SELECT id, name, channel, status, start_date, end_date, budget, owner, created_at, updated_at FROM campaigns ORDER BY id DESC",
                conn
            )
            assets = pd.read_sql_query(
                "SELECT id, name, asset_type, mime_type, size_bytes, owner, created_at, tags FROM assets ORDER BY id DESC",
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
            wf = pd.read_sql_query("SELECT id, name, trigger, is_enabled, owner, created_at FROM workflows ORDER BY id DESC", conn)
            integ = pd.read_sql_query("SELECT id, name, status, details, updated_at FROM integrations ORDER BY id DESC", conn)
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


# ---- Build tab labels ----
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
    # Team Intel can show team modules; Admin is the governance console
    # Keeping Team Intel as a lighter ops view; Admin as full governance.
    st.info("Team Intel modules are available in Admin Console. Use Admin for governance, RBAC, and compliance.")
    render_team_intel()

with TAB["⚙ Admin"]:
    render_admin()
