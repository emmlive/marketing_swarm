import os
import re
import csv
import json
import time
import sqlite3
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from docx import Document
from fpdf import FPDF
import fpdf

from main import run_marketing_swarm

# ============================================================
# APP NAME
# ============================================================
APP_NAME = "SwarmDigiz"

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title=APP_NAME, layout="wide")

DB_PATH = "breatheeasy.db"
APP_LOGO_PATH = "Logo1.jpeg"

PLAN_SEATS = {"Lite": 1, "Basic": 1, "Pro": 5, "Enterprise": 20, "Unlimited": 9999}
PLAN_AGENT_LIMITS = {"Lite": 3, "Basic": 3, "Pro": 5, "Enterprise": 8, "Unlimited": 8}

DEPLOY_PROTOCOL = [
    "Configure mission in the sidebar (Brand, Location, Directives, Website URL).",
    "Agents are locked by plan (upgrade to unlock more).",
    "Click LAUNCH OMNI-SWARM to start.",
    "Use Pause/Stop between agents (Step Runner).",
    "Review outputs in each seat, export Word/PDF, save to Vault, manage execution in Team Intel.",
]

# Canonical agent keys
AGENT_UI = [
    ("🕵️ Analyst", "analyst"),
    ("🧭 Marketing Adviser", "marketing_adviser"),
    ("🔎 Market Researcher", "market_researcher"),
    ("🛒 E-Commerce Marketer", "ecommerce_marketer"),
    ("📺 Ads", "ads"),
    ("🎨 Creative", "creative"),
    ("🧩 Guest Posting", "guest_posting"),
    ("👔 Strategist", "strategist"),
    ("📱 Social", "social"),
    ("📍 GEO", "geo"),
    ("🌐 Website Audit", "audit"),
    ("✍ SEO", "seo"),
]

AGENT_SPECS = {
    "analyst": "Competitor gaps, pricing, positioning, quick wins.",
    "marketing_adviser": "Messaging, channel priorities, measurement, next steps.",
    "market_researcher": "Segments, competitors, demand signals, themes.",
    "ecommerce_marketer": "Offers, landing pages, flows, remarketing.",
    "ads": "Google/Meta ad tables and angles.",
    "creative": "Concepts + prompt packs + ad variants.",
    "guest_posting": "Outreach templates + PR/link plan.",
    "strategist": "30-day execution roadmap + KPIs.",
    "social": "30-day social plan with hooks & CTAs.",
    "geo": "Local visibility, citations, GBP plan.",
    "audit": "Conversion friction audit + fixes (needs URL).",
    "seo": "Authority article + clusters.",
}

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

# ============================================================
# SESSION STATE INIT (must run before widgets)
# ============================================================
def ss_init(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

ss_init("theme_mode", "Night")
ss_init("sidebar_compact", False)

ss_init("swarm_running", False)
ss_init("swarm_paused", False)
ss_init("swarm_stop", False)
ss_init("swarm_queue", [])
ss_init("swarm_idx", 0)
ss_init("swarm_payload", {})
ss_init("swarm_autorun", True)
ss_init("swarm_autodelay", 3)  # 1 / 3 / 5
ss_init("swarm_next_ts", 0.0)

ss_init("report", {})
ss_init("gen", False)
ss_init("last_active_swarm", [])

ss_init("website_url", "")
ss_init("biz_name", "")
ss_init("directives", "")

# ============================================================
# THEME + SIDEBAR CSS (includes compact/expanded + animation)
# ============================================================
def inject_theme_css():
    mode = st.session_state.get("theme_mode", "Night")
    compact = bool(st.session_state.get("sidebar_compact", False))

    if mode == "Night":
        bg = "#0b1220"
        sidebar_bg = "#0e1627"
        panel = "rgba(17, 24, 39, 0.94)"
        text = "#e5e7eb"
        muted = "#9ca3af"
        border = "rgba(148, 163, 184, 0.22)"
        input_bg = "rgba(255,255,255,0.06)"
    else:
        bg = "#ffffff"
        sidebar_bg = "#f8fafc"
        panel = "rgba(255,255,255,0.96)"
        text = "#0f172a"
        muted = "#475569"
        border = "rgba(15,23,42,0.14)"
        input_bg = "#ffffff"

    # Sidebar width
    sbw = "250px" if compact else "360px"

    st.markdown(f"""
    <style>
      .stApp {{
        background: {bg};
        color: {text};
      }}

      /* Keep core text readable */
      .stApp, .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
        color: {text};
      }}
      .ms-muted {{ color: {muted} !important; }}

      /* Sidebar width + animation */
      section[data-testid="stSidebar"] {{
        width: {sbw} !important;
        transition: width 240ms ease-in-out;
      }}
      section[data-testid="stSidebar"] > div {{
        background: {sidebar_bg};
        border-right: 1px solid {border};
        padding-top: 0.6rem;
        padding-bottom: 0.6rem;
      }}

      /* Tight spacing in sidebar */
      section[data-testid="stSidebar"] .stTextInput,
      section[data-testid="stSidebar"] .stTextArea,
      section[data-testid="stSidebar"] .stSelectbox,
      section[data-testid="stSidebar"] .stRadio,
      section[data-testid="stSidebar"] .stCheckbox,
      section[data-testid="stSidebar"] .stToggle {{
        margin-bottom: 0.35rem !important;
      }}
      section[data-testid="stSidebar"] label {{
        margin-bottom: 0.15rem !important;
        font-size: 0.85rem !important;
        opacity: 0.96;
      }}
      section[data-testid="stSidebar"] hr {{
        margin: 0.6rem 0 !important;
        border-color: {border};
      }}

      /* Inputs */
      input, textarea {{
        background: {input_bg} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        padding: 6px 10px !important;
      }}
      div[data-baseweb="select"] > div {{
        background: {input_bg} !important;
        color: {text} !important;
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        min-height: 36px !important;
      }}

      /* Card */
      .ms-card {{
        border: 1px solid {border};
        border-radius: 16px;
        background: {panel};
        box-shadow: 0 14px 36px rgba(0,0,0,0.18);
        padding: 14px 16px;
        margin-bottom: 10px;
      }}

      /* Tabs spacing */
      .stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}

      /* Badges */
      .ms-badge {{
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        border:1px solid {border};
        background: rgba(99,102,241,0.14);
        font-size:12px;
        color: {text};
      }}

      /* Hide Streamlit chrome */
      #MainMenu {{ visibility: hidden; }}
      footer {{ visibility: hidden; }}
    </style>
    """, unsafe_allow_html=True)

inject_theme_css()

# ============================================================
# DB
# ============================================================
def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

def _hash_password(pw: str) -> str:
    pw = pw or ""
    try:
        if hasattr(stauth, "Hasher") and hasattr(stauth.Hasher, "hash"):
            return stauth.Hasher.hash(pw)
    except Exception:
        pass
    try:
        return stauth.Hasher([pw]).generate()[0]
    except Exception:
        return pw

@st.cache_resource
def init_db_once() -> None:
    conn = db_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orgs (
            team_id TEXT PRIMARY KEY,
            org_name TEXT,
            plan TEXT DEFAULT 'Lite',
            seats_allowed INTEGER DEFAULT 1,
            allowed_agents_json TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',
            active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'ORG_001',
            created_at TEXT DEFAULT (datetime('now')),
            last_login_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            team_id TEXT,
            actor TEXT,
            actor_role TEXT,
            action_type TEXT,
            object_type TEXT,
            object_id TEXT,
            details TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            title TEXT,
            city TEXT,
            service TEXT,
            stage TEXT DEFAULT 'Discovery',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            created_by TEXT,
            location TEXT,
            biz_name TEXT,
            selected_agents_json TEXT,
            report_json TEXT,
            full_report TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            owner TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            project_id INTEGER,
            title TEXT,
            assignee TEXT,
            status TEXT DEFAULT 'Todo',
            due_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")
    ensure_column(conn, "orgs", "allowed_agents_json", "TEXT DEFAULT ''")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")

    # Seed ROOT
    cur.execute("""
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active', '')
    """)
    root_pw = _hash_password(os.getenv("ROOT_PASSWORD", "root123"))
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username,email,name,password,role,active,plan,credits,verified,team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1,'Unlimited',9999,1,'ROOT')
    """, (root_pw,))

    # Demo org
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id!='ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        allowed = json.dumps(["analyst", "marketing_adviser", "strategist"])
        cur.execute("""
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
            VALUES ('ORG_001','TechNovance Customer','Lite',1,'active',?)
        """, (allowed,))
        admin_pw = _hash_password("admin123")
        cur.execute("""
            INSERT OR REPLACE INTO users
            (username,email,name,password,role,active,plan,credits,verified,team_id)
            VALUES ('admin','admin@customer.ai','Org Admin',?, 'admin',1,'Lite',999,1,'ORG_001')
        """, (admin_pw,))

    conn.commit()
    conn.close()

init_db_once()

def get_org(team_id: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM orgs WHERE team_id=?", conn, params=(team_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {"team_id": team_id, "org_name": team_id, "plan": "Lite", "seats_allowed": 1, "status": "active", "allowed_agents_json": ""}

def get_user(username: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(username,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}

def seats_allowed_for_team(team_id: str) -> int:
    org = get_org(team_id)
    return int(org.get("seats_allowed") or 1)

def active_user_count(team_id: str) -> int:
    conn = db_conn()
    df = pd.read_sql_query("SELECT COUNT(*) AS n FROM users WHERE team_id=? AND active=1 AND role!='root'", conn, params=(team_id,))
    conn.close()
    return int(df.iloc[0]["n"] or 0)

def normalize_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in {"viewer","editor","admin","root"} else "viewer"

def log_audit(team_id: str, actor: str, actor_role: str, action_type: str,
              object_type: str = "", object_id: str = "", details: str = "") -> None:
    try:
        conn = db_conn()
        conn.execute("""
            INSERT INTO audit_logs (timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details)
            VALUES (?,?,?,?,?,?,?,?)
        """, (datetime.utcnow().isoformat(), team_id, actor, actor_role, action_type, object_type, object_id, details[:4000]))
        conn.commit(); conn.close()
    except Exception:
        pass

def plan_agent_limit(plan: str) -> int:
    return int(PLAN_AGENT_LIMITS.get(plan, 3))

def default_allowed_agents_for_plan(plan: str) -> List[str]:
    order = [k for _, k in AGENT_UI]
    return order[:max(1, min(plan_agent_limit(plan), len(order)))]

def get_allowed_agents(team_id: str) -> List[str]:
    org = get_org(team_id)
    raw = (org.get("allowed_agents_json") or "").strip()
    try:
        lst = json.loads(raw) if raw else []
    except Exception:
        lst = []
    lst = [str(x).strip().lower() for x in lst if str(x).strip()]
    valid = {k for _, k in AGENT_UI}
    lst = [x for x in lst if x in valid]
    if lst:
        return lst
    auto = default_allowed_agents_for_plan(org.get("plan", "Lite"))
    conn = db_conn()
    conn.execute("UPDATE orgs SET allowed_agents_json=? WHERE team_id=?", (json.dumps(auto), team_id))
    conn.commit(); conn.close()
    return auto

def set_org_plan_and_auto_agents(team_id: str, plan: str) -> List[str]:
    plan = (plan or "Lite").strip()
    seats = PLAN_SEATS.get(plan, 1)
    agents = default_allowed_agents_for_plan(plan)
    conn = db_conn()
    conn.execute("UPDATE orgs SET plan=?, seats_allowed=?, allowed_agents_json=? WHERE team_id=?",
                 (plan, int(seats), json.dumps(agents), team_id))
    conn.commit(); conn.close()
    return agents

# ============================================================
# EXPORT
# ============================================================
def export_word(content, title):
    doc = Document()
    doc.add_heading(str(title), 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def export_pdf(content: str, title: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_font("Arial","B",14)
    pdf.cell(0, 7, str(title), ln=True)
    pdf.set_font("Arial", size=10)
    txt = str(content).encode("latin-1","ignore").decode("latin-1")
    pdf.multi_cell(0, 6, txt)
    return pdf.output(dest="S").encode("latin-1")

# ============================================================
# AUTH
# ============================================================
def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT username,email,name,password FROM users WHERE active=1", conn)
        return {"usernames": {r["username"]: {"email": r.get("email",""), "name": r.get("name", r["username"]), "password": r["password"]} for _, r in df.iterrows()}}
    finally:
        conn.close()

cookie_name = st.secrets.get("cookie", {}).get("name", "swarmdigiz_cookie")
cookie_key = st.secrets.get("cookie", {}).get("key", "swarmdigiz_cookie_key_change_me")
cookie_days = int(st.secrets.get("cookie", {}).get("expiry_days", 30))

authenticator = stauth.Authenticate(get_db_creds(), cookie_name, cookie_key, cookie_days)

def login_page():
    st.title(APP_NAME)
    st.caption("Root login: root / root123 (or ROOT_PASSWORD env var).")
    tabs = st.tabs(["Login", "Forgot Password"])
    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state["username"])
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u["username"]))
            conn.commit(); conn.close()
            log_audit(u.get("team_id",""), u["username"], u.get("role",""), "auth.login", "user", u["username"], "login_success")
            st.rerun()
    with tabs[1]:
        authenticator.forgot_password(location="main")
    st.stop()

if not st.session_state.get("authentication_status"):
    login_page()

# ============================================================
# CONTEXT
# ============================================================
me = get_user(st.session_state["username"])
my_team = me.get("team_id", "ORG_001")
my_role = normalize_role(me.get("role", "viewer"))
is_root = (my_role == "root") or (my_team == "ROOT")
org = get_org(my_team)
org_plan = str(org.get("plan", "Lite"))

unlocked_agents = [k for _, k in AGENT_UI] if is_root else get_allowed_agents(my_team)

# Admin vs Viewer badges
role_badge = "🛡 Org Admin" if my_role in {"admin","root"} else "👁 Viewer"
role_color = "ms-badge"

# ============================================================
# SIDEBAR UI (compact toggle + badge)
# ============================================================
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.markdown(f"<span class='ms-badge'>{role_badge}</span>", unsafe_allow_html=True)
    st.caption(f"Team: `{my_team}`")

    cA, cB = st.columns([1,1])
    with cA:
        st.checkbox("Compact", value=st.session_state["sidebar_compact"], key="sidebar_compact")
    with cB:
        st.selectbox("Theme", ["Night", "Day"], index=0 if st.session_state["theme_mode"]=="Night" else 1, key="theme_mode")

    inject_theme_css()

    st.metric("Plan", org_plan)
    st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")
    st.divider()

    st.text_input("Brand Name", value=st.session_state["biz_name"], key="biz_name")
    st.text_input("Website URL (for Website Audit)", value=st.session_state["website_url"], key="website_url")
    st.text_area("Strategic Directives", value=st.session_state["directives"], key="directives", height=90)

    st.divider()

    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption("Select unlocked agents. Locked agents are disabled.")
        for label, key in AGENT_UI:
            widget_key = f"tg_{key}"
            if widget_key not in st.session_state:
                st.session_state[widget_key] = False
            disabled = (not is_root) and (key not in unlocked_agents)
            st.toggle(label, key=widget_key, disabled=disabled)
            if disabled:
                st.caption(f"🔒 Locked by plan: {key}")

    st.divider()

    st.checkbox("Auto-run remaining agents", value=st.session_state["swarm_autorun"], key="swarm_autorun")
    st.selectbox("Auto-run delay", [1,3,5], index=[1,3,5].index(int(st.session_state["swarm_autodelay"])), key="swarm_autodelay")

    if st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True):
        selected = [k for _, k in AGENT_UI if st.session_state.get(f"tg_{k}", False)]
        if not st.session_state["biz_name"].strip():
            st.error("Enter Brand Name first.")
        elif not selected:
            st.warning("Select at least one agent.")
        else:
            st.session_state["last_active_swarm"] = selected[:]
            st.session_state["swarm_payload"] = {
                "biz_name": st.session_state["biz_name"].strip(),
                "city": "USA",
                "directives": st.session_state["directives"].strip(),
                "url": st.session_state["website_url"].strip(),
                "package": org_plan,
            }
            st.session_state["swarm_queue"] = selected[:]
            st.session_state["swarm_idx"] = 0
            st.session_state["swarm_running"] = True
            st.session_state["swarm_paused"] = False
            st.session_state["swarm_stop"] = False
            st.session_state["swarm_next_ts"] = time.time()
            st.session_state["report"] = {}
            st.session_state["gen"] = False
            st.toast("Swarm started.", icon="🚀")
            st.rerun()

    authenticator.logout("Sign Out", "sidebar")

# ============================================================
# MAIN TABS (always show Team Intel; show Admin for org admin; show Root Admin for root)
# ============================================================
def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Viewer sees read-only. Admin sees full tools. Same tab layout always.")

    is_admin_like = (my_role in {"admin","root"})
    tabs = st.tabs(["🧩 Projects", "🗂 Kanban Leads", "🧾 Reports Vault", "👥 Users & RBAC", "🔐 Security Logs"])

    def viewer_notice():
        st.info("Viewer access: read-only. Ask Org Admin for create/edit access.")

    with tabs[0]:
        st.subheader("Projects")
        conn = db_conn()
        pdf = pd.read_sql_query("SELECT id,name,owner,status,created_at FROM projects WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(pdf, use_container_width=True, hide_index=True)
        if not is_admin_like:
            viewer_notice()

    with tabs[1]:
        st.subheader("Kanban Leads")
        conn = db_conn()
        ldf = pd.read_sql_query("SELECT id,title,city,service,stage,created_at FROM leads WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(ldf, use_container_width=True, hide_index=True)
        if not is_admin_like:
            viewer_notice()

    with tabs[2]:
        st.subheader("Reports Vault")
        conn = db_conn()
        vdf = pd.read_sql_query("SELECT id,name,biz_name,location,created_by,created_at FROM reports_vault WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(vdf, use_container_width=True, hide_index=True)
        if not is_admin_like:
            viewer_notice()

    with tabs[3]:
        st.subheader("Users & RBAC")
        conn = db_conn()
        udf = pd.read_sql_query("SELECT username,name,email,role,credits,active,last_login_at,created_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(udf, use_container_width=True, hide_index=True)
        if not is_admin_like:
            viewer_notice()

    with tabs[4]:
        st.subheader("Security Logs")
        conn = db_conn()
        logs = pd.read_sql_query("SELECT timestamp,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 250", conn, params=(my_team,))
        conn.close()
        st.dataframe(logs, use_container_width=True, hide_index=True)

def render_root_admin():
    st.header("🛡 SaaS Root Admin")
    st.caption("Manage org plans + auto agents.")
    team_id = st.text_input("Team ID")
    plan = st.selectbox("Plan", ["Lite","Pro","Enterprise","Unlimited"], index=0)
    if st.button("Apply Plan + Auto Agents", use_container_width=True):
        agents = set_org_plan_and_auto_agents(team_id.strip(), plan)
        log_audit("ROOT", me["username"], my_role, "root.plan_auto_agents", "org", team_id, f"plan={plan} agents={agents}")
        st.success(f"Updated {team_id}: {plan} agents={agents}")

def render_guide():
    st.header(f"📖 {APP_NAME} Guide")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")

def render_seat(label: str, key: str):
    st.subheader(f"{label} Seat")
    st.caption(AGENT_SPECS.get(key, ""))
    rep = st.session_state.get("report", {}) or {}
    if key not in rep:
        st.info("No report yet for this seat. Run the Swarm.")
        return
    st.text_area("Output", value=str(rep.get(key)), height=360)

tab_labels = ["📖 Guide"] + [lbl for lbl, _k in AGENT_UI] + ["🤝 Team Intel"]
if my_role in {"admin","root"}:
    tab_labels.append("⚙ Org Admin")
if is_root:
    tab_labels.append("🛡 Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (lbl, k) in AGENT_UI:
    with TAB[lbl]:
        render_seat(lbl, k)

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "⚙ Org Admin" in TAB:
    with TAB["⚙ Org Admin"]:
        render_team_intel()

if "🛡 Admin" in TAB:
    with TAB["🛡 Admin"]:
        render_root_admin()
