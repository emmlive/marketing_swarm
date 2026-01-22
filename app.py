import os
import re
import time
import sqlite3
import unicodedata
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

# Dedicated team_id for SaaS owner/root (never shared with customers)
PLATFORM_TEAM_ID = "PLATFORM"
PLATFORM_USERNAME = "platform_admin"  # seeded root user


# ============================================================
# 1) CSS (LOAD ONCE) + LOGIN CHROME HIDE
# ============================================================
def load_css_once():
    if st.session_state.get("_css_loaded"):
        return
    st.session_state["_css_loaded"] = True

    st.markdown(
        """
<style>
/* Reduce top chrome + improve “SaaS feel” */
header[data-testid="stHeader"] { display: none; }
footer { display: none; }
#MainMenu { visibility: hidden; }

/* Default page padding tighter */
.block-container { padding-top: 1.2rem; }

/* -------- LOGIN PAGE -------- */
.ms-login-shell {
  min-height: 92vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px 14px;
  background:
    radial-gradient(1200px 600px at 20% 15%, rgba(37,99,235,0.25), transparent 55%),
    radial-gradient(1100px 520px at 85% 20%, rgba(168,85,247,0.22), transparent 55%),
    radial-gradient(1100px 520px at 50% 85%, rgba(34,197,94,0.12), transparent 60%),
    linear-gradient(180deg, #060a18, #070b18);
}
.ms-login-card {
  width: min(1120px, 100%);
  border-radius: 22px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(10px);
  box-shadow: 0 30px 90px rgba(0,0,0,0.45);
  overflow: hidden;
}
.ms-login-top {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 18px;
  padding: 22px;
}
@media (max-width: 980px) {
  .ms-login-top { grid-template-columns: 1fr; }
}
.ms-brand-row { display:flex; gap:14px; align-items:center; }
.ms-brand-title { color:#fff; font-weight: 900; font-size: 40px; margin: 6px 0 6px; letter-spacing:-0.02em;}
.ms-brand-sub { color: rgba(255,255,255,0.82); font-size: 14px; margin: 0; }
.ms-chip {
  display:inline-flex; align-items:center; gap:8px;
  border: 1px solid rgba(255,255,255,0.16);
  padding: 6px 12px;
  border-radius: 999px;
  color: rgba(255,255,255,0.90);
  font-size: 12px;
}
.ms-kpis { display:grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-top: 14px; }
@media (max-width: 980px) { .ms-kpis { grid-template-columns: 1fr; } }
.ms-kpi {
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255,255,255,0.05);
}
.ms-kpi b { color:#fff; }
.ms-kpi span { color: rgba(255,255,255,0.75); font-size: 12px; }
.ms-login-body { padding: 0 22px 22px 22px; }
.ms-divider { border-top: 1px solid rgba(255,255,255,0.14); margin: 0 22px; }

/* Improve tab contrast on login */
.ms-login-card .stTabs [data-baseweb="tab"] { color: rgba(255,255,255,0.90) !important; }
.ms-login-card .stTabs [aria-selected="true"] { color: #ffffff !important; }

/* -------- APP LAYOUT -------- */
.ms-caption { opacity: 0.8; }
</style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# 2) DATABASE + SEEDS
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

    # --- USERS ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',          -- superuser | admin | editor | viewer
            is_active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'HQ_001',
            sso_provider TEXT DEFAULT '',
            mfa_enabled INTEGER DEFAULT 0,
            last_login TEXT DEFAULT ''
        )
        """
    )

    # --- ACTIVITY LOGS (org-scoped) ---
    cur.execute(
        """
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
        """
    )

    # --- LEADS / PIPELINE ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            city TEXT,
            service TEXT,
            status TEXT DEFAULT 'Discovery',
            team_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # --- CAMPAIGNS ---
    cur.execute(
        """
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
        """
    )

    # --- ASSETS ---
    cur.execute(
        """
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
        """
    )

    # --- WORKFLOWS ---
    cur.execute(
        """
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
        """
    )

    # --- INTEGRATIONS ---
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT,
            details TEXT,
            team_id TEXT,
            updated_at TEXT
        )
        """
    )

    # --- BILLING (Stripe placeholders) ---
    cur.execute(
        """
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
        """
    )

    # Migrations / safety
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

    # Seed root superuser (platform team)
    platform_pw = stauth.Hasher.hash("admin123")
    cur.execute(
        """
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, is_active, plan, credits, verified, team_id, mfa_enabled)
        VALUES
        (?, 'admin@tech.ai', 'Platform Admin', ?, 'superuser', 1, 'Unlimited', 9999, 1, ?, 0)
        """,
        (PLATFORM_USERNAME, platform_pw, PLATFORM_TEAM_ID),
    )

    # Optional demo org admin (HQ_001)
    org_admin_pw = stauth.Hasher.hash("admin123")
    cur.execute(
        """
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, is_active, plan, credits, verified, team_id, mfa_enabled)
        VALUES
        ('admin', 'orgadmin@tech.ai', 'Org Admin', ?, 'admin', 1, 'Pro', 9999, 1, 'HQ_001', 0)
        """,
        (org_admin_pw,),
    )

    conn.commit()
    conn.close()


def log_event(actor: str, action_type: str, object_type: str = "", object_id: str = "", details: str = "", team_id: str = ""):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute(
            """
            INSERT INTO activity_logs (timestamp, actor, action_type, object_type, object_id, details, team_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (datetime.utcnow().isoformat(), actor, action_type, object_type, str(object_id), details, team_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# init once to avoid blink
if not st.session_state.get("_db_inited"):
    init_db()
    st.session_state["_db_inited"] = True


# ============================================================
# 3) SEAT LIMITS (PLAN ENFORCEMENT)
# ============================================================
SEAT_LIMITS = {
    "lite": 1,
    "pro": 5,
    "enterprise": 25,
    "unlimited": 10_000_000,
}

AGENT_LIMITS = {
    "lite": 3,
    "pro": 8,
    "enterprise": 8,
    "unlimited": 8,
}

def get_seat_limit(plan: str) -> int:
    return SEAT_LIMITS.get(str(plan).strip().lower(), 1)

def get_agent_limit(plan: str) -> int:
    return AGENT_LIMITS.get(str(plan).strip().lower(), 3)


# ============================================================
# 4) EXPORTS (EXEC READY + LITE LOGO)
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
        pdf.cell(0, 10, f"Executive Intelligence Brief: {nuclear_ascii(title)}", ln=True, align="C")

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
# 5) AUTH (Streamlit Authenticator)
# ============================================================
def get_db_creds():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        df = pd.read_sql_query(
            "SELECT username, email, name, password FROM users WHERE is_active=1",
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

    st.markdown('<div class="ms-login-shell"><div class="ms-login-card">', unsafe_allow_html=True)
    st.markdown('<div class="ms-login-top">', unsafe_allow_html=True)

    # Left: brand
    st.markdown('<div>', unsafe_allow_html=True)
    st.markdown('<div class="ms-chip">🧠 AI Marketing OS • Secure • Multi-Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="ms-brand-row">', unsafe_allow_html=True)
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=90)
    st.markdown('<div>', unsafe_allow_html=True)
    st.markdown('<div class="ms-brand-title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<p class="ms-brand-sub">Modern SaaS for campaign ops, analytics, governance & executive reporting — organization-scoped.</p>', unsafe_allow_html=True)
    st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown("""
      <div class="ms-kpis">
        <div class="ms-kpi"><b>RBAC</b><br><span>Admin • Editor • Viewer</span></div>
        <div class="ms-kpi"><b>Org Isolation</b><br><span>Team-scoped data access</span></div>
        <div class="ms-kpi"><b>Exports</b><br><span>Executive Word/PDF</span></div>
      </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # end left

    # Right: login tabs
    st.markdown('<div>', unsafe_allow_html=True)
    auth_tabs = st.tabs(["🔑 Login", "✨ Plans", "💳 Billing (Stripe)", "❓ Forgot Password"])

    with auth_tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            st.rerun()

    with auth_tabs[1]:
        st.write("**Lite**: 1 seat • 3 agents")
        st.write("**Pro**: 5 seats • 8 agents")
        st.write("**Enterprise**: 25 seats • 8 agents")
        st.caption("Plan selection here is informational; Stripe checkout controls billing in this build.")

    with auth_tabs[2]:
        st.caption("Add these to Streamlit secrets to enable Checkout Links:")
        st.code(
            "STRIPE_CHECKOUT_LITE_URL\nSTRIPE_CHECKOUT_PRO_URL\nSTRIPE_CHECKOUT_ENTERPRISE_URL",
            language="text",
        )
        lite_url = st.secrets.get("STRIPE_CHECKOUT_LITE_URL", "")
        pro_url = st.secrets.get("STRIPE_CHECKOUT_PRO_URL", "")
        ent_url = st.secrets.get("STRIPE_CHECKOUT_ENTERPRISE_URL", "")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.link_button("Pay for Lite", lite_url) if lite_url else st.info("Missing LITE URL")
        with c2:
            st.link_button("Pay for Pro", pro_url) if pro_url else st.info("Missing PRO URL")
        with c3:
            st.link_button("Pay for Enterprise", ent_url) if ent_url else st.info("Missing ENTERPRISE URL")

        st.info("Server-side verification (webhooks) requires an API endpoint (not included in Streamlit-only deployment).")

    with auth_tabs[3]:
        authenticator.forgot_password(location="main")

    st.markdown('</div>', unsafe_allow_html=True)  # end right

    st.markdown('</div><div class="ms-divider"></div><div class="ms-login-body">', unsafe_allow_html=True)
    st.caption("© Your SaaS • Secure login • Organization-scoped access")
    st.markdown('</div></div></div>', unsafe_allow_html=True)


if not st.session_state.get("authentication_status"):
    render_login_screen()
    st.stop()


# ============================================================
# 6) USER CONTEXT + ORG ISOLATION
# ============================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
user_row = pd.read_sql_query(
    "SELECT * FROM users WHERE username=? AND is_active=1",
    conn,
    params=(st.session_state["username"],)
).iloc[0]
conn.close()

current_user = user_row.get("username", "")
current_role = str(user_row.get("role", "viewer")).strip().lower()
current_tier = str(user_row.get("plan", "Lite"))
team_id = str(user_row.get("team_id", "HQ_001"))
st.session_state["current_tier"] = current_tier

is_platform = (team_id == PLATFORM_TEAM_ID) and (current_role == "superuser")

# log login event scoped to their team
try:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("UPDATE users SET last_login=? WHERE username=?", (datetime.utcnow().isoformat(), current_user))
    conn.commit()
    conn.close()
except Exception:
    pass
log_event(current_user, "auth.login", "user", current_user, "login_success", team_id)


# ============================================================
# 7) RBAC PERMISSIONS
# ============================================================
PERMS = {
    "superuser": {"*"},
    "admin": {
        "user.view", "user.provision", "user.deactivate", "user.bulk_import",
        "campaign.view", "campaign.create", "campaign.edit",
        "asset.view", "asset.upload",
        "workflow.view", "workflow.manage",
        "integration.view", "integration.manage",
        "analytics.view",
        "export.data",
        "logs.view",
    },
    "editor": {
        "campaign.view", "campaign.create", "campaign.edit",
        "asset.view", "asset.upload",
        "workflow.view",
        "integration.view",
        "analytics.view",
        "export.data",
    },
    "viewer": {
        "campaign.view",
        "asset.view",
        "workflow.view",
        "integration.view",
        "analytics.view",
    },
}

def can(perm: str) -> bool:
    p = PERMS.get(current_role, set())
    return ("*" in p) or (perm in p)


# ============================================================
# 8) SIDEBAR
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
    if is_platform:
        st.warning("Platform Console enabled (root account).")

    st.metric(f"{current_tier} Plan", f"{int(user_row.get('credits', 0))} Credits")
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp")

    custom_logo = None
    if current_tier.strip().lower() == "lite" and not is_platform:
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

    agent_info = st.text_area("✍️ Strategic Directives", placeholder="Injected into all agent prompts...")

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

    agent_limit = 8 if is_platform else get_agent_limit(current_tier)
    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Plan cap: {agent_limit} agents")
        toggles = {k: st.toggle(t, value=st.session_state.get(f"tg_{k}", False), key=f"tg_{k}") for t, k in agent_map}
        if not is_platform and sum(1 for v in toggles.values() if v) > agent_limit:
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
                    time.sleep(pause_sec * attempt)
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
                    report = run_swarm_in_batches(base_payload, active_agents, batch_size=3, pause_sec=20, max_retries=2)
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
# 10) GUIDE / SEATS / TEAM INTEL / PLATFORM CONSOLE
# ============================================================
AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: competitor gaps, pricing, positioning.",
    "ads": "📺 **Ads Architect**: deployable ads for Google/Meta.",
    "creative": "🎨 **Creative Director**: concepts + prompt packs.",
    "strategist": "🧭 **Strategist**: 30-day execution roadmap.",
    "social": "📱 **Social**: engagement content calendar.",
    "geo": "📍 **GEO**: local visibility and citations.",
    "audit": "🔍 **Audit**: website conversion friction.",
    "seo": "📝 **SEO**: authority article.",
}

DEPLOY_GUIDES = {
    "analyst": "Identify pricing gaps and positioning opportunities.",
    "ads": "Build ad headlines, descriptions, hooks.",
    "creative": "Create concepts + Midjourney/Canva prompt packs.",
    "strategist": "Synthesize into CEO-ready roadmap.",
    "social": "Build a 30-day plan with hooks and CTAs.",
    "geo": "Local plan: citations, GBP, near-me targeting.",
    "audit": "Audit for friction and fixes.",
    "seo": "Write local SEO authority article.",
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
        unsafe_allow_html=True,
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
    st.header("📘 Agent Intelligence Manual")
    st.info(f"Command Center Active for: {biz_name or 'Global Mission'}")

    st.subheader("Agent Specializations")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)

    st.markdown("---")
    st.subheader("🛡️ Swarm Execution Protocol")
    st.markdown(
        """
1) **Configure** your Brand, Location, and Directives in the sidebar.  
2) **Select agents** based on your plan limits (Lite/Pro/Enterprise).  
3) Click **Launch Omni-Swarm**.  
4) Review outputs in each **Agent Seat** and refine as needed.  
5) Use **Exports** (Word/PDF) for executive delivery.  
6) Use **Team Intel** for lightweight org operations (campaigns/assets/users within seat limits).  
7) Root owner uses **Platform Console** for SaaS-wide management (only platform_admin).
        """
    )

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
            if can("export.data"):
                st.download_button("📄 Download Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
            else:
                st.info("Export requires Editor/Admin.")
        with c2:
            if can("export.data"):
                st.download_button("📕 Download PDF", export_pdf(edited, title), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)
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


# ------------------------------------------------------------
# TEAM INTEL (CUSTOMER MINIMAL)
# ------------------------------------------------------------
def render_team_intel_customer():
    st.header("🤝 Team Intel")
    st.caption("Customer dashboard — organization-scoped and plan-limited.")

    # org scoped counts
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        users_df = pd.read_sql_query(
            "SELECT username, name, email, role, is_active, plan, verified, last_login FROM users WHERE team_id=? ORDER BY username",
            conn, params=(team_id,)
        )
        camp_df = pd.read_sql_query(
            "SELECT id, name, channel, status, start_date, end_date, budget, owner, created_at FROM campaigns WHERE team_id=? ORDER BY id DESC",
            conn, params=(team_id,)
        )
        assets_df = pd.read_sql_query(
            "SELECT id, name, asset_type, size_bytes, owner, created_at, tags FROM assets WHERE team_id=? ORDER BY id DESC",
            conn, params=(team_id,)
        )
        leads_df = pd.read_sql_query(
            "SELECT id, city, service, status, timestamp FROM leads WHERE team_id=? ORDER BY id DESC",
            conn, params=(team_id,)
        )
        logs_df = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM activity_logs WHERE team_id=? ORDER BY id DESC LIMIT 150",
            conn, params=(team_id,)
        )

    seat_limit = get_seat_limit(current_tier)
    active_seats = int((users_df["is_active"] == 1).sum())
    remaining = max(seat_limit - active_seats, 0)

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Active Seats", active_seats)
    k2.metric("Seat Limit", seat_limit)
    k3.metric("Seats Remaining", remaining)
    k4.metric("Campaigns", len(camp_df))
    k5.metric("Assets", len(assets_df))

    st.write("---")
    tabs = st.tabs(["👥 Users", "📣 Campaigns", "🗂️ Assets", "📌 Pipeline", "📊 Analytics", "🔐 Security"])

    # USERS (org admin only provisioning) + seat enforcement
    with tabs[0]:
        st.subheader("Users & Access (Org-scoped)")
        st.dataframe(users_df, use_container_width=True)

        if current_role == "admin":
            st.write("---")
            st.markdown("### ➕ Add user (seat-limited)")
            with st.form("cust_add_user"):
                u = st.text_input("Username")
                n = st.text_input("Full Name")
                e = st.text_input("Email")
                r = st.selectbox("Role", ["viewer", "editor", "admin"])
                active = st.checkbox("Active", value=True)
                pw = st.text_input("Temp Password", type="password")
                submit = st.form_submit_button("Create / Update")

                if submit:
                    if not u.strip() or not pw.strip():
                        st.error("Username and Temp Password required.")
                    else:
                        # seat check (new active or reactivation)
                        existing = users_df[users_df["username"] == u.strip()]
                        is_new = existing.empty
                        prev_active = int(existing["is_active"].iloc[0]) if not is_new else 0

                        if active and ((is_new and active_seats >= seat_limit) or (prev_active == 0 and active_seats >= seat_limit)):
                            st.error(f"Seat limit reached for {current_tier}. Upgrade to add more users.")
                            st.stop()

                        hashed = stauth.Hasher.hash(pw.strip())
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute(
                                """
                                INSERT INTO users (username, name, email, password, role, is_active, plan, verified, team_id, last_login)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, '')
                                ON CONFLICT(username) DO UPDATE SET
                                    name=excluded.name,
                                    email=excluded.email,
                                    password=excluded.password,
                                    role=excluded.role,
                                    is_active=excluded.is_active,
                                    plan=excluded.plan,
                                    team_id=excluded.team_id
                                """,
                                (u.strip(), n.strip(), e.strip(), hashed, r, 1 if active else 0, current_tier, team_id),
                            )
                            conn.commit()
                        log_event(current_user, "user.provision", "user", u.strip(), f"role={r}, active={active}", team_id)
                        st.success("User saved.")
                        st.rerun()

            st.write("---")
            st.markdown("### 📥 Bulk import users (CSV) — seat-limited")
            st.caption("CSV columns: username,name,email,role,is_active,temp_password")
            up = st.file_uploader("Upload CSV", type=["csv"], key="cust_bulk_users")
            if up is not None:
                try:
                    df = pd.read_csv(up)
                    st.dataframe(df.head(25), use_container_width=True)

                    if st.button("Import Users"):
                        # determine seat additions
                        existing_map = {r["username"]: int(r["is_active"]) for _, r in users_df.iterrows()}
                        seat_add = 0
                        rows = []

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

                            if desired_active and (uname not in existing_map or existing_map.get(uname, 0) == 0):
                                seat_add += 1

                            rows.append(rr)

                        if active_seats + seat_add > seat_limit:
                            st.error(
                                f"Bulk import exceeds seat limit. Active: {active_seats}, needed: {seat_add}, limit: {seat_limit}."
                            )
                            st.stop()

                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            for rr in rows:
                                uname = str(rr.get("username", "")).strip()
                                tpw = str(rr.get("temp_password", "")).strip()
                                if not uname or not tpw:
                                    continue

                                role_ = str(rr.get("role", "viewer")).strip().lower()
                                if role_ not in {"admin", "editor", "viewer"}:
                                    role_ = "viewer"

                                is_active_val = str(rr.get("is_active", "1")).strip()
                                try:
                                    is_active_ = int(is_active_val) if is_active_val != "" else 1
                                except Exception:
                                    is_active_ = 1

                                hashed = stauth.Hasher.hash(tpw)
                                conn.execute(
                                    """
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
                                    """,
                                    (
                                        uname,
                                        str(rr.get("name", "")).strip(),
                                        str(rr.get("email", "")).strip(),
                                        hashed,
                                        role_,
                                        1 if is_active_ else 0,
                                        current_tier,
                                        team_id,
                                    ),
                                )
                            conn.commit()

                        log_event(current_user, "user.bulk_import", "user", "", f"rows={len(rows)}", team_id)
                        st.success("Bulk import completed.")
                        st.rerun()

                except Exception as e:
                    st.error(f"CSV import error: {e}")
        else:
            st.info("Only your Org Admin can add/remove users.")

    # Campaigns
    with tabs[1]:
        st.subheader("Campaigns")
        st.dataframe(camp_df, use_container_width=True)
        if can("campaign.create"):
            with st.expander("➕ Create Campaign", expanded=False):
                with st.form("cust_create_campaign"):
                    name = st.text_input("Campaign Name")
                    channel = st.selectbox("Channel", ["email", "social", "ads", "seo", "geo", "other"])
                    status_ = st.selectbox("Status", ["draft", "scheduled", "live", "paused", "complete"])
                    start_date = st.text_input("Start (YYYY-MM-DD)", value="")
                    end_date = st.text_input("End (YYYY-MM-DD)", value="")
                    budget = st.number_input("Budget", min_value=0.0, value=0.0, step=50.0)
                    notes = st.text_area("Notes")
                    submit = st.form_submit_button("Create")
                    if submit:
                        now = datetime.utcnow().isoformat()
                        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                            conn.execute(
                                """
                                INSERT INTO campaigns (name, channel, status, start_date, end_date, budget, owner, team_id, created_at, updated_at, notes)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (name.strip(), channel, status_, start_date.strip(), end_date.strip(), float(budget), current_user, team_id, now, now, notes.strip()),
                            )
                            conn.commit()
                        log_event(current_user, "campaign.create", "campaign", name.strip(), f"channel={channel}", team_id)
                        st.success("Campaign created.")
                        st.rerun()
        else:
            st.info("Campaign creation requires Editor/Admin.")

    # Assets
    with tabs[2]:
        st.subheader("Assets")
        st.dataframe(assets_df, use_container_width=True)
        if can("asset.upload"):
            with st.expander("📤 Upload Asset (<=2MB)", expanded=False):
                up = st.file_uploader("Upload", type=["png", "jpg", "jpeg", "pdf", "docx", "txt"])
                asset_type = st.selectbox("Asset Type", ["image", "template", "copy", "other"])
                tags = st.text_input("Tags (comma-separated)")
                if st.button("Save Asset"):
                    if up is None:
                        st.error("Upload a file first.")
                    else:
                        data = up.getvalue()
                        if len(data) > 2_000_000:
                            st.error("File too large for DB storage. Keep <= 2MB.")
                        else:
                            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                                conn.execute(
                                    """
                                    INSERT INTO assets (name, asset_type, mime_type, size_bytes, content, owner, team_id, created_at, tags)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (up.name, asset_type, up.type or "", len(data), data, current_user, team_id, datetime.utcnow().isoformat(), tags.strip()),
                                )
                                conn.commit()
                            log_event(current_user, "asset.upload", "asset", up.name, asset_type, team_id)
                            st.success("Asset saved.")
                            st.rerun()
        else:
            st.info("Asset upload requires Editor/Admin.")

    # Pipeline
    with tabs[3]:
        st.subheader("Pipeline")
        st.dataframe(leads_df, use_container_width=True)

    # Analytics (minimal)
    with tabs[4]:
        st.subheader("Analytics (Minimal)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Leads", len(leads_df))
        c2.metric("Campaigns", len(camp_df))
        c3.metric("Assets", len(assets_df))
        if not camp_df.empty:
            st.markdown("#### Campaign Status")
            st.bar_chart(camp_df["status"].value_counts())
        if not logs_df.empty:
            st.markdown("#### Usage (Top Actions)")
            st.bar_chart(logs_df["action_type"].value_counts().head(10))

    # Security (customers: hide auth.login unless org admin)
    with tabs[5]:
        st.subheader("Security & Logs")
        if current_role != "admin":
            logs_view = logs_df[logs_df["action_type"] != "auth.login"]
        else:
            logs_view = logs_df
        st.dataframe(logs_view, use_container_width=True)
        st.info("SSO/MFA: placeholders in Streamlit build. Production requires an IdP + MFA enforcement.")


# ------------------------------------------------------------
# PLATFORM CONSOLE (ROOT SaaS OWNER)
# ------------------------------------------------------------
def render_platform_console():
    st.header("🛡️ Platform Console")
    st.caption("Root/SaaS owner dashboard — cross-organization management.")

    # choose org to manage
    with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
        teams = pd.read_sql_query("SELECT DISTINCT team_id FROM users ORDER BY team_id", conn)["team_id"].tolist()

    teams = [t for t in teams if t]  # clean
    selected_team = st.selectbox("Select Organization (Team ID)", teams, index=teams.index(PLATFORM_TEAM_ID) if PLATFORM_TEAM_ID in teams else 0)

    tab_users, tab_billing, tab_logs = st.tabs(["👥 Users", "💳 Billing", "🧾 Logs"])

    with tab_users:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            df = pd.read_sql_query(
                "SELECT username, name, email, role, is_active, plan, verified, team_id, last_login FROM users WHERE team_id=? ORDER BY username",
                conn, params=(selected_team,)
            )
        st.dataframe(df, use_container_width=True)

        st.write("---")
        st.subheader("Set Plan / Seats for Org")
        plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise", "Unlimited"])
        seats = st.number_input("Seats", min_value=1, value=get_seat_limit(plan), step=1)
        if st.button("Save Org Billing Record"):
            with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
                conn.execute(
                    """
                    INSERT INTO billing (team_id, plan, seats, renewal_date, status, updated_at)
                    VALUES (?, ?, ?, '', 'active', ?)
                    """,
                    (selected_team, plan, int(seats), datetime.utcnow().isoformat()),
                )
                conn.commit()
            st.success("Saved billing record.")
            log_event(current_user, "platform.billing.save", "billing", selected_team, f"{plan}/{seats}", PLATFORM_TEAM_ID)

    with tab_billing:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            b = pd.read_sql_query(
                "SELECT team_id, plan, seats, status, stripe_customer_id, stripe_subscription_id, updated_at FROM billing ORDER BY id DESC",
                conn
            )
        st.dataframe(b, use_container_width=True)
        st.info("Stripe webhooks/verification not included in Streamlit-only deployment. Use an API service for production billing logic.")

    with tab_logs:
        with sqlite3.connect(DB_PATH, check_same_thread=False) as conn:
            l = pd.read_sql_query(
                "SELECT timestamp, actor, action_type, object_type, object_id, details, team_id FROM activity_logs ORDER BY id DESC LIMIT 500",
                conn
            )
        st.dataframe(l, use_container_width=True)


# ============================================================
# 11) TABS
# ============================================================
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]

# Root-only tab:
if is_platform:
    tab_labels.append("🛡️ Platform Console")
# Customer org admins could still have an admin tab later; we keep minimal now.

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
    # Customers see minimal Team Intel; platform uses Platform Console for SaaS backend
    render_team_intel_customer()

if "
