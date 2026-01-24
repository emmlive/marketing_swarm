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

# ============================================================
# THEME: DAY / NIGHT (high contrast)
# ============================================================
def init_theme_state():
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = "Night"  # default
init_theme_state()

def inject_theme_css():
    mode = st.session_state.get("theme_mode", "Night")
    if mode == "Night":
        bg = "#0b1220"
        panel = "rgba(17, 24, 39, 0.90)"
        panel2 = "rgba(15, 23, 42, 0.75)"
        text = "#e5e7eb"
        muted = "#9ca3af"
        border = "rgba(148, 163, 184, 0.18)"
        accent = "rgba(99,102,241,0.35)"
        chip_bg = "rgba(99,102,241,0.16)"
        chip_text = "#c7d2fe"
    else:
        bg = "#ffffff"
        panel = "rgba(255,255,255,0.92)"
        panel2 = "rgba(248,250,252,0.92)"
        text = "#0f172a"
        muted = "#475569"
        border = "rgba(15,23,42,0.12)"
        accent = "rgba(99,102,241,0.20)"
        chip_bg = "rgba(99,102,241,0.10)"
        chip_text = "#3730a3"

    st.markdown(f"""
    <style>
      /* Global background */
      .stApp {{
        background: {bg};
        color: {text};
      }}

      /* Keep text readable */
      h1,h2,h3,h4,h5,h6,p,li,span,div,label {{
        color: {text} !important;
      }}
      .ms-muted {{
        color: {muted} !important;
      }}

      /* Panels/cards */
      .ms-card {{
        border: 1px solid {border};
        border-radius: 16px;
        background: {panel};
        box-shadow: 0 18px 40px rgba(0,0,0,0.20);
        padding: 14px 16px;
        margin-bottom: 10px;
      }}
      .ms-card2 {{
        border: 1px solid {border};
        border-radius: 16px;
        background: {panel2};
        padding: 12px 14px;
        margin-bottom: 10px;
      }}

      /* Chips */
      .ms-chip {{
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        border:1px solid {accent};
        background:{chip_bg};
        color:{chip_text} !important;
        font-size:12px;
      }}

      /* Tabs spacing */
      .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
      }}

      /* Hide Streamlit chrome if desired */
      #MainMenu {{visibility: hidden;}}
      footer {{visibility: hidden;}}
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

def log_audit(team_id: str, actor: str, actor_role: str, action_type: str,
              object_type: str = "", object_id: str = "", details: str = "") -> None:
    try:
        conn = db_conn()
        conn.execute("""
            INSERT INTO audit_logs (timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details)
            VALUES (?,?,?,?,?,?,?,?)
        """, (datetime.utcnow().isoformat(), team_id, actor, actor_role, action_type, object_type, object_id, details[:4000]))
        conn.commit()
        conn.close()
    except Exception:
        pass

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
    plan = str(org.get("plan", "Lite"))
    return int(org.get("seats_allowed") or PLAN_SEATS.get(plan, 1))

def active_user_count(team_id: str) -> int:
    conn = db_conn()
    df = pd.read_sql_query("SELECT COUNT(*) AS n FROM users WHERE team_id=? AND active=1 AND role!='root'", conn, params=(team_id,))
    conn.close()
    return int(df.iloc[0]["n"] or 0)

def normalize_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in {"viewer","editor","admin","root"} else "viewer"

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
    lst = [x for x in lst if any(x == k for _, k in AGENT_UI)]
    if lst:
        return lst
    # auto set if missing
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

def export_pdf(content: str, title: str, logo_file):
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
# SESSION STATE INIT (fixes your APIException)
# ============================================================
def ss_init(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default

# Swarm runner settings (these must be set BEFORE any widgets use these keys)
ss_init("swarm_running", False)
ss_init("swarm_paused", False)
ss_init("swarm_stop", False)
ss_init("swarm_queue", [])
ss_init("swarm_idx", 0)
ss_init("swarm_payload", {})
ss_init("swarm_autorun", True)
ss_init("swarm_autodelay", 3)  # seconds
ss_init("swarm_next_ts", 0.0)
ss_init("report", {})
ss_init("gen", False)
ss_init("last_active_swarm", [])
ss_init("website_url", "")
ss_init("biz_name", "")
ss_init("directives", "")

# ============================================================
# CONTEXT
# ============================================================
me = get_user(st.session_state["username"])
my_team = me.get("team_id", "ORG_001")
my_role = normalize_role(me.get("role", "viewer"))
is_root = (my_role == "root") or (my_team == "ROOT")
org = get_org(my_team)
org_plan = str(org.get("plan", "Lite"))

unlocked_agents = ALL_AGENT_KEYS if is_root else get_allowed_agents(my_team)

# ============================================================
# SIDEBAR (reorganized + collapsible Swarm Personnel)
# ============================================================
@st.cache_data(ttl=3600)
def default_geo_data() -> Dict[str, List[str]]:
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
    }

with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.caption(f"Team: `{my_team}` • Role: **{my_role.upper()}**")
    st.metric("Plan", org_plan)
    st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")

    # Day/Night toggle
    st.session_state["theme_mode"] = st.selectbox("🌗 Theme", ["Night", "Day"], index=0 if st.session_state["theme_mode"] == "Night" else 1)
    inject_theme_css()

    st.divider()

    st.text_input("🏢 Brand Name", value=st.session_state["biz_name"], key="biz_name")
    st.text_input("🌐 Business Website URL (required for Website Audit)", value=st.session_state["website_url"], key="website_url")

    geo = default_geo_data()
    state = st.selectbox("🎯 Target State", sorted(geo.keys()))
    city_mode = st.radio("City", ["Pick from list", "Add custom"], horizontal=True)
    if city_mode == "Pick from list":
        city = st.selectbox("🏙️ Target City", sorted(geo[state]))
    else:
        city = st.text_input("🏙️ Target City (custom)", value="")

    full_loc = f"{city}, {state}".strip(", ").strip()

    st.text_area("✍️ Strategic Directives", value=st.session_state["directives"], key="directives")

    st.divider()

    # Runner controls / settings
    st.markdown("### ⚙ Swarm Controls")
    st.checkbox("⚡ Auto-run remaining agents", value=st.session_state["swarm_autorun"], key="swarm_autorun")
    st.selectbox("⏱ Auto-run delay", [1, 3, 5], index=[1,3,5].index(int(st.session_state["swarm_autodelay"])), key="swarm_autodelay")

    if st.session_state["swarm_running"]:
        st.warning("Swarm is running")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⏸ Pause", use_container_width=True):
                st.session_state["swarm_paused"] = True
                st.rerun()
            if st.button("▶ Resume", use_container_width=True):
                st.session_state["swarm_paused"] = False
                st.rerun()
        with c2:
            if st.button("🛑 Stop", type="secondary", use_container_width=True):
                st.session_state["swarm_stop"] = True
                st.session_state["swarm_running"] = False
                st.session_state["swarm_paused"] = False
                st.toast("Stopped.", icon="🛑")
                st.rerun()

    # Collapsible Swarm Personnel
    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption("Select unlocked agents to run. Locked agents are disabled.")
        for label, key in AGENT_UI:
            k = f"tg_{key}"
            if k not in st.session_state:
                st.session_state[k] = False
            disabled = (not is_root) and (key not in unlocked_agents)
            st.toggle(label, key=k, disabled=disabled)
            if disabled:
                st.caption(f"🔒 Locked by plan: {key}")

    st.divider()

    # Launch
    if not st.session_state["swarm_running"]:
        if st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True):
            selected = [k for _lbl, k in AGENT_UI if st.session_state.get(f"tg_{k}", False)]
            if not st.session_state["biz_name"].strip():
                st.error("Enter Brand Name first.")
            elif not selected:
                st.warning("Select at least one agent.")
            else:
                st.session_state["last_active_swarm"] = selected[:]
                st.session_state["swarm_payload"] = {
                    "biz_name": st.session_state["biz_name"].strip(),
                    "city": full_loc or "USA",
                    "directives": st.session_state["directives"].strip(),
                    "url": st.session_state["website_url"].strip(),
                    "package": org_plan,
                }
                st.session_state["swarm_queue"] = selected[:]
                st.session_state["swarm_idx"] = 0
                st.session_state["swarm_running"] = True
                st.session_state["swarm_paused"] = False
                st.session_state["swarm_stop"] = False
                st.session_state["swarm_next_ts"] = time.time()  # run immediately
                st.session_state["report"] = {}
                st.session_state["gen"] = False
                st.toast("Swarm started.", icon="🚀")
                st.rerun()

    authenticator.logout("🔒 Sign Out", "sidebar")

# ============================================================
# TOP BANNER (return to dashboard while running)
# ============================================================
if st.session_state["swarm_running"]:
    q = st.session_state["swarm_queue"]
    idx = int(st.session_state["swarm_idx"])
    total = len(q)
    next_agent = q[idx] if idx < total else "—"
    st.markdown(
        f"""
        <div class="ms-card">
          <b>🚀 Swarm Running</b>
          <span class="ms-chip">Next: {next_agent}</span>
          <div class="ms-muted">You can navigate tabs while the swarm runs. Use Pause/Stop in the sidebar.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# SWARM RUNNER (one-by-one + autorun delay)
# ============================================================
def is_placeholder(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    low = s.lower()
    if low.startswith("agent not selected"):
        return True
    if "not selected for this run" in low:
        return True
    return False

def swarm_run_one_agent(agent_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Runs only one agent
    p = dict(payload)
    p["active_swarm"] = [agent_key]
    out = run_marketing_swarm(p) or {}
    return out

def build_full_report(payload: Dict[str, Any], report: Dict[str, Any]) -> str:
    biz = payload.get("biz_name", "")
    loc = payload.get("city", "")
    plan = payload.get("package", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sections = []
    for _lbl, k in AGENT_UI:
        if k in report and not is_placeholder(report.get(k)):
            sections.append(f"## {k}\n{report.get(k)}")
    if not sections:
        sections = ["## Summary\nNo outputs generated."]
    return f"# {biz} Intelligence Report\n**Date:** {now} | **Location:** {loc} | **Plan:** {plan}\n---\n\n" + "\n\n".join(sections)

# Auto-run tick
if st.session_state["swarm_running"] and (not st.session_state["swarm_paused"]) and (not st.session_state["swarm_stop"]):
    # Only run if time reached
    if time.time() >= float(st.session_state["swarm_next_ts"]):
        q = st.session_state["swarm_queue"]
        idx = int(st.session_state["swarm_idx"])
        if idx >= len(q):
            # finished
            st.session_state["swarm_running"] = False
            st.session_state["gen"] = True
            st.toast("✅ Swarm completed.", icon="✅")
        else:
            agent_key = q[idx]
            payload = dict(st.session_state["swarm_payload"])
            with st.status(f"Running {agent_key}…", expanded=True) as status:
                out = {}
                try:
                    out = swarm_run_one_agent(agent_key, payload)
                except Exception as e:
                    st.error(str(e))
                    out = {}

                # merge
                rep = dict(st.session_state["report"] or {})
                if agent_key in out and not is_placeholder(out.get(agent_key)):
                    rep[agent_key] = out.get(agent_key)
                else:
                    # if main returns different field, still keep whatever it returned
                    # but do not store placeholders
                    if agent_key in out and not is_placeholder(out.get(agent_key)):
                        rep[agent_key] = out.get(agent_key)

                rep["full_report"] = build_full_report(payload, rep)
                st.session_state["report"] = rep

                status.update(label=f"✅ {agent_key} done", state="complete", expanded=False)

            st.session_state["swarm_idx"] = idx + 1
            # schedule next tick
            st.session_state["swarm_next_ts"] = time.time() + float(st.session_state["swarm_autodelay"]) if st.session_state["swarm_autorun"] else 10**12
            # if not autorun, pause instead
            if not st.session_state["swarm_autorun"]:
                st.session_state["swarm_paused"] = True
        st.rerun()

# ============================================================
# RENDERERS
# ============================================================
def seat_how_to_use(agent_key: str) -> str:
    guides = {
        "analyst": "Use this to price your services, position against competitors, and pick 3 offers to push for 30 days.",
        "marketing_adviser": "Use this to pick your channel priorities, define messaging pillars, and set weekly KPIs.",
        "market_researcher": "Use this to choose segments, build an ICP, and identify demand themes for content + ads.",
        "ecommerce_marketer": "Use this to build an offer ladder, landing page structure, email/SMS flows, and remarketing.",
        "ads": "Copy into Google Ads / Meta Ads Manager. Keep claims verifiable; add your proof points.",
        "creative": "Use the concepts to brief designers; use the prompt pack in Midjourney/Canva/Runway batches.",
        "guest_posting": "Use the outreach templates to contact sites; track pitches in Projects + Kanban.",
        "strategist": "Follow the weekly roadmap. Assign tasks in Projects and review KPIs weekly.",
        "social": "Schedule the calendar. Reuse winning hooks in ads and email.",
        "geo": "Apply GBP checklist, citation plan, and review system. Track progress weekly.",
        "audit": "Fix top issues first; prioritize mobile speed, trust, and conversion friction. Re-run after updates.",
        "seo": "Publish the article, then build supporting pages from the cluster suggestions.",
    }
    return guides.get(agent_key, "Apply this output to your marketing execution plan.")

def render_guide():
    st.header(f"📖 {APP_NAME} Guide")
    st.markdown("**How to use your intelligence outputs:**")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")
    st.markdown("---")
    st.subheader("Unlocked Agents")
    st.write(unlocked_agents)

def render_seat(label: str, key: str):
    st.subheader(f"{label} Seat")
    st.caption(AGENT_SPECS.get(key, ""))
    st.info(seat_how_to_use(key))

    rep = st.session_state.get("report", {}) or {}
    if key not in rep or is_placeholder(rep.get(key)):
        st.warning("No report yet for this seat. Run the Swarm.")
        return

    edited = st.text_area("Refine Intel", value=str(rep.get(key)), height=380, key=f"ed_{key}")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📄 Word", export_word(edited, label), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
    with c2:
        st.download_button("📕 PDF", export_pdf(edited, label, None), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)

def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Org-scoped tools for team execution + collaboration.")
    tabs = st.tabs(["🧩 Projects", "🗂 Kanban Leads", "🧾 Reports Vault", "👥 Users & RBAC", "🔐 Security Logs"])

    # Projects (collab tools)
    with tabs[0]:
        st.subheader("Projects")
        conn = db_conn()
        pdf = pd.read_sql_query("SELECT id,name,owner,status,created_at FROM projects WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(pdf, use_container_width=True, hide_index=True)

        with st.expander("➕ New Project", expanded=False):
            with st.form("proj_new"):
                name = st.text_input("Project name")
                owner = st.text_input("Owner", value=me.get("username", ""))
                status = st.selectbox("Status", ["Active", "Paused", "Done"], index=0)
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("INSERT INTO projects (team_id,name,owner,status,notes) VALUES (?,?,?,?,?)",
                             (my_team, name, owner, status, notes))
                conn.commit(); conn.close()
                log_audit(my_team, me["username"], my_role, "project.create", "project", "", name)
                st.success("Created.")
                st.rerun()

        st.markdown("---")
        st.subheader("Project Tasks")
        conn = db_conn()
        tdf = pd.read_sql_query("SELECT id,project_id,title,assignee,status,due_date FROM project_tasks WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(tdf, use_container_width=True, hide_index=True)

    # Kanban Leads
    with tabs[1]:
        st.subheader("Kanban Leads")
        stages = ["Discovery", "Execution", "ROI Verified"]
        conn = db_conn()
        ldf = pd.read_sql_query("SELECT * FROM leads WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()

        cols = st.columns(3)
        for i, stage in enumerate(stages):
            with cols[i]:
                st.markdown(f"### {stage}")
                sdf = ldf[ldf["stage"] == stage] if not ldf.empty else pd.DataFrame()
                for _, r in sdf.iterrows():
                    st.write(f"- {r.get('title','')} ({r.get('city','')})")

        with st.expander("➕ Add Lead", expanded=False):
            with st.form("lead_new"):
                title = st.text_input("Lead title")
                city = st.text_input("City")
                service = st.text_input("Service")
                stage = st.selectbox("Stage", stages, index=0)
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("INSERT INTO leads (team_id,title,city,service,stage) VALUES (?,?,?,?,?)",
                             (my_team, title, city, service, stage))
                conn.commit(); conn.close()
                log_audit(my_team, me["username"], my_role, "lead.create", "lead", "", title)
                st.success("Created.")
                st.rerun()

    # Reports Vault
    with tabs[2]:
        st.subheader("Reports Vault")
        rep = st.session_state.get("report", {}) or {}
        if rep:
            with st.form("vault_save"):
                name = st.text_input("Report name", value=f"{st.session_state['biz_name']} • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                submit = st.form_submit_button("Save Current Report", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("""
                    INSERT INTO reports_vault (team_id,name,created_by,location,biz_name,selected_agents_json,report_json,full_report)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (my_team, name, me["username"], full_loc, st.session_state["biz_name"],
                      json.dumps(st.session_state.get("last_active_swarm", [])),
                      json.dumps(rep), str(rep.get("full_report",""))))
                conn.commit(); conn.close()
                log_audit(my_team, me["username"], my_role, "vault.save", "report", "", name)
                st.success("Saved.")
                st.rerun()

        conn = db_conn()
        vdf = pd.read_sql_query("SELECT id,name,biz_name,location,created_by,created_at FROM reports_vault WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(vdf, use_container_width=True, hide_index=True)

    # Users & RBAC
    with tabs[3]:
        st.subheader("Users & RBAC")
        conn = db_conn()
        udf = pd.read_sql_query("SELECT username,name,email,role,credits,active FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(udf, use_container_width=True, hide_index=True)

    # Security Logs
    with tabs[4]:
        conn = db_conn()
        logs = pd.read_sql_query("SELECT timestamp,actor,action_type,object_type,object_id,details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 250", conn, params=(my_team,))
        conn.close()
        st.dataframe(logs, use_container_width=True, hide_index=True)

def render_root_admin():
    st.header("🛡️ SaaS Root Admin")
    st.caption("Manage orgs, plans, allowed agents, users, credits, and logs.")
    tabs = st.tabs(["🏢 Orgs", "🪄 Plan → Auto Agents", "📜 Global Logs"])
    with tabs[0]:
        conn = db_conn()
        odf = pd.read_sql_query("SELECT team_id,org_name,plan,seats_allowed,status,allowed_agents_json FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(odf, use_container_width=True, hide_index=True)

    with tabs[1]:
        team_id = st.text_input("Team ID")
        plan = st.selectbox("Plan", ["Lite","Pro","Enterprise","Unlimited"], index=0)
        if st.button("Apply Plan + Auto Agents", use_container_width=True):
            agents = set_org_plan_and_auto_agents(team_id.strip(), plan)
            log_audit("ROOT", me["username"], my_role, "root.plan_auto_agents", "org", team_id, f"plan={plan} agents={agents}")
            st.success(f"Updated {team_id}: {plan} agents={agents}")

    with tabs[2]:
        conn = db_conn()
        gdf = pd.read_sql_query("SELECT timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(gdf, use_container_width=True, hide_index=True)

# ============================================================
# MAIN TABS (ensure Team Intel always present, Root Admin always present for root)
# ============================================================
tab_labels = ["📖 Guide"] + [lbl for lbl, _k in AGENT_UI] + ["🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (lbl, k) in AGENT_UI:
    with TAB[lbl]:
        render_seat(lbl, k)

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
