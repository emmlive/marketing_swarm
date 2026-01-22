import os
import re
import csv
import json
import time
import sqlite3
import unicodedata
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
# CONFIG
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")

DB_PATH = "breatheeasy.db"
APP_LOGO_PATH = "Logo1.jpeg"

PRODUCTION_MODE = True  # hides Streamlit chrome (NOT Streamlit Cloud overlays)

PLAN_SEATS = {"Lite": 1, "Basic": 1, "Pro": 5, "Enterprise": 20, "Unlimited": 9999}
PLAN_AGENT_LIMITS = {"Lite": 3, "Basic": 3, "Pro": 5, "Enterprise": 8, "Unlimited": 8}

ALL_AGENT_KEYS = ["analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo"]
AGENT_LABELS = {
    "analyst": "🕵️ Analyst",
    "ads": "📺 Ads",
    "creative": "🎨 Creative",
    "strategist": "👔 Strategist",
    "social": "📱 Social",
    "geo": "📍 GEO",
    "audit": "🌐 Auditor",
    "seo": "✍ SEO",
}
AGENT_SPECS = {
    "analyst": "Competitor gaps, pricing, positioning.",
    "ads": "Deployable ads for Google/Meta.",
    "creative": "Concepts + prompt packs + ad variants.",
    "strategist": "30-day execution roadmap.",
    "social": "Engagement content calendar.",
    "geo": "Local visibility and citations.",
    "audit": "Website conversion friction.",
    "seo": "Authority article + cluster plan.",
}

DEPLOY_PROTOCOL = [
    "Configure mission in the sidebar (Brand, Location, Directives).",
    "Agents are **locked by plan** (upgrade to unlock more).",
    "Click **LAUNCH OMNI-SWARM**.",
    "Review and refine outputs in each seat.",
    "Export as Word/PDF and publish via platform consoles.",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]


# ============================================================
# CSS
# ============================================================
def inject_css_once():
    if st.session_state.get("_css_loaded"):
        return
    st.session_state["_css_loaded"] = True

    hide_chrome = ""
    if PRODUCTION_MODE:
        hide_chrome = """
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header[data-testid="stHeader"] {visibility: hidden; height: 0px;}
        [data-testid="stToolbar"] {visibility: hidden;}
        """

    st.markdown(f"""
    <style>
      {hide_chrome}
      .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
      .ms-card {{
        border: 1px solid rgba(15,23,42,0.10);
        border-radius: 18px;
        background: rgba(255,255,255,0.94);
        box-shadow: 0 24px 60px rgba(2,6,23,0.08);
        padding: 16px;
      }}
      .ms-bar {{
        height: 10px; border-radius: 999px;
        background: linear-gradient(90deg, rgba(99,102,241,0.20), rgba(16,185,129,0.20), rgba(236,72,153,0.20));
        overflow: hidden; position: relative;
      }}
      .ms-bar::after {{
        content:""; position:absolute; top:0; left:-40%; width:40%; height:100%;
        background: linear-gradient(90deg, transparent, rgba(99,102,241,0.75), transparent);
        animation: ms-slide 1.2s infinite;
      }}
      @keyframes ms-slide {{ 0%{{left:-40%}} 100%{{left:100%}} }}
      .bg {{
        position: fixed; inset: 0;
        background:
          radial-gradient(1200px 600px at 50% 0%, rgba(99,102,241,0.18), transparent 60%),
          radial-gradient(900px 500px at 10% 30%, rgba(16,185,129,0.14), transparent 60%),
          radial-gradient(900px 500px at 90% 30%, rgba(236,72,153,0.12), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #fafafe 60%, #ffffff 100%);
        z-index: -1;
      }}
      .shell {{ max-width: 1120px; margin: 0 auto; padding: 26px 12px 40px; }}
      .title {{ font-size: 44px; font-weight: 850; letter-spacing:-0.02em; margin: 6px 0 8px; color:#0f172a; }}
      .sub {{ color:#334155; font-size:14px; margin:0 0 16px; }}
      .grid {{ display:grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; }}
      .pricing {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
      .pricecard {{ border:1px solid rgba(15,23,42,0.10); border-radius: 16px; padding: 12px; background: rgba(255,255,255,0.92); }}
      .price {{ font-size: 26px; font-weight: 900; }}
      @media (max-width: 980px){{ .grid {{ grid-template-columns: 1fr; }} .pricing {{ grid-template-columns: 1fr; }} .title{{font-size:34px;}} }}
    </style>
    """, unsafe_allow_html=True)

inject_css_once()


# ============================================================
# DB + TENANCY
# ============================================================
def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

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
            allowed_agents_json TEXT DEFAULT '[]',
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
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            channel TEXT,
            status TEXT DEFAULT 'draft',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            asset_type TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            enabled INTEGER DEFAULT 0,
            trigger TEXT,
            steps TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            enabled INTEGER DEFAULT 0,
            config_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    ensure_column(conn, "orgs", "allowed_agents_json", "TEXT DEFAULT '[]'")
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")

    # Root org + root user
    cur.execute("""
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, allowed_agents_json, status)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, '[]', 'active')
    """)
    root_pw = stauth.Hasher.hash("root123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """, (root_pw,))

    # Demo org
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        default_allowed = json.dumps(["analyst", "creative", "strategist"])
        cur.execute("""
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, allowed_agents_json, status)
            VALUES ('ORG_001', 'TechNovance Customer', 'Lite', 1, ?, 'active')
        """, (default_allowed,))
        admin_pw = stauth.Hasher.hash("admin123")
        cur.execute("""
            INSERT OR REPLACE INTO users
            (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES ('admin','admin@customer.ai','Org Admin',?, 'admin',1,'Lite',999,1,'ORG_001')
        """, (admin_pw,))

    conn.commit()
    conn.close()

def log_audit(team_id: str, actor: str, actor_role: str, action_type: str,
              object_type: str = "", object_id: str = "", details: str = "") -> None:
    try:
        conn = db_conn()
        conn.execute("""
            INSERT INTO audit_logs (timestamp, team_id, actor, actor_role, action_type, object_type, object_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), team_id, actor, actor_role, action_type, object_type, object_id, details))
        conn.commit()
        conn.close()
    except Exception:
        pass

def get_org(team_id: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM orgs WHERE team_id=?", conn, params=(team_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {"team_id": team_id, "org_name": team_id, "plan": "Lite", "seats_allowed": 1, "allowed_agents_json": "[]"}

def get_user(username: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(username,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}

def normalize_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in {"viewer","editor","admin","root"} else "viewer"

def plan_agent_limit(plan: str) -> int:
    return int(PLAN_AGENT_LIMITS.get(plan, 3))

def allowed_agents_for_org(team_id: str) -> List[str]:
    org = get_org(team_id)
    raw = org.get("allowed_agents_json") or "[]"
    try:
        lst = json.loads(raw)
        return [x for x in lst if x in ALL_AGENT_KEYS]
    except Exception:
        return []

def set_allowed_agents_for_org(team_id: str, agents: List[str]) -> None:
    agents = [a for a in agents if a in ALL_AGENT_KEYS]
    conn = db_conn()
    conn.execute("UPDATE orgs SET allowed_agents_json=? WHERE team_id=?", (json.dumps(agents), team_id))
    conn.commit()
    conn.close()

def set_org_plan(team_id: str, plan: str) -> None:
    plan = plan.strip()
    seats = PLAN_SEATS.get(plan, 1)
    limit = plan_agent_limit(plan)
    auto_agents = ALL_AGENT_KEYS[:limit]
    conn = db_conn()
    conn.execute(
        "UPDATE orgs SET plan=?, seats_allowed=?, allowed_agents_json=? WHERE team_id=?",
        (plan, int(seats), json.dumps(auto_agents), team_id)
    )
    conn.commit()
    conn.close()

def active_user_count(team_id: str) -> int:
    conn = db_conn()
    df = pd.read_sql_query("SELECT COUNT(*) AS n FROM users WHERE team_id=? AND active=1 AND role!='root'", conn, params=(team_id,))
    conn.close()
    return int(df.iloc[0]["n"] or 0)

def seats_allowed_for_team(team_id: str) -> int:
    org = get_org(team_id)
    plan = str(org.get("plan", "Lite"))
    return int(org.get("seats_allowed") or PLAN_SEATS.get(plan, 1))

def create_user(team_id: str, username: str, name: str, email: str, password_plain: str, role: str) -> Tuple[bool, str]:
    username = (username or "").strip()
    if not username:
        return False, "Username required."
    if username.lower() == "root":
        return False, "Reserved username."
    role = normalize_role(role)
    if role == "root":
        return False, "Root role cannot be assigned."

    seats = seats_allowed_for_team(team_id)
    used = active_user_count(team_id)
    if used >= seats:
        return False, f"Seat limit reached ({used}/{seats}). Upgrade to add more users."

    hashed = stauth.Hasher.hash(password_plain)
    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO users (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES (?, ?, ?, ?, ?, 1, (SELECT plan FROM orgs WHERE team_id=?), 10, 1, ?)
        """, (username, email, name, hashed, role, team_id, team_id))
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def set_user_active(team_id: str, username: str, active: int) -> None:
    conn = db_conn()
    conn.execute("UPDATE users SET active=? WHERE username=? AND team_id=? AND role!='root'", (int(active), username, team_id))
    conn.commit()
    conn.close()

def update_user_role(team_id: str, username: str, role: str) -> None:
    role = normalize_role(role)
    if role == "root":
        return
    conn = db_conn()
    conn.execute("UPDATE users SET role=? WHERE username=? AND team_id=? AND role!='root'", (role, username, team_id))
    conn.commit()
    conn.close()

def bulk_import_users(team_id: str, csv_bytes: bytes) -> Tuple[int, List[str]]:
    errors = []
    created = 0
    seats = seats_allowed_for_team(team_id)
    used = active_user_count(team_id)
    remaining = max(0, seats - used)

    decoded = csv_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(decoded.splitlines())
    rows = list(reader)

    if len(rows) > remaining:
        errors.append(f"Seat limit: only {remaining} more user(s) can be added ({used}/{seats}). Extra rows ignored.")
        rows = rows[:remaining]

    for i, r in enumerate(rows, start=1):
        u = (r.get("username") or "").strip()
        n = (r.get("name") or u).strip()
        e = (r.get("email") or "").strip()
        ro = normalize_role(r.get("role") or "viewer")
        pw = (r.get("password") or "").strip()
        if not u or not pw:
            errors.append(f"Row {i}: missing username or password.")
            continue
        ok, msg = create_user(team_id, u, n, e, pw, ro)
        if ok:
            created += 1
        else:
            errors.append(f"Row {i} ({u}): {msg}")

    return created, errors

def normalize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    alias_map = {
        "market_data": "analyst",
        "website_audit": "audit",
        "ads_output": "ads",
        "creative_pack": "creative",
        "strategist_brief": "strategist",
        "social_plan": "social",
        "geo_intel": "geo",
        "seo_article": "seo",
    }
    fixed = dict(report)
    for src, dst in alias_map.items():
        if dst not in fixed and src in fixed and fixed.get(src):
            fixed[dst] = fixed.get(src)
    return fixed

def is_placeholder_output(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    # the default placeholders from your state
    if s.lower().startswith("agent not selected"):
        return True
    if "not selected for this run" in s.lower():
        return True
    if "not generated" in s.lower():
        return True
    return False

init_db_once()


# ============================================================
# EXPORT
# ============================================================
_original_putpages = fpdf.fpdf.FPDF._putpages
def _patched_putpages(self):
    pages = self.pages
    self.pages = {}
    for k, v in pages.items():
        if isinstance(v, str):
            v = v.encode("latin-1","ignore").decode("latin-1","ignore")
        self.pages[k] = v
    _original_putpages(self)
fpdf.fpdf.FPDF._putpages = _patched_putpages

def export_pdf(content: str, title: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_font("Arial","B",14)
    pdf.cell(0, 7, str(title), ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 6, str(content))
    return pdf.output(dest="S").encode("latin-1")

def export_word(content: str, title: str) -> bytes:
    doc = Document()
    doc.add_heading(f"{title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# AUTH (Fresh creds each unauth render)
# ============================================================
def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users WHERE active=1", conn)
        return {"usernames": {r["username"]: {"email": r.get("email",""), "name": r.get("name", r["username"]), "password": r["password"]} for _, r in df.iterrows()}}
    finally:
        conn.close()

if not st.session_state.get("authentication_status"):
    st.session_state["authenticator"] = stauth.Authenticate(
        get_db_creds(),
        st.secrets["cookie"]["name"],
        st.secrets["cookie"]["key"],
        30
    )
authenticator = st.session_state["authenticator"]

def login_page():
    st.markdown('<div class="bg"></div><div class="shell">', unsafe_allow_html=True)

    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=70)

    st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Root login: <b>root / root123</b></div>', unsafe_allow_html=True)

    st.markdown('<div class="grid">', unsafe_allow_html=True)

    # Pricing
    st.markdown('<div class="ms-card">', unsafe_allow_html=True)
    st.markdown("### Pricing")
    st.markdown('<div class="pricing">', unsafe_allow_html=True)
    st.markdown('<div class="pricecard"><b>🥉 Lite</b><div class="price">$99/mo</div><div style="color:#475569;font-size:13px;">Seats: 1 • Agents: 3</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pricecard"><b>🥈 Pro</b><div class="price">$299/mo</div><div style="color:#475569;font-size:13px;">Seats: 5 • Agents: 5</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="pricecard"><b>🥇 Enterprise</b><div class="price">$999/mo</div><div style="color:#475569;font-size:13px;">Seats: 20 • Agents: 8</div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### What you get")
    st.markdown("- Org isolation (Team ID)\n- RBAC (Admin / Editor / Viewer)\n- Audit logs\n- Locked agents per plan")
    st.markdown("</div>", unsafe_allow_html=True)

    # Login
    st.markdown('<div class="ms-card">', unsafe_allow_html=True)
    tabs = st.tabs(["Login", "Forgot Password", "Refresh Credentials"])
    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state["username"])
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u["username"]))
            conn.commit(); conn.close()
            log_audit(u["team_id"], u["username"], u.get("role",""), "auth.login", "user", u["username"], "login_success")
            st.rerun()
    with tabs[1]:
        authenticator.forgot_password(location="main")
    with tabs[2]:
        if st.button("Refresh Now", use_container_width=True):
            st.session_state.pop("authenticator", None)
            st.session_state["authentication_status"] = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()

if not st.session_state.get("authentication_status"):
    login_page()


# ============================================================
# POST-AUTH CONTEXT
# ============================================================
me = get_user(st.session_state["username"])
my_team = me.get("team_id", "ORG_001")
my_role = normalize_role(me.get("role", "viewer"))
is_root = (my_role == "root") or (my_team == "ROOT")
org = get_org(my_team)
org_plan = str(org.get("plan", "Lite"))

allowed_agents = allowed_agents_for_org(my_team)
if not allowed_agents and not is_root:
    # Fixes your “Unlocked agents: []” issue by auto-initializing
    set_org_plan(my_team, org_plan)
    allowed_agents = allowed_agents_for_org(my_team)

visible_agent_keys = ALL_AGENT_KEYS if is_root else allowed_agents


# ============================================================
# SIDEBAR
# ============================================================
@st.cache_data(ttl=3600)
def default_geo_data():
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
        "California": ["Los Angeles", "San Francisco", "San Diego"],
        "Florida": ["Miami", "Orlando", "Tampa"],
        "Illinois": ["Chicago", "Naperville", "Plainfield"],
        "Texas": ["Austin", "Dallas", "Houston"],
    }

with st.sidebar:
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=110)
    st.subheader(org.get("org_name", "Organization"))
    st.caption(f"Team: `{my_team}` • Role: **{my_role.upper()}**")
    st.metric("Plan", org_plan)
    if not is_root:
        st.caption(f"Unlocked agents: {len(allowed_agents)}/{plan_agent_limit(org_plan)}")
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", value=st.session_state.get("biz_name", ""))
    st.session_state["biz_name"] = biz_name

    custom_logo = st.file_uploader("📤 Brand Logo", type=["png", "jpg", "jpeg"])

    geo = default_geo_data()
    selected_state = st.selectbox("🎯 Target State", sorted(geo.keys()))
    selected_city = st.selectbox("🏙️ Target City", sorted(geo[selected_state]))
    full_loc = f"{selected_city}, {selected_state}"

    st.divider()
    directives = st.text_area("✍️ Strategic Directives", value=st.session_state.get("directives", ""))
    st.session_state["directives"] = directives

    st.markdown("### 🤖 Swarm Personnel (Locked)")
    effective_allowed = ALL_AGENT_KEYS if is_root else allowed_agents

    toggles: Dict[str, bool] = {}
    for k in ALL_AGENT_KEYS:
        toggles[k] = st.toggle(
            AGENT_LABELS[k],
            value=bool(st.session_state.get(f"tg_{k}", False)) if k in effective_allowed else False,
            disabled=(k not in effective_allowed),
            key=f"tg_{k}"
        )

    st.divider()
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
    authenticator.logout("Sign Out", "sidebar")


# ============================================================
# RUN SWARM
# ============================================================
def safe_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return run_marketing_swarm(payload) or {}
    except Exception as e:
        st.error(f"Swarm error: {e}")
        log_audit(my_team, me["username"], my_role, "swarm.error", "swarm", "", str(e)[:2000])
        return {}

if run_btn:
    active_agents = [k for k, v in toggles.items() if v]
    st.session_state["last_active_swarm"] = active_agents

    if not biz_name:
        st.error("Enter Brand Name first.")
    elif not active_agents:
        st.warning("Select at least one agent.")
    else:
        box = st.empty()
        with box.container():
            st.markdown('<div class="ms-card">', unsafe_allow_html=True)
            st.markdown("### 🚀 Running Swarm…")
            st.markdown('<div class="ms-bar"></div>', unsafe_allow_html=True)
            st.write("")
            st.write("Selected agents:", active_agents)
            st.markdown("</div>", unsafe_allow_html=True)

        report = safe_run({
            "city": full_loc,
            "biz_name": biz_name,
            "active_swarm": active_agents,
            "package": org_plan,
            "custom_logo": custom_logo,
            "directives": directives,
        })
        report = normalize_report(report)
        box.empty()

        # Filter out placeholder outputs
        cleaned = {}
        for k, v in report.items():
            if k == "full_report":
                cleaned[k] = v
                continue
            if not is_placeholder_output(v):
                cleaned[k] = v

        st.session_state["last_report_keys"] = sorted(list(cleaned.keys()))
        if cleaned:
            st.session_state["report"] = cleaned
            st.session_state["gen"] = True
            log_audit(my_team, me["username"], my_role, "swarm.run", "swarm", biz_name, f"agents={active_agents}")
        else:
            st.session_state["report"] = {}
            st.session_state["gen"] = False
            log_audit(my_team, me["username"], my_role, "swarm.empty", "swarm", biz_name, f"agents={active_agents}")

        st.rerun()


# ============================================================
# RENDERERS
# ============================================================
def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Mission: **{st.session_state.get('biz_name', 'Global Mission')}**")
    st.subheader("Execution Protocol")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")
    st.markdown("---")
    st.subheader("Unlocked Agents")
    st.write(visible_agent_keys)

def render_agent_seat(title: str, key: str):
    st.subheader(f"{title} Seat")
    st.caption(AGENT_SPECS.get(key, ""))

    report = st.session_state.get("report") or {}
    selected = st.session_state.get("last_active_swarm", [])
    st.caption(f"Selected this run: {'✅ YES' if key in selected else '❌ NO'}")
    st.caption(f"Last report keys: {st.session_state.get('last_report_keys', [])}")

    if key in selected and st.session_state.get("gen") and (key not in report or is_placeholder_output(report.get(key))):
        st.error("This agent was selected, but it returned placeholder output. Check provider limits or main.py.")
        return

    if st.session_state.get("gen") and report.get(key) and not is_placeholder_output(report.get(key)):
        edited = st.text_area("Refine Intel", value=str(report.get(key)), height=420, key=f"ed_{key}")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📄 Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
        with c2:
            st.download_button("📕 PDF", export_pdf(edited, title), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)

        if key in {"ads", "creative", "social"}:
            st.markdown("---")
            st.markdown("#### 📣 Publish / Push")
            st.text_area("Copy-ready content", value=edited, height=140, key=f"push_{key}")
            cols = st.columns(4)
            for i, (nm, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
                with cols[i % 4]:
                    st.link_button(nm, url)
        return

    st.info("No content yet. Run the swarm to generate this seat.")

def render_vision():
    st.header("👁️ Vision")
    st.info("Reserved for future visual analysis workflows.")

def render_veo():
    st.header("🎬 Veo Studio")
    st.info("Reserved for future video generation workflows.")

def render_team_intel_minimal():
    st.header("🤝 Team Intel")
    st.caption("Org dashboard (scoped).")
    st.write(f"Unlocked agents: {allowed_agents}")

    if my_role in {"admin", "root"}:
        st.markdown("---")
        st.subheader("Org Admin Tools")

        # Users
        with st.expander("👥 Users (Seats enforced)", expanded=False):
            conn = db_conn()
            udf = pd.read_sql_query(
                "SELECT username,name,email,role,active,created_at,last_login_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC",
                conn, params=(my_team,)
            )
            conn.close()
            st.dataframe(udf, width="stretch")

            seats = seats_allowed_for_team(my_team)
            used = active_user_count(my_team)
            st.info(f"Seats: {used}/{seats}")

            st.markdown("### Add user")
            with st.form("add_user_form"):
                u = st.text_input("Username")
                n = st.text_input("Name")
                e = st.text_input("Email")
                r = st.selectbox("Role", ["viewer","editor","admin"])
                pw = st.text_input("Temp Password", type="password")
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                ok, msg = create_user(my_team, u, n, e, pw, r)
                if ok:
                    log_audit(my_team, me["username"], my_role, "user.create", "user", u, f"role={r}")
                    st.success(msg); st.rerun()
                else:
                    st.error(msg)

            st.markdown("### Bulk import CSV")
            st.caption("Headers: username,name,email,role,password")
            up = st.file_uploader("Upload CSV", type=["csv"], key="bulk_users")
            if up and st.button("Import Users", use_container_width=True):
                created, errs = bulk_import_users(my_team, up.getvalue())
                log_audit(my_team, me["username"], my_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                if created:
                    st.success(f"Imported {created} user(s).")
                if errs:
                    st.error("Issues:")
                    for x in errs[:15]:
                        st.write(f"- {x}")
                st.rerun()

def render_root_admin():
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend.")

    tabs = st.tabs(["🏢 Orgs", "🔧 Set Plan → Auto Agents", "📜 Logs"])
    with tabs[0]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, allowed_agents_json FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, width="stretch")

    with tabs[1]:
        conn = db_conn()
        orgs_df = pd.read_sql_query("SELECT team_id, org_name, plan FROM orgs WHERE team_id!='ROOT' ORDER BY org_name", conn)
        conn.close()
        if orgs_df.empty:
            st.info("No orgs found.")
            return
        team_id = st.selectbox("Org", orgs_df["team_id"].tolist())
        new_plan = st.selectbox("New plan", ["Lite", "Pro", "Enterprise", "Unlimited"], index=0)
        if st.button("Apply plan + auto agents", use_container_width=True):
            set_org_plan(team_id, new_plan)
            log_audit("ROOT", me["username"], my_role, "root.plan_update", "org", team_id, f"plan={new_plan}")
            st.success("Applied.")
            st.rerun()

    with tabs[2]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT timestamp, team_id, actor, actor_role, action_type, object_type, object_id, details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(df, width="stretch")


# ============================================================
# TABS (Lite now shows non-empty tabs: only unlocked agent seats)
# ============================================================
agent_tabs = [AGENT_LABELS[k] for k in visible_agent_keys]
tab_labels = ["📖 Guide"] + agent_tabs + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for k in visible_agent_keys:
    with TAB[AGENT_LABELS[k]]:
        render_agent_seat(AGENT_LABELS[k], k)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel_minimal()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
