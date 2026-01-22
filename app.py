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
APP_LOGO_PATH = "Logo1.jpeg"


# ============================================================
# 1) CSS (LOAD ONCE) + BLINK REDUCTION
# ============================================================
def load_css_once():
    if st.session_state.get("_css_loaded"):
        return
    st.session_state["_css_loaded"] = True

    st.markdown("""
    <style>
      .ms-login-wrap { max-width: 980px; margin: 36px auto; padding: 0 12px; }
      .ms-login-card {
        border: 1px solid rgba(0,0,0,0.10);
        border-radius: 20px;
        overflow: hidden;
        background: white;
        box-shadow: 0 24px 70px rgba(0,0,0,0.08);
      }
      @media (prefers-color-scheme: dark) {
        .ms-login-card { background: #0b1220; border-color: rgba(255,255,255,0.12); }
      }
      .ms-login-hero {
        padding: 22px 22px 16px 22px;
        background: radial-gradient(900px 300px at 20% 10%, rgba(37,99,235,0.25), transparent 55%),
                    radial-gradient(900px 300px at 80% 20%, rgba(168,85,247,0.20), transparent 55%),
                    linear-gradient(180deg, rgba(2,6,23,1), rgba(8,12,26,1));
      }
      .ms-login-title { color:#fff; font-size: 38px; font-weight: 900; margin: 0; letter-spacing: -0.02em; }
      .ms-login-sub { color: rgba(255,255,255,0.82); margin-top: 8px; margin-bottom: 0; font-size: 14px; }
      .ms-chip {
        display:inline-flex; align-items:center; gap:8px;
        padding: 6px 12px; border-radius: 999px;
        border: 1px solid rgba(255,255,255,0.14);
        color: rgba(255,255,255,0.9);
        font-size: 12px;
      }
      .ms-login-body { padding: 18px 22px 22px 22px; }
      .ms-kpis { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
      @media (max-width: 980px) { .ms-kpis { grid-template-columns: 1fr; } }
      .ms-kpi { border: 1px solid rgba(255,255,255,0.12); border-radius: 14px; padding: 12px; background: rgba(255,255,255,0.06); }
      .ms-kpi b { color:#fff; }
      .ms-kpi span { color: rgba(255,255,255,0.75); font-size: 12px; }

      /* Hide sidebar on login to reduce layout shifts */
      [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# 2) DATABASE: SaaS CORE SCHEMA (ONE TIME PER SESSION)
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

    # USERS (org-scoped by team_id)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',          -- admin | editor | viewer
            is_active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001',
            sso_provider TEXT DEFAULT '',
            mfa_enabled INTEGER DEFAULT 0,
            last_login TEXT DEFAULT ''
        )
    """)

    # Activity logs (org scoped)
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

    # Leads
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

    # Campaigns
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

    # Assets
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

    # Workflows
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

    # Integrations
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

    # Billing / subscriptions (Stripe ready placeholders)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            plan TEXT,
            seats INTEGER DEFAULT 1,
            renewal_date TEXT,
            status TEXT,
            stripe_customer_id TEXT DEFAULT '',
            stripe_subscription_id TEXT DEFAULT '',
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

    ensure_column(conn, "billing", "stripe_customer_id", "TEXT DEFAULT ''")
    ensure_column(conn, "billing", "stripe_subscription_id", "TEXT DEFAULT ''")

    # Seed PLATFORM admin (not visible to customer orgs)
    platform_pw = stauth.Hasher.hash("admin123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, is_active, plan, credits, verified, team_id, mfa_enabled)
        VALUES
        ('platform_admin', 'admin@tech.ai', 'Platform Admin', ?, 'admin', 1, 'Unlimited', 9999, 1, 'PLATFORM', 0)
    """, (platform_pw,))

    # Optional: seed demo org admin for HQ_001
    org_admin_pw = stauth.Hasher.hash("admin123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, is_active, plan, credits, verified, team_id, mfa_enabled)
        VALUES
        ('admin', 'orgadmin@tech.ai', 'Org Admin', ?, 'admin', 1, 'Pro', 9999, 1, 'HQ_001', 0)
    """, (org_admin_pw,))

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


if not st.session_state.get("_db_inited"):
    init_db()
    st.session_state["_db_inited"] = True


# ============================================================
# 3) SEAT LIMITS (PLAN ENFORCEMENT)
# ============================================================
SEAT_LIMITS = {
    "lite": 1,          # adjust if you want
    "pro": 5,
    "enterprise": 25,
    "unlimited": 10_000_000
}

def get_seat_limit(plan: str) -> int:
    return SEAT_LIMITS.get(str(plan).strip().lower(), 1)


# ============================================================
# 4) EXPORTS (EXEC-READY + LITE LOGO HEADER)
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
            doc.add_picture(APP_LOGO_PATH, width=Inches(2.4))
        except Exception:
            pass
    doc.add_heading(f"Executive Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# 5) AUTHENTICATION
# ============================================================
def get_db_creds():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query(
            "SELECT username, email, name, password FROM users WHERE is_active = 1",
            conn
        )
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
    load_css_once()

    st.markdown('<div class="ms-login-wrap"><div class="ms-login-card">', unsafe_allow_html=True)
    st.markdown('<div class="ms-login-hero">', unsafe_allow_html=True)

    top = st.columns([1, 3])
    with top[0]:
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=110)
    with top[1]:
        st.markdown('<div class="ms-chip">🧠 AI Marketing OS • Secure • Multi-Agent</div>', unsafe_allow_html=True)
        st.markdown('<h1 class="ms-login-title">Marketing Swarm Intelligence</h1>', unsafe_allow_html=True)
        st.markdown('<p class="ms-login-sub">Campaign ops, governance, analytics & executive reporting — organization-scoped.</p>', unsafe_allow_html=True)
        st.markdown("""
        <div class="ms-kpis">
          <div class="ms-kpi"><b>RBAC</b><br><span>Admin • Editor • Viewer</span></div>
          <div class="ms-kpi"><b>Audit Trails</b><br><span>Login, actions, exports</span></div>
          <div class="ms-kpi"><b>Org Isolation</b><br><span>Team-scoped data access</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # hero
    st.markdown('<div class="ms-login-body">', unsafe_allow_html=True)

    auth_tabs = st.tabs(["🔑 Login", "✨ Pricing & Sign Up", "💳 Billing (Stripe)", "❓ Forgot Password"])

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
            st.write("- 1 seat\n- Standard exports\n- System logo on reports")
            if st.button("Choose Lite", key="p_lite", use_container_width=True):
                st.session_state.selected_tier = "Lite"
        with c2:
            st.markdown("#### 🥈 PRO")
            st.markdown("**$299/mo**")
            st.write("- 5 seats\n- Team Intel\n- Advanced modules")
            if st.button("Choose Pro", key="p_pro", use_container_width=True):
                st.session_state.selected_tier = "Pro"
        with c3:
            st.markdown("#### 🥇 ENTERPRISE")
            st.markdown("**$999/mo**")
            st.write("- 25 seats\n- Governance\n- Integrations")
            if st.button("Choose Enterprise", key="p_ent", use_container_width=True):
                st.session_state.selected_tier = "Enterprise"

        if st.session_state.get("selected_tier"):
            st.info(f"Selected: **{st.session_state.selected_tier}** — complete registration below.")
            try:
                if authenticator.register_user(location="main"):
                    st.success("Account created! Switch to Login tab.")
            except Exception as e:
                st.error(f"Registration error: {e}")

    # Stripe billing placeholder (client-side redirect)
    with auth_tabs[2]:
        st.subheader("Stripe Billing (Checkout Links)")
        st.caption("Paste your Stripe Checkout links in Streamlit secrets to enable live payments.")
        st.markdown("""
**Required secrets (examples):**
- `STRIPE_CHECKOUT_LITE_URL`
- `STRIPE_CHECKOUT_PRO_URL`
- `STRIPE_CHECKOUT_ENTERPRISE_URL`

When users click a plan, they’ll be redirected to Stripe Checkout.
""")
        lite_url = st.secrets.get("STRIPE_CHECKOUT_LITE_URL", "")
        pro_url = st.secrets.get("STRIPE_CHECKOUT_PRO_URL", "")
        ent_url = st.secrets.get("STRIPE_CHECKOUT_ENTERPRISE_URL", "")

        b1, b2, b3 = st.columns(3)
        with b1:
            if lite_url:
                st.link_button("Pay for LITE", lite_url)
            else:
                st.info("Add STRIPE_CHECKOUT_LITE_URL")
        with b2:
            if pro_url:
                st.link_button("Pay for PRO", pro_url)
            else:
                st.info("Add STRIPE_CHECKOUT_PRO_URL")
        with b3:
            if ent_url:
                st.link_button("Pay for ENTERPRISE", ent_url)
            else:
                st.info("Add STRIPE_CHECKOUT_ENTERPRISE_URL")

        st.info("Server-side Stripe verification requires a webhook endpoint (not included in Streamlit-only app).")

    with auth_tabs[3]:
        authenticator.forgot_password(location="main")

    st.markdown("</div>", unsafe_allow_html=True)  # body
    st.markdown("</div></div>", unsafe_allow_html=True)  # card/wrap


if not st.session_state.get("authentication_status"):
    render_login_screen()
    st.stop()


# ============================================================
# 6) LOAD USER CONTEXT + ORG ISOLATION
# ============================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
user_row = pd.read_sql_query(
    "SELECT * FROM users WHERE username = ? AND is_active = 1",
    conn,
    params=(st.session_state["username"],)
).iloc[0]
conn.close()

current_user = user_row.get("username", "")
current_role = str(user_row.get("role", "viewer")).strip().lower()
current_tier = str(user_row.get("plan", "Lite"))
team_id = user_row.get("team_id", "HQ_001")
st.session_state["current_tier"] = current_tier

# last login + audit
try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (datetime.utcnow().isoformat(), current_user))
    conn.commit()
    conn.close()
    log_event(current_user, "auth.login", "user", current_user, "login_success", team_id)
except Exception:
    pass


# ============================================================
# 7) RBAC PERMS
# ============================================================
PERMS = {
    "admin": {"*"},
    "editor": {
        "user.view",
        "campaign.view", "campaign.create", "campaign.edit",
        "asset.view", "asset.upload",
        "workflow.view", "workflow.manage",
        "integration.view", "integration.manage",
        "analytics.view",
        "export.data",
        "logs.view",
    },
    "viewer": {
        "campaign.view",
        "asset.view",
        "workflow.view",
        "integration.view",
        "analytics.view",
    }
}

def can(perm: str) -> bool:
    p = PERMS.get(current_role, set())
    return ("*" in p) or (perm in p)


# ============================================================
# 8) SIDEBAR (DYNAMIC GEO + AGENTS)
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
    st.caption(f"Role: **{current_role.upper()}** | Org: **{team_id}**")
    st.metric(f"{current_tier} Plan", f"{int(user_row.get('credits', 0))} Credits")
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    custom_logo = None
    if current_tier.strip().lower() == "lite" and current_role != "admin":
        st.info("🪪 LITE: System logo used on exports.")
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

    # Agent toggles
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

    # Agent limit by plan (kept from earlier logic)
    tier_agent_limits = {"lite": 3, "pro": 8, "enterprise": 8, "unlimited": 8}
    agent_limit = 8 if current_role == "admin" else tier_agent_limits.get(current_tier.strip().lower(), 3)

    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Plan cap: {agent_limit} agents")
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
# 9) RUN SWARM (BATCHED)
# ============================================================
def run_swarm_in_batches(base_payload: dict, agents: list[str], batch_size: int = 3, pause_sec: int = 20, max_retries: int = 2):
    final_report: dict = {}
    total = len(agents)

    for start in range(0, total, batch_size):
        batch = agents[start:start + batch_size]

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
                    status.update(label="✅ Swarm Complete", state="complete", expanded=False)
                    st.rerun()
                except Exception as e:
                    st.session_state.report = {}
                    st.session_state.gen = False
                    log_event(current_user, "swarm.error", "swarm", "", str(e), team_id)
                    status.update(label="❌ Swarm failed", state="error", expanded=True)
                    st.error(f"Swarm Error: {e}")


# ============================================================
# 10) DASHBOARD: Team Intel with seat limits + org isolation
# ============================================================
def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Organization-scoped SaaS dashboard. Data is restricted to your Organization (Team ID).")

    # counts (org-scoped)
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        users_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM users WHERE team_id=? AND is_active=1", conn, params=(team_id,))["c"].iloc[0]
        camp_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM campaigns WHERE team_id=?", conn, params=(team_id,))["c"].iloc[0]
        asset_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM assets WHERE team_id=?", conn, params=(team_id,))["c"].iloc[0]
        wf_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM workflows WHERE team_id=? AND is_enabled=1", conn, params=(team_id,))["c"].iloc[0]
        lead_cnt = pd.read_sql_query("SELECT COUNT(*) AS c FROM leads WHERE team_id=?", conn, params=(team_id,))["c"].iloc[0]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Active Users", int(users_cnt))
    k2.metric("Campaigns", int(camp_cnt))
    k3.metric("Assets", int(asset_cnt))
    k4.metric("Enabled Workflows", int(wf_cnt))
    k5.metric("Leads", int(lead_cnt))

    org_plan = str(current_tier)
    seat_limit = get_seat_limit(org_plan)

    st.write("---")

    t_users, t_campaigns, t_assets, t_workflows, t_integrations, t_analytics, t_security = st.tabs([
        "👥 User & Access (RBAC)",
        "📣 Campaigns",
        "🗂️ Assets",
        "🤖 Workflows",
        "🔌 Integrations",
        "📊 Analytics",
        "🔐 Security & Logs",
    ])

    # Users & Access (seat limit enforcement)
    with t_users:
        st.subheader("Core User & Access Management (RBAC)")
        st.caption("Only your Organization users are visible here. Seat limits are enforced by plan.")

        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            users_df = pd.read_sql_query(
                "SELECT username, name, email, role, is_active, plan, verified, mfa_enabled, sso_provider, last_login "
                "FROM users WHERE team_id=? ORDER BY username",
                conn,
                params=(team_id,)
            )

        st.dataframe(users_df, use_container_width=True)

        active_seats = int((users_df["is_active"] == 1).sum())
        remaining = max(seat_limit - active_seats, 0)

        cA, cB, cC = st.columns(3)
        cA.metric("Plan", org_plan)
        cB.metric("Active Seats", active_seats)
        cC.metric("Seats Remaining", remaining)

        if current_role == "admin":
            st.write("---")
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("### ➕ Provision / Onboard User")
                with st.form("ti_provision_user"):
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
                            # Seat enforcement only when activating a NEW active user
                            # Check if user exists
                            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                                existing = pd.read_sql_query(
                                    "SELECT username, is_active FROM users WHERE username=? AND team_id=?",
                                    conn,
                                    params=(u.strip(), team_id)
                                )

                            is_new_user = existing.empty
                            would_be_active = bool(active)

                            if would_be_active:
                                # if new user OR re-activating an inactive user, enforce seats
                                if is_new_user:
                                    if active_seats >= seat_limit:
                                        st.error(f"Seat limit reached for {org_plan}. Upgrade plan to add more users.")
                                        st.stop()
                                else:
                                    prev_active = int(existing["is_active"].iloc[0])
                                    if prev_active == 0 and active_seats >= seat_limit:
                                        st.error(f"Seat limit reached for {org_plan}. Upgrade plan to add more users.")
                                        st.stop()

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

                            log_event(current_user, "user.provision", "user", u.strip(), f"role={r}, active={active}", team_id)
                            st.success("User provisioned/updated.")
                            st.rerun()

            with c2:
                st.markdown("### 📴 Deprovision / Deactivate User")
                target = st.selectbox("Select user", users_df["username"].tolist(), key="ti_deactivate_sel")
                if st.button("Deactivate User"):
                    if target == current_user:
                        st.error("You cannot deactivate yourself.")
                    else:
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute("UPDATE users SET is_active=0 WHERE username=? AND team_id=?", (target, team_id))
                            conn.commit()
                        log_event(current_user, "user.deactivate", "user", target, "deactivated", team_id)
                        st.success("User deactivated.")
                        st.rerun()

            st.write("---")
            st.markdown("### 📥 Bulk Import Users (CSV)")
            st.caption("CSV columns: username,name,email,role,plan,is_active,temp_password")
            up = st.file_uploader("Upload CSV", type=["csv"], key="ti_bulk_users")
            if up is not None:
                try:
                    df = pd.read_csv(up)
                    st.dataframe(df.head(25), use_container_width=True)

                    # count how many would add active seats
                    def _would_add_seat(row) -> bool:
                        uname = str(row.get("username", "")).strip()
                        if not uname:
                            return False
                        is_active_val = str(row.get("is_active", "1")).strip()
                        try:
                            desired_active = bool(int(is_active_val)) if is_active_val != "" else True
                        except Exception:
                            desired_active = True
                        if not desired_active:
                            return False

                        # if user exists and already active -> no
                        return True

                    if st.button("Import Users"):
                        # Determine seat impact precisely: new active users + reactivations
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            existing_df = pd.read_sql_query(
                                "SELECT username, is_active FROM users WHERE team_id=?",
                                conn, params=(team_id,)
                            )

                        existing_map = {r["username"]: int(r["is_active"]) for _, r in existing_df.iterrows()}

                        seat_add = 0
                        to_import = []

                        for _, rr in df.iterrows():
                            uname = str(rr.get("username", "")).strip()
                            tpw = str(rr.get("temp_password", "")).strip()
                            if not uname or not tpw:
                                continue

                            is_active_val = str(rr.get("is_active", "1")).strip()
                            try:
                                desired_active = bool(int(is_active_val)) if is_active_val != "" else True
                            except Exception:
                                desired_active = True

                            # seat increase if desired_active and (new user OR currently inactive)
                            if desired_active and (uname not in existing_map or existing_map.get(uname, 0) == 0):
                                seat_add += 1

                            to_import.append(rr)

                        if active_seats + seat_add > seat_limit:
                            st.error(
                                f"Bulk import exceeds seat limit for {org_plan}. "
                                f"Active seats: {active_seats}, seats needed: {seat_add}, limit: {seat_limit}."
                            )
                            st.stop()

                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            for rr in to_import:
                                uname = str(rr.get("username", "")).strip()
                                tpw = str(rr.get("temp_password", "")).strip()

                                role_ = str(rr.get("role", "viewer")).strip().lower()
                                if role_ not in {"admin", "editor", "viewer"}:
                                    role_ = "viewer"
                                plan_ = str(rr.get("plan", "Lite")).strip() or "Lite"

                                is_active_val = str(rr.get("is_active", "1")).strip()
                                try:
                                    is_active_ = int(is_active_val) if is_active_val != "" else 1
                                except Exception:
                                    is_active_ = 1

                                hashed = stauth.Hasher.hash(tpw)

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
                                    str(rr.get("name", "")).strip(),
                                    str(rr.get("email", "")).strip(),
                                    hashed,
                                    role_,
                                    1 if is_active_ else 0,
                                    plan_,
                                    team_id
                                ))
                            conn.commit()

                        log_event(current_user, "user.bulk_import", "user", "", f"rows={len(to_import)}", team_id)
                        st.success("Bulk import completed.")
                        st.rerun()

                except Exception as e:
                    st.error(f"CSV import error: {e}")

        else:
            st.info("Provisioning is Admin-only.")

        st.info("SSO/MFA are placeholders in this Streamlit build. Production SSO/MFA requires an external identity provider.")


    # Campaigns
    with t_campaigns:
        st.subheader("Campaign Management")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            camp_df = pd.read_sql_query(
                "SELECT id, name, channel, status, start_date, end_date, budget, owner, created_at, updated_at "
                "FROM campaigns WHERE team_id=? ORDER BY id DESC",
                conn,
                params=(team_id,)
            )
        st.dataframe(camp_df, use_container_width=True)

        if can("campaign.create"):
            with st.expander("➕ Create Campaign", expanded=False):
                with st.form("ti_create_campaign"):
                    name = st.text_input("Campaign Name")
                    channel = st.selectbox("Channel", ["email", "social", "ads", "seo", "geo", "other"])
                    status_ = st.selectbox("Status", ["draft", "scheduled", "live", "paused", "complete"])
                    start_date = st.text_input("Start (YYYY-MM-DD)", value="")
                    end_date = st.text_input("End (YYYY-MM-DD)", value="")
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
                                """, (name.strip(), channel, status_, start_date.strip(), end_date.strip(), float(budget), current_user, team_id, now, now, notes.strip()))
                                conn.commit()
                            log_event(current_user, "campaign.create", "campaign", name.strip(), f"channel={channel}", team_id)
                            st.success("Campaign created.")
                            st.rerun()
        else:
            st.info("Create campaigns requires Editor/Admin role.")

    # Assets
    with t_assets:
        st.subheader("Content & Asset Library")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            assets_df = pd.read_sql_query(
                "SELECT id, name, asset_type, mime_type, size_bytes, owner, created_at, tags "
                "FROM assets WHERE team_id=? ORDER BY id DESC",
                conn,
                params=(team_id,)
            )
        st.dataframe(assets_df, use_container_width=True)

        if can("asset.upload"):
            with st.expander("📤 Upload Asset", expanded=False):
                up = st.file_uploader("Upload (<=2MB)", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"])
                asset_type = st.selectbox("Asset Type", ["image", "template", "copy", "other"])
                tags = st.text_input("Tags (comma-separated)")
                save = st.button("Save Asset")
                if save:
                    if up is None:
                        st.error("Upload a file first.")
                    else:
                        data = up.getvalue()
                        if len(data) > 2_000_000:
                            st.error("File too large for DB storage. Keep assets <= 2MB or store externally.")
                        else:
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
            st.info("Upload assets requires Editor/Admin role.")

    # Workflows
    with t_workflows:
        st.subheader("Automation & Workflows")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            wf_df = pd.read_sql_query(
                "SELECT id, name, trigger, is_enabled, owner, created_at "
                "FROM workflows WHERE team_id=? ORDER BY id DESC",
                conn,
                params=(team_id,)
            )
        st.dataframe(wf_df, use_container_width=True)

        if can("workflow.manage"):
            with st.expander("➕ Create Workflow", expanded=False):
                with st.form("ti_create_workflow"):
                    name = st.text_input("Workflow Name")
                    trigger = st.selectbox("Trigger", ["lead_created", "campaign_scheduled", "approval_required", "manual"])
                    steps_json = st.text_area("Steps JSON", value='["step1","step2"]')
                    enabled = st.checkbox("Enabled", value=True)
                    submit = st.form_submit_button("Create")
                    if submit:
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute("""
                                INSERT INTO workflows (name, trigger, steps_json, is_enabled, owner, team_id, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (name.strip(), trigger, steps_json.strip(), 1 if enabled else 0, current_user, team_id, datetime.utcnow().isoformat()))
                            conn.commit()
                        log_event(current_user, "workflow.create", "workflow", name.strip(), trigger, team_id)
                        st.success("Workflow created.")
                        st.rerun()
        else:
            st.info("Manage workflows requires Editor/Admin role.")

    # Integrations
    with t_integrations:
        st.subheader("Integrations")
        st.caption("CRM/Analytics/Social connections stored as placeholders. Use secrets for real keys.")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            int_df = pd.read_sql_query(
                "SELECT id, name, status, details, updated_at "
                "FROM integrations WHERE team_id=? ORDER BY id DESC",
                conn,
                params=(team_id,)
            )
        st.dataframe(int_df, use_container_width=True)

        if can("integration.manage"):
            with st.expander("➕ Add / Update Integration", expanded=False):
                with st.form("ti_integration_form"):
                    name = st.selectbox("Integration", ["Salesforce", "HubSpot", "Google Analytics", "Meta", "Mailchimp", "Other"])
                    status_ = st.selectbox("Status", ["disconnected", "connected", "error"])
                    details = st.text_area("Details (non-secret)")
                    submit = st.form_submit_button("Save")
                    if submit:
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute("""
                                INSERT INTO integrations (name, status, details, team_id, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                            """, (name, status_, details.strip(), team_id, datetime.utcnow().isoformat()))
                            conn.commit()
                        log_event(current_user, "integration.save", "integration", name, status_, team_id)
                        st.success("Integration saved.")
                        st.rerun()
        else:
            st.info("Manage integrations requires Editor/Admin role.")

    # Analytics
    with t_analytics:
        st.subheader("Analytics & Reporting")
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            camps = pd.read_sql_query("SELECT status, channel, budget FROM campaigns WHERE team_id=?", conn, params=(team_id,))
            logs = pd.read_sql_query("SELECT action_type FROM activity_logs WHERE team_id=?", conn, params=(team_id,))
            leads = pd.read_sql_query("SELECT status FROM leads WHERE team_id=?", conn, params=(team_id,))

        r1, r2, r3 = st.columns(3)
        r1.metric("Leads", int(len(leads)))
        r2.metric("Campaigns", int(len(camps)))
        r3.metric("Active Users", int(users_cnt))

        st.write("---")
        if not leads.empty:
            st.markdown("#### Lead Status")
            st.bar_chart(leads["status"].value_counts())

        if not camps.empty:
            st.markdown("#### Campaign Status")
            st.bar_chart(camps["status"].value_counts())
            st.markdown("#### Channel Mix")
            st.bar_chart(camps["channel"].value_counts())

        if not logs.empty:
            st.markdown("#### Usage Analytics")
            st.bar_chart(logs["action_type"].value_counts().head(12))

    # Security & Logs (org-scoped; hide auth.login for non-admin)
    with t_security:
        st.subheader("Security & Compliance")
        base_query = """
            SELECT timestamp, actor, action_type, object_type, object_id, details
            FROM activity_logs
            WHERE team_id=?
        """
        params = [team_id]
        if current_role != "admin":
            base_query += " AND action_type NOT IN ('auth.login')"
        base_query += " ORDER BY id DESC LIMIT 300"

        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            logs_df = pd.read_sql_query(base_query, conn, params=tuple(params))

        st.dataframe(logs_df, use_container_width=True)
        st.info("SSO/MFA are placeholders in this Streamlit build. For real SaaS, enforce SSO+MFA at the IdP.")


# ============================================================
# 11) OTHER TABS (GUIDE / AGENTS / VISION / VEO / ADMIN)
# ============================================================
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: competitor gaps, pricing, positioning.",
    "ads": "📺 **Ads Architect**: deployable ads for Google/Meta.",
    "creative": "🎨 **Creative Director**: concepts + prompt packs.",
    "strategist": "📝 **Strategist**: 30-day execution roadmap.",
    "social": "📱 **Social**: engagement content calendar.",
    "geo": "📍 **GEO**: local visibility and citations.",
    "audit": "🔍 **Audit**: website conversion friction.",
    "seo": "📝 **SEO**: authority article."
}

DEPLOY_GUIDES = {
    "analyst": "Identify price gaps and positioning opportunities.",
    "ads": "Build ad headlines, descriptions, hooks.",
    "creative": "Create concepts + Midjourney/Canva prompt packs.",
    "strategist": "Synthesize into CEO-ready roadmap.",
    "social": "Build a 30-day plan with hooks and CTAs.",
    "geo": "Local plan: citations, GBP, near-me targeting.",
    "audit": "Audit for friction and fixes.",
    "seo": "Write local SEO authority article."
}

def show_deploy_guide(title: str, key: str):
    st.markdown(
        f"""
        <div style="background-color:#f0f2f6; padding:14px; border-radius:10px;
                    border-left: 5px solid #2563EB; margin-bottom: 14px;">
            <b style="color:#0f172a;">🚀 {title.upper()} GUIDE:</b><br>
            <span style="color:#334155;">{DEPLOY_GUIDES.get(key, "")}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_social_push_panel():
    st.markdown("### 🚀 Publish / Push")
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
    st.info(f"Command Center Active for: {biz_name or 'Global Mission'}")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)

def render_agent_seat(title: str, key: str):
    st.subheader(f"🚀 {title} Seat")
    show_deploy_guide(title, key)

    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report and report.get(key):
        edited = st.text_area("Refine Intel", value=str(report.get(key)), height=420, key=f"ed_{key}")

        if key in {"ads", "creative", "social"}:
            st.write("---")
            render_social_push_panel()

        st.write("---")
        c1, c2 = st.columns(2)
        with c1:
            if can("export.data") or current_role == "admin":
                st.download_button("📄 Download Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
                log_event(current_user, "export.word", "agent_output", key, "", team_id)
            else:
                st.info("Export requires Editor/Admin.")
        with c2:
            if can("export.data") or current_role == "admin":
                st.download_button("📕 Download PDF", export_pdf(edited, title), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)
                log_event(current_user, "export.pdf", "agent_output", key, "", team_id)
            else:
                st.info("Export requires Editor/Admin.")
    else:
        st.info("Agent not selected for this run. Launch from sidebar.")

def render_vision():
    st.header("👁️ Visual Intelligence")
    st.write("Visual audits and image analysis results appear here.")

def render_veo():
    st.header("🎬 Veo Video Studio")
    st.write("AI video generation assets appear here.")

def render_admin():
    st.header("⚙ Admin Console")
    st.caption("Platform governance. (Organization-scoped in this build.)")
    if current_role != "admin":
        st.info("Admin-only view.")
        return
    st.info("Admin features are available inside Team Intel. This tab is reserved for platform-level controls.")
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        df = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM activity_logs WHERE team_id=? ORDER BY id DESC LIMIT 200",
            conn, params=(team_id,)
        )
    st.dataframe(df, use_container_width=True)


# ============================================================
# 12) TABS
# ============================================================
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
