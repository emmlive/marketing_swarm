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

# IMPORTANT: main.py must expose run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]
from main import run_marketing_swarm

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")

DB_PATH = "breatheeasy.db"
APP_LOGO_PATH = "Logo1.jpeg"
PRODUCTION_MODE = True  # hides Streamlit chrome (not Streamlit Cloud overlays)

# ------------------------------------------------------------
# Agents (keys MUST match main.py)
# ------------------------------------------------------------
AGENT_SPECS: Dict[str, str] = {
    "analyst": "🕵️ **Market Analyst**: competitor gaps, pricing, positioning, offers.",
    "marketing_adviser": "🧭 **Marketing Adviser**: messaging, channel priorities, next steps.",
    "market_researcher": "📊 **Market Researcher**: segments, competitors, insights, assumptions.",
    "ecommerce_marketer": "🛒 **E‑Commerce Marketer**: positioning, funnel, email/SMS, upsells.",
    "ads": "📺 **Ads Architect**: Google/Meta ad copy (tables).",
    "creative": "🎨 **Creative Director**: concepts + prompt packs + ad variants.",
    "guest_posting": "📰 **Guest Posting**: outreach list, pitches, topics, placement plan.",
    "strategist": "👔 **Strategist**: 30‑day roadmap + KPIs.",
    "social": "📱 **Social**: 30‑day engagement calendar.",
    "geo": "📍 **GEO**: local visibility & citations.",
    "audit": "🌐 **Website Audit**: conversion friction (needs URL).",
    "seo": "✍️ **Search Engine Marketing (SEO)**: authority article + cluster plan.",
}

# UI order (seats)
AGENT_ORDER: List[Tuple[str, str]] = [
    ("🕵️ Analyst", "analyst"),
    ("🧭 Marketing Adviser", "marketing_adviser"),
    ("📊 Market Researcher", "market_researcher"),
    ("🛒 E‑Commerce Marketer", "ecommerce_marketer"),
    ("📺 Ads", "ads"),
    ("🎨 Creative", "creative"),
    ("📰 Guest Posting", "guest_posting"),
    ("👔 Strategist", "strategist"),
    ("📱 Social", "social"),
    ("📍 GEO", "geo"),
    ("🌐 Website Audit", "audit"),
    ("✍ SEO", "seo"),
]

PLAN_SEATS = {
    "Lite": 1,
    "Basic": 1,
    "Pro": 5,
    "Enterprise": 20,
    "Unlimited": 9999,
}

PLAN_AGENT_LIMIT = {
    "Lite": 3,
    "Basic": 3,
    "Pro": 5,
    "Enterprise": len(AGENT_SPECS),
    "Unlimited": len(AGENT_SPECS),
}

# Default unlocked agents per plan (can be overridden per org during signup / by root)
PLAN_ALLOWED_AGENTS: Dict[str, List[str]] = {
    "Lite": ["analyst", "marketing_adviser", "strategist"],
    "Basic": ["analyst", "marketing_adviser", "strategist"],
    "Pro": ["analyst", "marketing_adviser", "strategist", "ads", "creative"],
    "Enterprise": list(AGENT_SPECS.keys()),
    "Unlimited": list(AGENT_SPECS.keys()),
}

DEPLOY_PROTOCOL = [
    "1) Configure mission (Brand, Location, Directives, URL if auditing).",
    "2) Your plan unlocks a fixed set of agent seats. Locked agents are grayed out.",
    "3) Select which unlocked agents to run for this mission, then click **LAUNCH OMNI‑SWARM**.",
    "4) Review outputs in each seat and refine them. Save the run to **Reports Vault** in Team Intel.",
    "5) Export to Word/PDF and deploy inside your channels (GBP/Meta/Google Ads/Email/etc).",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

# ============================================================
# THEME (Light/Dark)
# ============================================================
THEMES = {
    "Light": {
        "bg": "#f8fafc",
        "card": "rgba(255,255,255,0.92)",
        "card_border": "rgba(15,23,42,0.10)",
        "text": "#0f172a",
        "muted": "#475569",
        "accent": "#4f46e5",
        "accent_bg": "rgba(99,102,241,0.10)",
        "danger": "#ef4444",
    },
    "Dark": {
        "bg": "#0b1220",
        "card": "rgba(15,23,42,0.80)",
        "card_border": "rgba(148,163,184,0.18)",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "accent": "#a5b4fc",
        "accent_bg": "rgba(165,180,252,0.12)",
        "danger": "#fb7185",
    },
}

def _theme_name() -> str:
    return st.session_state.get("ui_theme", "Light") if st.session_state.get("ui_theme") in THEMES else "Light"

# ============================================================
# CSS / CHROME
# ============================================================
def inject_global_css():
    theme = THEMES[_theme_name()]

    hide_chrome = ""
    if PRODUCTION_MODE:
        hide_chrome = """
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header[data-testid="stHeader"] {visibility: hidden; height: 0px;}
        [data-testid="stToolbar"] {visibility: hidden;}
        """

    st.markdown(
        f"""
<style>
{hide_chrome}

/* Base */
html, body, [data-testid="stAppViewContainer"] {{
  background: {theme["bg"]} !important;
  color: {theme["text"]} !important;
}}
[data-testid="stSidebar"] > div {{
  background: {theme["bg"]} !important;
}}
/* Typography */
.ms-muted {{ color: {theme["muted"]}; font-size: 13px; }}
.ms-pill {{
  display:inline-block; padding:5px 10px; border-radius:999px;
  border: 1px solid {theme["card_border"]};
  background: {theme["accent_bg"]};
  color: {theme["text"]};
  font-size:12px;
}}
.ms-card {{
  border: 1px solid {theme["card_border"]};
  background: {theme["card"]};
  border-radius: 18px;
  box-shadow: 0 24px 60px rgba(2,6,23,0.12);
  padding: 14px 14px;
}}
.ms-banner {{
  border: 1px solid {theme["card_border"]};
  background: {theme["card"]};
  border-radius: 18px;
  box-shadow: 0 18px 44px rgba(2,6,23,0.12);
  padding: 12px 14px;
}}
.ms-danger {{
  border: 1px solid rgba(239,68,68,0.25);
  background: rgba(239,68,68,0.10);
  border-radius: 14px;
  padding: 10px 12px;
}}
/* Tabs spacing */
.stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}

/* Make text inputs readable in dark */
textarea, input {{
  color: {theme["text"]} !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )

# ============================================================
# UI WRAPPERS (Streamlit version differences)
# ============================================================
def ui_link_button(label: str, url: str):
    if hasattr(st, "link_button"):
        try:
            return st.link_button(label, url)
        except Exception:
            pass
    st.markdown(f"- [{label}]({url})")

def ui_toast(msg: str, icon: str = "✅"):
    if hasattr(st, "toast"):
        try:
            st.toast(msg, icon=icon)
            return
        except Exception:
            pass
    st.success(msg)

# ============================================================
# DB HELPERS + SCHEMA
# ============================================================
def db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def ensure_column(conn: sqlite3.Connection, table: str, col: str, col_def: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

def _json_loads_safe(s: Any, default):
    try:
        if s is None:
            return default
        if isinstance(s, (list, dict)):
            return s
        s = str(s).strip()
        if not s:
            return default
        return json.loads(s)
    except Exception:
        return default

@st.cache_resource
def init_db_once() -> None:
    conn = db_conn()
    cur = conn.cursor()

    # Orgs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orgs (
            team_id TEXT PRIMARY KEY,
            org_name TEXT,
            plan TEXT DEFAULT 'Lite',
            seats_allowed INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            allowed_agents_json TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT
        )
    """)

    # Users
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

    # Audit logs
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

    # Work artifacts
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            channel TEXT,
            status TEXT DEFAULT 'draft',
            start_date TEXT,
            end_date TEXT,
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kpi_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            event_type TEXT,
            value REAL DEFAULT 1,
            metadata_json TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)

    # Reports vault
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            mission_name TEXT,
            biz_name TEXT,
            location TEXT,
            directives TEXT,
            url TEXT,
            agents_json TEXT,
            report_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Kanban / tasks
    cur.execute("""
        CREATE TABLE IF NOT EXISTS kanban_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            title TEXT,
            description TEXT,
            stage TEXT,
            priority TEXT DEFAULT 'Medium',
            owner TEXT,
            due_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Geo catalog (dynamic cities)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS geo_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state TEXT,
            city TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Schema evolution safety
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")
    ensure_column(conn, "orgs", "allowed_agents_json", "TEXT DEFAULT ''")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")

    # Seed ROOT org + root user
    cur.execute("""
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active', ?)
    """, (json.dumps(PLAN_ALLOWED_AGENTS["Unlimited"]),))

    # IMPORTANT: bcrypt hash is stable; we do NOT randomize passwords.
    # Root credentials (default):
    # username: root  password: root123
    root_pw = stauth.Hasher.hash("root123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """, (root_pw,))

    # Seed demo org + admin (default):
    # username: admin  password: admin123
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        cur.execute("""
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
            VALUES ('ORG_001', 'TechNovance Customer', 'Lite', 1, 'active', ?)
        """, (json.dumps(PLAN_ALLOWED_AGENTS["Lite"]),))
        admin_pw = stauth.Hasher.hash("admin123")
        cur.execute("""
            INSERT OR REPLACE INTO users
            (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES ('admin','admin@customer.ai','Org Admin',?, 'admin',1,'Lite',999,1,'ORG_001')
        """, (admin_pw,))

    # seed geo catalog if empty
    cur.execute("SELECT COUNT(*) FROM geo_catalog")
    if int(cur.fetchone()[0] or 0) == 0:
        seed = [
            ("Illinois", "Chicago"), ("Illinois", "Naperville"), ("Illinois", "Plainfield"),
            ("Texas", "Dallas"), ("Texas", "Houston"), ("Texas", "Austin"),
            ("California", "Los Angeles"), ("California", "San Francisco"), ("California", "San Diego"),
            ("Florida", "Miami"), ("Florida", "Orlando"), ("Florida", "Tampa"),
            ("Arizona", "Phoenix"), ("Arizona", "Tucson"), ("Georgia", "Atlanta"),
            ("New York", "New York City"), ("Washington", "Seattle"), ("Colorado", "Denver"),
        ]
        cur.executemany("INSERT INTO geo_catalog (state, city) VALUES (?, ?)", seed)

    conn.commit()
    conn.close()

def log_audit(team_id: str, actor: str, actor_role: str, action_type: str,
              object_type: str = "", object_id: str = "", details: str = "") -> None:
    try:
        conn = db_conn()
        conn.execute("""
            INSERT INTO audit_logs (timestamp, team_id, actor, actor_role, action_type, object_type, object_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.utcnow().isoformat(), team_id, actor, actor_role, action_type, object_type, object_id, details[:2000]))
        conn.commit()
        conn.close()
    except Exception:
        pass

def normalize_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in {"viewer", "editor", "admin", "root"} else "viewer"

PERMISSIONS = {
    "viewer": {"read"},
    "editor": {"read", "campaign_write", "asset_write", "workflow_write"},
    "admin": {"read", "campaign_write", "asset_write", "workflow_write", "user_manage", "export", "credits_manage"},
    "root": {"*"},
}
def can(role: str, perm: str) -> bool:
    perms = PERMISSIONS.get(normalize_role(role), {"read"})
    return ("*" in perms) or (perm in perms) or (perm == "read")

def get_org(team_id: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM orgs WHERE team_id=?", conn, params=(team_id,))
    conn.close()
    if df.empty:
        return {"team_id": team_id, "org_name": team_id, "plan": "Lite", "seats_allowed": 1, "status": "active", "allowed_agents_json": ""}
    return df.iloc[0].to_dict()

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

def get_allowed_agents_for_org(org: Dict[str, Any]) -> List[str]:
    plan = str(org.get("plan", "Lite"))
    limit = int(PLAN_AGENT_LIMIT.get(plan, 3))
    raw = _json_loads_safe(org.get("allowed_agents_json"), [])
    # sanitize keys
    keys = [k for k in raw if k in AGENT_SPECS]
    if keys:
        return keys[:limit]
    return PLAN_ALLOWED_AGENTS.get(plan, list(AGENT_SPECS.keys()))[:limit]

def upsert_org(team_id: str, org_name: str, plan: str, allowed_agents: Optional[List[str]] = None):
    plan = (plan or "Lite").strip()
    seats = int(PLAN_SEATS.get(plan, 1))
    limit = int(PLAN_AGENT_LIMIT.get(plan, 3))
    if allowed_agents is None:
        allowed_agents = PLAN_ALLOWED_AGENTS.get(plan, [])[:limit]
    allowed_agents = [a for a in allowed_agents if a in AGENT_SPECS][:limit]
    conn = db_conn()
    conn.execute("""
        INSERT OR REPLACE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at)
        VALUES (?, ?, ?, ?, 'active', ?, COALESCE((SELECT created_at FROM orgs WHERE team_id=?), datetime('now')))
    """, (team_id, org_name, plan, seats, json.dumps(allowed_agents), team_id))
    conn.commit()
    conn.close()

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

    if not password_plain:
        return False, "Password required."

    hashed = stauth.Hasher.hash(password_plain)
    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO users (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES (?, ?, ?, ?, ?, 1, (SELECT plan FROM orgs WHERE team_id=?), 10, 1, ?)
        """, (username, email, name or username, hashed, role, team_id, team_id))
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def set_user_active(team_id: str, username: str, active: int):
    conn = db_conn()
    conn.execute("UPDATE users SET active=? WHERE username=? AND team_id=? AND role!='root'", (int(active), username, team_id))
    conn.commit()
    conn.close()

def update_user_role(team_id: str, username: str, role: str):
    role = normalize_role(role)
    if role == "root":
        return
    conn = db_conn()
    conn.execute("UPDATE users SET role=? WHERE username=? AND team_id=? AND role!='root'", (role, username, team_id))
    conn.commit()
    conn.close()

def update_user_credits(team_id: str, username: str, credits: int):
    conn = db_conn()
    conn.execute("UPDATE users SET credits=? WHERE username=? AND team_id=? AND role!='root'", (int(credits), username, team_id))
    conn.commit()
    conn.close()

def reset_user_password(team_id: str, username: str, new_pw: str):
    if not new_pw:
        return
    hashed = stauth.Hasher.hash(new_pw)
    conn = db_conn()
    conn.execute("UPDATE users SET password=? WHERE username=? AND team_id=? AND role!='root'", (hashed, username, team_id))
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

# Initialize DB once (cached)
init_db_once()

# ============================================================
# FPDF PATCH (unicode safety)
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
        text.replace("\u200b","")
            .replace("\u200c","")
            .replace("\u200d","")
            .replace("\ufeff","")
    )
    text = text.encode("ascii","ignore").decode("ascii")
    text = re.sub(r"[^\x20-\x7E\n]","", text)
    return text

def export_pdf(content: str, title: str, logo_file):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=14)

        tmp_path = None
        if logo_file is not None:
            try:
                tmp_path = "/tmp/upload_logo.png"
                with open(tmp_path, "wb") as f:
                    f.write(logo_file.getvalue())
            except Exception:
                tmp_path = None
        elif os.path.exists(APP_LOGO_PATH):
            tmp_path = APP_LOGO_PATH

        if tmp_path:
            try:
                pdf.image(tmp_path, x=10, y=10, w=28)
                pdf.set_xy(45, 12)
            except Exception:
                pdf.set_xy(10, 12)
        else:
            pdf.set_xy(10, 12)

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 7, nuclear_ascii(title), ln=True)

        pdf.set_font("Arial", size=10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        body = nuclear_ascii(content).replace("\r","")
        body = "\n".join(line[:900] for line in body.split("\n"))
        pdf.multi_cell(0, 6, body)

        return pdf.output(dest="S").encode("latin-1")
    except Exception:
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Arial", size=12)
        fallback.multi_cell(0, 10, "PDF GENERATION FAILED\n\nContent sanitized.\nError handled safely.")
        return fallback.output(dest="S").encode("latin-1")

def export_word(content: str, title: str):
    doc = Document()
    doc.add_heading(f"Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ============================================================
# AUTHENTICATION
# ============================================================
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if hasattr(st, "secrets") and name in st.secrets and st.secrets[name]:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)

def _get_cookie_secret() -> Tuple[str, str]:
    # Supports st.secrets["cookie"]["name"] and ["key"], with env fallbacks.
    try:
        cookie = st.secrets.get("cookie", {})
        name = cookie.get("name")
        key = cookie.get("key")
        if name and key:
            return str(name), str(key)
    except Exception:
        pass
    # env fallbacks
    return (
        _get_secret("COOKIE_NAME", "ms_cookie"),
        _get_secret("COOKIE_KEY", "ms_cookie_key_change_me"),
    )

def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users WHERE active=1", conn)
        return {"usernames": {r["username"]: {"email": r.get("email",""), "name": r.get("name", r["username"]), "password": r["password"]} for _, r in df.iterrows()}}
    finally:
        conn.close()

def build_authenticator() -> stauth.Authenticate:
    cookie_name, cookie_key = _get_cookie_secret()
    return stauth.Authenticate(
        get_db_creds(),
        cookie_name,
        cookie_key,
        30
    )

# Ensure we can refresh credentials when admins add users/reset passwords
if "auth_refresh_nonce" not in st.session_state:
    st.session_state["auth_refresh_nonce"] = 0

if "authenticator" not in st.session_state:
    st.session_state["authenticator"] = build_authenticator()
    st.session_state["auth_nonce_loaded"] = st.session_state["auth_refresh_nonce"]
else:
    if st.session_state.get("auth_nonce_loaded") != st.session_state.get("auth_refresh_nonce"):
        st.session_state["authenticator"] = build_authenticator()
        st.session_state["auth_nonce_loaded"] = st.session_state["auth_refresh_nonce"]

authenticator = st.session_state["authenticator"]

# ============================================================
# LOGIN PAGE
# ============================================================
def login_page():
    inject_global_css()
    theme = THEMES[_theme_name()]

    st.markdown(
        f"""
<style>
/* Hide sidebar on login */
[data-testid="stSidebar"] {{ display:none; }}
.ms-login-bg {{
  position: fixed; inset: 0;
  background:
    radial-gradient(1200px 600px at 50% 0%, rgba(99,102,241,0.20), transparent 60%),
    radial-gradient(900px 500px at 10% 30%, rgba(16,185,129,0.16), transparent 60%),
    radial-gradient(900px 500px at 90% 30%, rgba(236,72,153,0.14), transparent 60%),
    linear-gradient(180deg, {theme["bg"]} 0%, {theme["bg"]} 100%);
  z-index: -1;
}}
.ms-shell {{
  max-width: 1120px; margin: 0 auto; padding: 26px 12px 40px;
}}
.ms-grid {{
  display:grid; grid-template-columns: 1.15fr 0.85fr; gap: 16px;
}}
.ms-title {{
  font-size: 46px; font-weight: 900; letter-spacing:-0.02em; margin: 6px 0 8px; color: {theme["text"]};
}}
.ms-sub {{ color: {theme["muted"]}; font-size:14px; margin:0 0 16px; }}
.ms-badge {{
  font-size:12px; padding: 5px 10px; border-radius: 999px;
  border:1px solid {theme["card_border"]};
  background: {theme["accent_bg"]};
  color:{theme["text"]}; display:inline-block;
}}
.ms-pricing {{
  display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px;
}}
.ms-pricecard {{
  border:1px solid {theme["card_border"]};
  border-radius: 16px; padding: 12px; background: {theme["card"]};
}}
.ms-price {{ font-size: 26px; font-weight: 900; color: {theme["text"]}; }}
.ms-feat {{ color: {theme["muted"]}; font-size:13px; line-height:1.35; }}
@media (max-width: 980px){{
  .ms-grid{{ grid-template-columns: 1fr; }}
  .ms-pricing{{ grid-template-columns: 1fr; }}
  .ms-title{{ font-size:36px; }}
}}
</style>
<div class="ms-login-bg"></div>
""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="ms-shell">', unsafe_allow_html=True)

    # header centered
    cols = st.columns([1, 2, 1])
    with cols[1]:
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=80)
        st.markdown('<div class="ms-badge">AI Marketing OS • Secure • Multi‑Tenant</div>', unsafe_allow_html=True)
        st.markdown('<div class="ms-title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="ms-sub">Campaign ops, governance, analytics & executive reporting — org‑scoped.</div>', unsafe_allow_html=True)

    st.markdown('<div class="ms-grid">', unsafe_allow_html=True)

    # Left: value prop + pricing
    st.markdown('<div class="ms-card">', unsafe_allow_html=True)
    st.markdown("### What you get")
    st.markdown(
        """
- Org isolation (Team ID)
- RBAC (Admin / Editor / Viewer)
- Audit trails (logins, exports, changes)
- Reports Vault + Kanban + Campaign/Asset tools
- Executive exports (Word/PDF, logo supported)
        """
    )
    st.markdown("### Price Packages")
    st.markdown('<div class="ms-pricing">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="ms-pricecard">
  <b>🥉 LITE</b><div class="ms-price">$99/mo</div>
  <div class="ms-feat">1 seat • pick 3 agent seats<br/>Best for solo operators</div>
</div>
<div class="ms-pricecard">
  <b>🥈 PRO</b><div class="ms-price">$299/mo</div>
  <div class="ms-feat">5 seats • pick 5 agent seats<br/>Best for small teams</div>
</div>
<div class="ms-pricecard">
  <b>🥇 ENTERPRISE</b><div class="ms-price">$999/mo</div>
  <div class="ms-feat">20 seats • all agents unlocked<br/>Best for agencies</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Later enhancement: package cards can route to a dedicated landing page + checkout. For now, create your org in the **Create Org & Admin** tab.")
    st.markdown("</div>", unsafe_allow_html=True)  # pricing grid
    st.markdown("</div>", unsafe_allow_html=True)  # card

    # Right: auth tabs
    st.markdown('<div class="ms-card">', unsafe_allow_html=True)
    tabs = st.tabs(["🔑 Login", "✨ Create Org & Admin", "💳 Billing (Stripe)", "❓ Forgot Password"])

    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state["username"])
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u["username"]))
            conn.commit(); conn.close()
            log_audit(u.get("team_id",""), u["username"], normalize_role(u.get("role","viewer")), "auth.login", "user", u["username"], "login_success")
            st.rerun()

    with tabs[1]:
        st.subheader("Create Organization")
        st.caption("You choose your unlocked agent seats during signup. Locked seats remain grayed out until you upgrade.")
        with st.form("org_create_form"):
            team_id = st.text_input("Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
            org_name = st.text_input("Organization Name", placeholder="e.g., Acme Corp")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise"], index=0)

            # Pick allowed agents (locked set)
            max_agents = PLAN_AGENT_LIMIT.get(plan, 3)
            default_agents = PLAN_ALLOWED_AGENTS.get(plan, [])[:max_agents]
            allowed_agents = st.multiselect(
                f"Unlocked agent seats (pick {max_agents})",
                options=list(AGENT_SPECS.keys()),
                default=default_agents,
            )
            # enforce limit in UI: if too many, trim on submit
            admin_username = st.text_input("Org Admin Username", placeholder="e.g., acme_admin")
            admin_name = st.text_input("Admin Name", placeholder="e.g., Jane Doe")
            admin_email = st.text_input("Admin Email", placeholder="e.g., jane@acme.com")
            admin_password = st.text_input("Admin Password", type="password")

            submitted = st.form_submit_button("Create Org + Admin", use_container_width=True)

        if submitted:
            team_id = (team_id or "").strip()
            if not team_id or not org_name or not admin_username or not admin_password:
                st.error("Team ID, Org Name, Admin Username, Admin Password are required.")
            elif team_id.upper() == "ROOT":
                st.error("ROOT is reserved.")
            else:
                max_agents = PLAN_AGENT_LIMIT.get(plan, 3)
                allowed_agents = [a for a in allowed_agents if a in AGENT_SPECS][:max_agents]
                if len(allowed_agents) < max_agents and plan in {"Lite", "Pro"}:
                    st.warning(f"Selected {len(allowed_agents)}/{max_agents}. You can edit allowed agents later (Admin → Team Intel).")
                upsert_org(team_id, org_name, plan, allowed_agents=allowed_agents if allowed_agents else None)
                ok, msg = create_user(team_id, admin_username, admin_name, admin_email, admin_password, "admin")
                if ok:
                    log_audit(team_id, admin_username, "admin", "org.create", "org", team_id, f"plan={plan} allowed_agents={allowed_agents}")
                    st.session_state["auth_refresh_nonce"] += 1
                    st.success("Organization created. Use Login tab to sign in.")
                else:
                    st.error(msg)

    with tabs[2]:
        st.subheader("Stripe Billing (Scaffold)")
        st.info("Wire Stripe Checkout + webhooks to auto-upgrade plans. This tab is a placeholder for Sprint.")
        st.code("TODO: Stripe checkout session + webhook → update org plan/seats/allowed_agents_json", language="text")

    with tabs[3]:
        authenticator.forgot_password(location="main")

    st.markdown("</div>", unsafe_allow_html=True)  # card
    st.markdown("</div>", unsafe_allow_html=True)  # grid
    st.markdown("</div>", unsafe_allow_html=True)  # shell

    st.stop()

# ============================================================
# POST-AUTH CONTEXT
# ============================================================
def require_login():
    if not st.session_state.get("authentication_status"):
        login_page()

require_login()

me = get_user(st.session_state["username"])
my_team = me.get("team_id", "ORG_001")
my_role = normalize_role(me.get("role", "viewer"))
is_root = (my_role == "root") or (my_team == "ROOT")

org = get_org(my_team)
org_plan = str(org.get("plan", "Lite"))
allowed_agents = get_allowed_agents_for_org(org) if not is_root else list(AGENT_SPECS.keys())

# ============================================================
# SWARM RUNTIME STATE
# ============================================================
def _reset_swarm_state():
    st.session_state["report"] = {}
    st.session_state["gen"] = False
    st.session_state["swarm_running"] = False
    st.session_state["swarm_paused"] = False
    st.session_state["swarm_queue"] = []
    st.session_state["swarm_completed"] = []
    st.session_state["swarm_current"] = ""
    st.session_state["swarm_last_error"] = ""
    st.session_state["swarm_run_id"] = ""
    st.session_state["swarm_next_due"] = 0.0
    st.session_state["swarm_step_index"] = 0
    st.session_state["swarm_autorun"] = st.session_state.get("swarm_autorun", True)
    st.session_state["swarm_autorun_delay"] = st.session_state.get("swarm_autorun_delay", 3)

def _ensure_swarm_defaults():
    for k, v in {
        "report": {},
        "gen": False,
        "swarm_running": False,
        "swarm_paused": False,
        "swarm_queue": [],
        "swarm_completed": [],
        "swarm_current": "",
        "swarm_last_error": "",
        "swarm_run_id": "",
        "swarm_next_due": 0.0,
        "swarm_step_index": 0,
        "swarm_autorun": True,
        "swarm_autorun_delay": 3,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

_ensure_swarm_defaults()

def _compose_full_report(ctx: Dict[str, Any], report: Dict[str, str]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        f"# {ctx.get('biz_name','')} Intelligence Report\n"
        f"**Date:** {now} | **Location:** {ctx.get('city','')} | **Plan:** {ctx.get('package','')}\n"
        f"---\n\n"
    )
    blocks = []
    section_map = [
        ("## 🕵️ Market Analysis", "analyst"),
        ("## 🧭 Marketing Adviser", "marketing_adviser"),
        ("## 📊 Market Research", "market_researcher"),
        ("## 🛒 E‑Commerce Marketing", "ecommerce_marketer"),
        ("## 🌐 Website Audit", "audit"),
        ("## 👔 Executive Strategy", "strategist"),
        ("## 📺 Ads Output", "ads"),
        ("## 🎨 Creative Pack", "creative"),
        ("## 📰 Guest Posting", "guest_posting"),
        ("## ✍️ SEO", "seo"),
        ("## 📍 GEO", "geo"),
        ("## 📱 Social Roadmap", "social"),
    ]
    for title, key in section_map:
        val = (report.get(key) or "").strip()
        if not val:
            continue
        blocks.append(f"{title}\n{val}\n")
    return header + "\n".join(blocks)

def _agent_display_name(agent_key: str) -> str:
    for label, key in AGENT_ORDER:
        if key == agent_key:
            return label
    return agent_key

def safe_run_one(payload: Dict[str, Any], agent_key: str) -> str:
    try:
        res = run_marketing_swarm({**payload, "active_swarm": [agent_key]}) or {}
        # main.py returns agent_key and full_report; we take agent_key
        txt = str(res.get(agent_key, "") or "").strip()
        if not txt:
            # Try to surface something helpful
            txt = "No output returned. Check API keys, rate limits, and agent configuration."
        return txt
    except Exception as e:
        msg = str(e)
        st.session_state["swarm_last_error"] = msg
        log_audit(my_team, me.get("username",""), my_role, "swarm.error", "agent", agent_key, msg)
        return f"ERROR running {agent_key}: {msg}"

def start_swarm_run(selected_agents: List[str], ctx: Dict[str, Any]):
    _reset_swarm_state()
    st.session_state["swarm_running"] = True
    st.session_state["swarm_queue"] = list(selected_agents)
    st.session_state["swarm_completed"] = []
    st.session_state["swarm_run_id"] = f"run_{int(time.time())}"
    st.session_state["swarm_next_due"] = time.time()
    st.session_state["swarm_step_index"] = 0
    st.session_state["swarm_current"] = ""
    st.session_state["swarm_last_error"] = ""
    st.session_state["swarm_ctx"] = ctx
    st.session_state["gen"] = True  # show seats immediately (even if some pending)

def stop_swarm_run():
    st.session_state["swarm_running"] = False
    st.session_state["swarm_paused"] = False
    st.session_state["swarm_queue"] = []
    st.session_state["swarm_current"] = ""
    st.session_state["swarm_next_due"] = 0.0

def pause_swarm():
    st.session_state["swarm_paused"] = True

def resume_swarm():
    st.session_state["swarm_paused"] = False
    # schedule next step immediately
    st.session_state["swarm_next_due"] = time.time()

def run_next_agent_step():
    if not st.session_state.get("swarm_running"):
        return
    if st.session_state.get("swarm_paused"):
        return
    queue = st.session_state.get("swarm_queue", [])
    if not queue:
        return

    agent_key = queue.pop(0)
    st.session_state["swarm_current"] = agent_key
    st.session_state["swarm_step_index"] = int(st.session_state.get("swarm_step_index", 0)) + 1

    payload = st.session_state.get("swarm_ctx", {})
    with st.spinner(f"Running {_agent_display_name(agent_key)}…"):
        txt = safe_run_one(payload, agent_key)

    st.session_state.setdefault("report", {})
    st.session_state["report"][agent_key] = txt
    st.session_state["report"]["full_report"] = _compose_full_report(payload, st.session_state["report"])
    st.session_state.setdefault("swarm_completed", []).append(agent_key)

    # schedule next due
    delay = int(st.session_state.get("swarm_autorun_delay", 3) or 3)
    st.session_state["swarm_next_due"] = time.time() + max(1, delay)

    # finish?
    if not st.session_state.get("swarm_queue"):
        st.session_state["swarm_running"] = False
        st.session_state["swarm_current"] = ""
        st.session_state["swarm_next_due"] = 0.0
        ui_toast("Swarm complete — reports are ready.", icon="✅")
        log_audit(my_team, me.get("username",""), my_role, "swarm.complete", "swarm", payload.get("biz_name",""), f"agents={st.session_state.get('swarm_completed',[])}")

# ============================================================
# AUTO-RERUN SCHEDULER (for auto-run)
# ============================================================
def schedule_autorun_rerun(seconds: int, key: str):
    seconds = int(max(1, seconds))
    # Streamlit may have st.autorefresh (newer). If not, use a tiny JS reload.
    if hasattr(st, "autorefresh"):
        try:
            st.autorefresh(interval=seconds * 1000, key=key)
            return
        except Exception:
            pass
    # Fallback: JS reload. This may open a new session in some environments,
    # but usually keeps the same session in Streamlit Cloud.
    try:
        import streamlit.components.v1 as components
        components.html(
            f"<script>setTimeout(()=>{{window.location.reload();}}, {seconds*1000});</script>",
            height=0,
        )
    except Exception:
        pass

# ============================================================
# SIDEBAR (Mission config + agents + run controls)
# ============================================================
def load_geo_catalog() -> Dict[str, List[str]]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT state, city FROM geo_catalog ORDER BY state, city", conn)
    conn.close()
    geo: Dict[str, List[str]] = {}
    for _, r in df.iterrows():
        st_name = str(r["state"])
        city = str(r["city"])
        geo.setdefault(st_name, [])
        if city not in geo[st_name]:
            geo[st_name].append(city)
    # fallback if empty
    if not geo:
        geo = {"Illinois": ["Chicago", "Naperville", "Plainfield"]}
    return geo

def render_sidebar() -> Dict[str, Any]:
    inject_global_css()

    with st.sidebar:
        # Theme toggle
        st.caption("Appearance")
        theme_choice = st.radio("Theme", ["Light", "Dark"], horizontal=True, key="ui_theme", index=0 if _theme_name()=="Light" else 1)
        st.divider()

        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=110)

        st.subheader(org.get("org_name", "Organization"))
        st.caption(f"Team: `{my_team}` • Role: **{my_role.upper()}**")
        st.metric("Plan", org_plan)
        st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")

        # Show locked seats summary (for customers)
        if not is_root:
            st.markdown("**Unlocked agent seats (fixed):**")
            st.write(", ".join([k.replace("_", " ").title() for k in allowed_agents]) if allowed_agents else "—")

        st.divider()

        biz_name = st.text_input("🏢 Brand Name", value=st.session_state.get("biz_name", ""))
        st.session_state["biz_name"] = biz_name

        custom_logo = st.file_uploader("📤 Brand Logo (all plans)", type=["png", "jpg", "jpeg"])

        # Location
        geo = load_geo_catalog()
        states = sorted(list(geo.keys()))
        selected_state = st.selectbox("🎯 Target State", states, index=min(0, len(states)-1))
        city_list = sorted(geo.get(selected_state, [])) or ["(Add city in Team Intel → Tools)"]
        selected_city = st.selectbox("🏙️ Target City", city_list)
        # optional override
        if selected_city.startswith("(Add city"):
            selected_city = st.text_input("City (custom)", value="")
        full_loc = f"{selected_city}, {selected_state}" if selected_city else selected_state

        st.divider()
        website_url = st.text_input("🌐 Business Website URL (required for Website Audit)", value=st.session_state.get("website_url", ""), placeholder="https://example.com")
        st.session_state["website_url"] = website_url

        directives = st.text_area("✍️ Strategic Directives", value=st.session_state.get("directives", ""), height=110)
        st.session_state["directives"] = directives

        st.divider()
        st.markdown("### 🤖 Swarm Personnel")
        st.caption("Select which unlocked agents to run for this mission.")

        toggles: Dict[str, bool] = {}
        for label, key in AGENT_ORDER:
            unlocked = (key in allowed_agents) or is_root
            disabled = (not unlocked)
            # Use a stable widget key that won't collide
            toggles[key] = st.toggle(label, value=bool(st.session_state.get(f"tg_{key}", False)), key=f"tg_{key}", disabled=disabled)
            if not unlocked:
                st.caption(f"🔒 Locked by plan: {key}")

        selected_agents = [k for k, v in toggles.items() if v and ((k in allowed_agents) or is_root)]

        st.divider()
        st.markdown("### ▶️ Run Controls")

        st.checkbox("Auto-run remaining agents", value=bool(st.session_state.get("swarm_autorun", True)), key="swarm_autorun")
        st.selectbox("Auto-run delay", options=[1, 3, 5], index=[1,3,5].index(int(st.session_state.get("swarm_autorun_delay", 3))), key="swarm_autorun_delay")

        run_btn = st.button("🚀 LAUNCH OMNI‑SWARM", type="primary", use_container_width=True, key="btn_launch")

        # Pause/Resume/Stop (works between agents)
        if st.session_state.get("swarm_running"):
            c1, c2 = st.columns(2)
            with c1:
                if st.button("⏸ Pause", use_container_width=True, key="btn_pause"):
                    pause_swarm()
                    log_audit(my_team, me.get("username",""), my_role, "swarm.pause", "swarm", st.session_state.get("biz_name",""), "")
                    st.rerun()
            with c2:
                if st.button("⏵ Resume", use_container_width=True, key="btn_resume"):
                    resume_swarm()
                    log_audit(my_team, me.get("username",""), my_role, "swarm.resume", "swarm", st.session_state.get("biz_name",""), "")
                    st.rerun()

            if st.button("🛑 Stop run", use_container_width=True, key="btn_stop", help="Stops after the current agent. Completed outputs remain."):
                stop_swarm_run()
                log_audit(my_team, me.get("username",""), my_role, "swarm.stop", "swarm", st.session_state.get("biz_name",""), "")
                st.rerun()

        authenticator.logout("🔒 Sign Out", "sidebar")

    return {
        "biz_name": biz_name,
        "custom_logo": custom_logo,
        "city": full_loc,
        "directives": directives,
        "url": website_url,
        "selected_agents": selected_agents,
        "run_btn": run_btn,
    }

sidebar_ctx = render_sidebar()

# ============================================================
# START / ADVANCE SWARM
# ============================================================
if sidebar_ctx["run_btn"]:
    agents = sidebar_ctx["selected_agents"]
    if not sidebar_ctx["biz_name"]:
        st.error("Enter Brand Name first.")
    elif not agents:
        st.warning("Select at least one unlocked agent.")
    elif ("audit" in agents) and (not (sidebar_ctx.get("url") or "").strip()):
        st.error("Website Audit is selected — please provide a Business Website URL in the sidebar.")
    else:
        # payload/context shared for all agents
        ctx = {
            "city": sidebar_ctx["city"],
            "biz_name": sidebar_ctx["biz_name"],
            "package": org_plan,
            "custom_logo": sidebar_ctx["custom_logo"],
            "directives": sidebar_ctx["directives"],
            "url": sidebar_ctx.get("url", ""),
        }
        start_swarm_run(agents, ctx)
        log_audit(my_team, me.get("username",""), my_role, "swarm.start", "swarm", sidebar_ctx["biz_name"], f"agents={agents}")
        st.rerun()

# Auto-run tick
if st.session_state.get("swarm_running") and st.session_state.get("swarm_autorun") and (not st.session_state.get("swarm_paused")):
    # If due, run one step now
    if time.time() >= float(st.session_state.get("swarm_next_due", 0.0) or 0.0):
        run_next_agent_step()
        # After step, rerun to update UI immediately
        st.rerun()
    else:
        # Schedule a rerun so next step happens automatically (user can still browse)
        seconds_left = max(1, int(st.session_state.get("swarm_next_due", time.time()) - time.time()))
        schedule_autorun_rerun(min(seconds_left, int(st.session_state.get("swarm_autorun_delay", 3) or 3)), key=f"autorun_{st.session_state.get('swarm_run_id','')}")

# ============================================================
# TOP BANNER (progress + manual next step)
# ============================================================
def render_swarm_banner():
    if not st.session_state.get("gen"):
        return

    running = bool(st.session_state.get("swarm_running"))
    paused = bool(st.session_state.get("swarm_paused"))
    queue: List[str] = st.session_state.get("swarm_queue", [])
    done: List[str] = st.session_state.get("swarm_completed", [])
    current = st.session_state.get("swarm_current", "")
    total = len(done) + len(queue)
    completed_n = len(done)

    with st.container():
        st.markdown('<div class="ms-banner">', unsafe_allow_html=True)

        left, right = st.columns([0.72, 0.28])
        with left:
            status = "RUNNING" if running else "READY"
            if paused and running:
                status = "PAUSED"
            st.markdown(f'<span class="ms-pill">Swarm: {status}</span>', unsafe_allow_html=True)
            st.write(f"**Mission:** {st.session_state.get('biz_name','')} • **Location:** {st.session_state.get('swarm_ctx',{}).get('city','')}")
            if total > 0:
                st.progress(completed_n / max(1, total))
                st.caption(f"Completed {completed_n}/{total}. Current: {current or '—'}")
            if st.session_state.get("swarm_last_error"):
                st.markdown(f'<div class="ms-danger"><b>Error:</b> {st.session_state["swarm_last_error"]}</div>', unsafe_allow_html=True)

        with right:
            if running:
                # Manual next step button (unique key)
                key = f"run_next_now_{st.session_state.get('swarm_run_id','')}_{st.session_state.get('swarm_step_index',0)}"
                if st.button("▶️ Run next agent now", key=key, use_container_width=True, disabled=paused or (len(queue)==0)):
                    run_next_agent_step()
                    st.rerun()

                # show next in queue
                if queue:
                    st.caption(f"Next: {_agent_display_name(queue[0])}")
                else:
                    st.caption("Next: —")
            else:
                st.caption("You can switch tabs while reports are generating. The banner stays here.")
                if st.button("💾 Save current run to Reports Vault", use_container_width=True, key="save_run_top"):
                    save_current_run_to_vault()
                    st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# REPORT VAULT SAVE (used in banner + Team Intel)
# ============================================================
def save_current_run_to_vault():
    ctx = st.session_state.get("swarm_ctx") or {}
    report = st.session_state.get("report") or {}
    agents = st.session_state.get("swarm_completed") or []
    if not report:
        st.warning("No report to save yet.")
        return

    mission = ctx.get("biz_name") or st.session_state.get("biz_name") or "Mission"
    conn = db_conn()
    conn.execute("""
        INSERT INTO reports (team_id, mission_name, biz_name, location, directives, url, agents_json, report_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        my_team,
        mission,
        ctx.get("biz_name",""),
        ctx.get("city",""),
        ctx.get("directives",""),
        ctx.get("url",""),
        json.dumps(agents),
        json.dumps(report),
    ))
    conn.commit()
    conn.close()
    log_audit(my_team, me.get("username",""), my_role, "report.save", "report", mission, f"agents={agents}")
    ui_toast("Saved to Reports Vault.", icon="💾")

# Render banner above tabs
render_swarm_banner()

# ============================================================
# RENDERERS
# ============================================================
IMPLEMENT_GUIDES: Dict[str, List[str]] = {
    "analyst": [
        "Pick 1–2 highest-value offers + differentiate pricing/positioning.",
        "Turn the competitor gaps into a landing page section + ad hooks.",
        "Convert quick wins into a 7‑day sprint checklist.",
    ],
    "marketing_adviser": [
        "Use the messaging pillars in your homepage hero + ad headlines.",
        "Follow the channel priority list for your next 30 days.",
        "Copy the CTA language into GBP/Meta/website buttons.",
    ],
    "market_researcher": [
        "Validate assumptions with 5–10 customer calls or surveys.",
        "Use the segment insights to tailor ad creatives per audience.",
        "Update pricing based on willingness-to-pay signals.",
    ],
    "ecommerce_marketer": [
        "Implement the recommended funnel steps (product page → checkout → post‑purchase).",
        "Set up email/SMS flows (welcome, abandoned cart, post‑purchase upsell).",
        "Use bundling + upsells suggested to improve AOV.",
    ],
    "ads": [
        "Paste Google Search tables into your Ads account (headlines/descriptions).",
        "Use Meta hooks as first-line copy; rotate 3 creatives per ad set.",
        "Track conversions (calls/forms/purchases) and cut weak ads weekly.",
    ],
    "creative": [
        "Use the concept names as creative themes for the next month.",
        "Generate images using the prompt pack (Runway/MJ/Canva) and ship variants.",
        "Match variants to audiences (cold vs warm) and test 2–3 CTAs.",
    ],
    "guest_posting": [
        "Start with the top 20 targets; personalize outreach using the pitch templates.",
        "Publish 2–4 placements/month; link to your main service page + GBP.",
        "Track replies and placements in the Kanban board.",
    ],
    "strategist": [
        "Turn the weekly plan into tasks in Team Intel → Kanban.",
        "Use KPIs as your reporting dashboard and update weekly.",
        "Schedule 1 optimization block per week for ads/SEO/GBP.",
    ],
    "social": [
        "Load the calendar into a scheduler; batch-create 7 posts at once.",
        "Use 3 recurring content pillars (education, proof, offer).",
        "Repurpose best posts into ads once engagement is proven.",
    ],
    "geo": [
        "Update GBP categories, services, and posts exactly as recommended.",
        "Create/clean citations for NAP consistency; monitor for duplicates.",
        "Add location pages with near‑me keywords and internal links.",
    ],
    "audit": [
        "Fix top 3 conversion blockers first (mobile, speed, trust, CTA).",
        "Add friction reducers (sticky CTA, FAQs, testimonials).",
        "Re-run audit after changes and compare conversion metrics.",
    ],
    "seo": [
        "Publish the authority article and interlink to service pages.",
        "Create supporting cluster posts (2/week) and link back to the pillar.",
        "Build local links via partnerships + guest posts.",
    ],
}

def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: **{st.session_state.get('biz_name','Global Mission')}**")
    st.subheader("Agent Specializations")
    for _, key in AGENT_ORDER:
        st.markdown(AGENT_SPECS.get(key, ""))
    st.markdown("---")
    st.subheader("🛡️ Swarm Execution Protocol")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")
    st.markdown("---")
    st.subheader("How to deploy results (quick playbook)")
    st.markdown(
        """
- **Choose 1 offer** and build a landing page section for it.
- Use **Ads + Creative** outputs to launch 1 Search campaign + 1 Meta campaign.
- Use **SEO + GEO** outputs to strengthen local ranking (GBP + citations + content).
- Track progress in **Team Intel**: Kanban + Reports Vault + KPI events.
        """
    )

def render_agent_seat(title: str, key: str, custom_logo):
    unlocked = (key in allowed_agents) or is_root
    st.subheader(f"{title} Seat")
    st.caption(AGENT_SPECS.get(key, ""))

    if not unlocked:
        st.info("🔒 This agent seat is locked by your plan. Upgrade to unlock.")
        return

    report = st.session_state.get("report") or {}
    value = report.get(key, "")

    if st.session_state.get("gen") and value:
        edited = st.text_area("Refine Intel", value=str(value), height=420, key=f"ed_{key}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("📄 Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
        with c2:
            st.download_button("📕 PDF", export_pdf(edited, title, custom_logo), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)
        with c3:
            if st.button("💾 Save run", key=f"save_{key}", use_container_width=True):
                save_current_run_to_vault()
                st.rerun()

        with st.expander("✅ How to implement this report", expanded=False):
            steps = IMPLEMENT_GUIDES.get(key, [])
            if steps:
                for s in steps:
                    st.markdown(f"- {s}")
            else:
                st.write("Deploy the recommendations as a 7–30 day plan and measure outcomes weekly.")

        if key in {"ads", "creative", "social"}:
            st.markdown("---")
            st.markdown("#### 📣 Publish / Push")
            st.text_area("Copy-ready content", value=edited, height=140, key=f"push_{key}")
            cols = st.columns(4)
            for i, (nm, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
                with cols[i % 4]:
                    ui_link_button(nm, url)

    else:
        if st.session_state.get("swarm_running") and (key in (st.session_state.get("swarm_queue") or []) or key == st.session_state.get("swarm_current")):
            st.info("⏳ This agent is queued or running. Check the progress banner at the top.")
        else:
            st.info("No report yet for this seat. Select it in the sidebar and run the Swarm.")

def render_vision():
    st.header("👁️ Vision")
    st.caption("Reserved for future photo/asset analysis workflows.")
    st.info("Vision module is enabled, but no vision pipeline is wired yet.")

def render_veo():
    st.header("🎬 Veo Studio")
    st.caption("Reserved for future video generation workflows.")
    st.info("Veo Studio module is enabled, but no video pipeline is wired yet.")

# ============================================================
# TEAM INTEL (Org-scoped)
# ============================================================
def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Org dashboard: Users, Reports Vault, Kanban, Campaigns, Assets, Workflows, Integrations, Logs.")

    users_n = active_user_count(my_team)
    seats = seats_allowed_for_team(my_team)
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Users", users_n)
    c2.metric("Seats Allowed", seats)
    c3.metric("Plan", org_plan)

    tabs = st.tabs([
        "📚 Reports Vault",
        "✅ Kanban",
        "👥 User & Access",
        "📣 Campaigns",
        "🧩 Assets",
        "⚙️ Workflows",
        "🔌 Integrations",
        "📈 Analytics",
        "🔐 Logs",
        "🗺️ Tools",
    ])

    # ---- Reports Vault ----
    with tabs[0]:
        st.subheader("Reports Vault")
        st.caption("Saved Swarm runs for your org. Use this as your client deliverable archive.")
        if st.button("💾 Save current run", use_container_width=True, key="save_current_run_vault"):
            save_current_run_to_vault()
            st.rerun()

        conn = db_conn()
        df = pd.read_sql_query(
            "SELECT id, mission_name, biz_name, location, created_at, agents_json FROM reports WHERE team_id=? ORDER BY id DESC LIMIT 200",
            conn, params=(my_team,)
        )
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        rid = st.number_input("Open report ID", min_value=0, step=1, value=0)
        if rid:
            conn = db_conn()
            rep = pd.read_sql_query("SELECT * FROM reports WHERE team_id=? AND id=?", conn, params=(my_team, int(rid)))
            conn.close()
            if rep.empty:
                st.warning("Report not found.")
            else:
                row = rep.iloc[0].to_dict()
                report_json = _json_loads_safe(row.get("report_json"), {})
                st.markdown("---")
                st.subheader(f"Report #{row['id']} — {row.get('mission_name','')}")
                st.caption(f"Created: {row.get('created_at','')} • Agents: {', '.join(_json_loads_safe(row.get('agents_json'), []))}")
                full = report_json.get("full_report", "")
                st.text_area("Full Report", value=full or "", height=360, key=f"vault_full_{rid}")
                c1, c2 = st.columns(2)
                with c1:
                    st.download_button("📄 Word (Full)", export_word(full, f"{row.get('mission_name','Report')}"), file_name=f"report_{rid}.docx", use_container_width=True, key=f"vault_word_{rid}")
                with c2:
                    st.download_button("📕 PDF (Full)", export_pdf(full, f"{row.get('mission_name','Report')}", None), file_name=f"report_{rid}.pdf", use_container_width=True, key=f"vault_pdf_{rid}")

    # ---- Kanban ----
    with tabs[1]:
        st.subheader("Kanban Board")
        st.caption("Turn agent recommendations into executable tasks.")
        stages = ["Backlog", "In Progress", "Blocked", "Done"]
        cols = st.columns(4)

        # Create card
        with st.expander("➕ Add Kanban card", expanded=False):
            with st.form("kanban_add"):
                title = st.text_input("Title")
                desc = st.text_area("Description")
                stage = st.selectbox("Stage", stages, index=0)
                priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
                owner = st.text_input("Owner")
                due = st.text_input("Due date (optional)", placeholder="YYYY-MM-DD")
                sub = st.form_submit_button("Add card", use_container_width=True)
            if sub:
                conn = db_conn()
                conn.execute("""
                    INSERT INTO kanban_cards (team_id, title, description, stage, priority, owner, due_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (my_team, title, desc, stage, priority, owner, due))
                conn.commit(); conn.close()
                log_audit(my_team, me.get("username",""), my_role, "kanban.create", "kanban", title, stage)
                st.success("Card added.")
                st.rerun()

        conn = db_conn()
        cards = pd.read_sql_query("SELECT * FROM kanban_cards WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()

        for i, stage in enumerate(stages):
            with cols[i]:
                st.markdown(f"### {stage}")
                subdf = cards[cards["stage"] == stage] if not cards.empty else pd.DataFrame()
                if subdf.empty:
                    st.caption("—")
                else:
                    for _, row in subdf.iterrows():
                        cid = int(row["id"])
                        with st.container(border=True):
                            st.markdown(f"**{row['title']}**")
                            st.caption(f"Priority: {row.get('priority','')} • Owner: {row.get('owner','') or '—'} • Due: {row.get('due_date','') or '—'}")
                            if str(row.get("description","")).strip():
                                st.write(str(row["description"])[:240] + ("…" if len(str(row["description"])) > 240 else ""))
                            new_stage = st.selectbox("Move to", stages, index=stages.index(stage), key=f"mv_{cid}")
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("Update", key=f"upd_{cid}", use_container_width=True):
                                    conn = db_conn()
                                    conn.execute("UPDATE kanban_cards SET stage=? WHERE id=? AND team_id=?", (new_stage, cid, my_team))
                                    conn.commit(); conn.close()
                                    log_audit(my_team, me.get("username",""), my_role, "kanban.move", "kanban", str(cid), f"{stage}->{new_stage}")
                                    st.rerun()
                            with c2:
                                if st.button("Delete", key=f"del_{cid}", use_container_width=True):
                                    conn = db_conn()
                                    conn.execute("DELETE FROM kanban_cards WHERE id=? AND team_id=?", (cid, my_team))
                                    conn.commit(); conn.close()
                                    log_audit(my_team, me.get("username",""), my_role, "kanban.delete", "kanban", str(cid), row.get("title",""))
                                    st.rerun()

    # ---- User & Access ----
    with tabs[2]:
        st.subheader("User & Access (RBAC)")
        conn = db_conn()
        udf = pd.read_sql_query(
            "SELECT username,name,email,role,active,credits,last_login_at,created_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC",
            conn, params=(my_team,)
        )
        conn.close()
        st.dataframe(udf, width="stretch", hide_index=True)

        if can(my_role, "user_manage") or is_root:
            st.markdown("### ➕ Add user")
            with st.form("add_user"):
                u = st.text_input("Username")
                n = st.text_input("Name")
                e = st.text_input("Email")
                r = st.selectbox("Role", ["viewer", "editor", "admin"])
                pw = st.text_input("Temp Password", type="password")
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                ok, msg = create_user(my_team, u, n, e, pw, r)
                if ok:
                    log_audit(my_team, me.get("username",""), my_role, "user.create", "user", u, f"role={r}")
                    st.session_state["auth_refresh_nonce"] += 1
                    st.success(msg); st.rerun()
                else:
                    st.error(msg)

            st.markdown("### ⚙️ Manage user")
            sel_user = st.selectbox("Select user", options=list(udf["username"]) if not udf.empty else [])
            if sel_user:
                row = udf[udf["username"] == sel_user].iloc[0].to_dict()
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_role = st.selectbox("Role", ["viewer","editor","admin"], index=["viewer","editor","admin"].index(row["role"]), key="um_role")
                with c2:
                    new_active = st.selectbox("Active", [1,0], index=0 if int(row["active"])==1 else 1, key="um_active")
                with c3:
                    new_credits = st.number_input("Credits", min_value=0, value=int(row.get("credits") or 0), step=1, key="um_credits")

                new_pw = st.text_input("Reset password (optional)", type="password", key="um_pw")
                if st.button("Apply changes", use_container_width=True, key="um_apply"):
                    update_user_role(my_team, sel_user, new_role)
                    set_user_active(my_team, sel_user, int(new_active))
                    if can(my_role, "credits_manage") or is_root:
                        update_user_credits(my_team, sel_user, int(new_credits))
                    if new_pw.strip():
                        reset_user_password(my_team, sel_user, new_pw.strip())
                        st.session_state["auth_refresh_nonce"] += 1
                    log_audit(my_team, me.get("username",""), my_role, "user.update", "user", sel_user, f"role={new_role} active={new_active} credits={new_credits}")
                    st.success("Updated.")
                    st.rerun()

            st.markdown("### 📥 Bulk import (CSV)")
            st.caption("Headers: username,name,email,role,password • seat limits enforced")
            up = st.file_uploader("Upload CSV", type=["csv"], key="bulk_csv")
            if up and st.button("Import", use_container_width=True, key="bulk_import"):
                created, errs = bulk_import_users(my_team, up.getvalue())
                log_audit(my_team, me.get("username",""), my_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                st.session_state["auth_refresh_nonce"] += 1
                if created:
                    st.success(f"Imported {created} user(s).")
                if errs:
                    st.error("Issues:")
                    for x in errs[:20]:
                        st.write(f"- {x}")
                st.rerun()
        else:
            st.info("Only Admin can manage users.")

    # ---- Campaigns ----
    with tabs[3]:
        st.subheader("Campaigns")
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,channel,status,start_date,end_date,created_at FROM campaigns WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        if can(my_role, "campaign_write") or is_root:
            with st.expander("➕ Add campaign", expanded=False):
                with st.form("camp_add"):
                    nm = st.text_input("Campaign name")
                    ch = st.text_input("Channel", placeholder="Google Ads / Meta / Email / SEO")
                    stt = st.selectbox("Status", ["draft","live","paused","done"], index=0)
                    sd = st.text_input("Start date", placeholder="YYYY-MM-DD")
                    ed = st.text_input("End date", placeholder="YYYY-MM-DD")
                    notes = st.text_area("Notes")
                    sub = st.form_submit_button("Create campaign", use_container_width=True)
                if sub:
                    conn = db_conn()
                    conn.execute("""
                        INSERT INTO campaigns (team_id,name,channel,status,start_date,end_date,notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (my_team, nm, ch, stt, sd, ed, notes))
                    conn.commit(); conn.close()
                    log_audit(my_team, me.get("username",""), my_role, "campaign.create", "campaign", nm, ch)
                    st.success("Created.")
                    st.rerun()

    # ---- Assets ----
    with tabs[4]:
        st.subheader("Assets")
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,asset_type,created_at FROM assets WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        if can(my_role, "asset_write") or is_root:
            with st.expander("➕ Add asset", expanded=False):
                with st.form("asset_add"):
                    nm = st.text_input("Asset name")
                    tp = st.selectbox("Asset type", ["copy", "prompt_pack", "creative_brief", "landing_page", "other"], index=0)
                    content = st.text_area("Content")
                    sub = st.form_submit_button("Save asset", use_container_width=True)
                if sub:
                    conn = db_conn()
                    conn.execute("INSERT INTO assets (team_id,name,asset_type,content) VALUES (?,?,?,?)", (my_team, nm, tp, content))
                    conn.commit(); conn.close()
                    log_audit(my_team, me.get("username",""), my_role, "asset.create", "asset", nm, tp)
                    st.success("Saved.")
                    st.rerun()

    # ---- Workflows ----
    with tabs[5]:
        st.subheader("Workflows (Automation)")
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,enabled,trigger,created_at FROM workflows WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        if can(my_role, "workflow_write") or is_root:
            with st.expander("➕ Add workflow", expanded=False):
                with st.form("wf_add"):
                    nm = st.text_input("Workflow name")
                    trig = st.text_input("Trigger", placeholder="e.g., weekly_report, new_lead")
                    steps = st.text_area("Steps (JSON or bullets)")
                    enabled = st.checkbox("Enabled", value=False)
                    sub = st.form_submit_button("Create workflow", use_container_width=True)
                if sub:
                    conn = db_conn()
                    conn.execute("INSERT INTO workflows (team_id,name,enabled,trigger,steps) VALUES (?,?,?,?,?)", (my_team, nm, int(enabled), trig, steps))
                    conn.commit(); conn.close()
                    log_audit(my_team, me.get("username",""), my_role, "workflow.create", "workflow", nm, trig)
                    st.success("Created.")
                    st.rerun()

    # ---- Integrations ----
    with tabs[6]:
        st.subheader("Integrations")
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,enabled,created_at FROM integrations WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)
        with st.expander("➕ Add integration (placeholder)", expanded=False):
            st.info("Integrations are scaffolding for future sprints (Google Ads, Meta, CRM, etc).")

    # ---- Analytics ----
    with tabs[7]:
        st.subheader("Analytics (KPI Events)")
        conn = db_conn()
        df = pd.read_sql_query("SELECT event_type, COUNT(*) as n, SUM(value) as total FROM kpi_events WHERE team_id=? GROUP BY event_type ORDER BY n DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)
        with st.expander("➕ Log KPI event", expanded=False):
            with st.form("kpi_add"):
                et = st.text_input("Event type", placeholder="lead, call, booking, purchase")
                val = st.number_input("Value", value=1.0, step=1.0)
                meta = st.text_area("Metadata (JSON)", value="{}")
                sub = st.form_submit_button("Log event", use_container_width=True)
            if sub:
                conn = db_conn()
                conn.execute("INSERT INTO kpi_events (team_id,event_type,value,metadata_json) VALUES (?,?,?,?)", (my_team, et, float(val), meta))
                conn.commit(); conn.close()
                log_audit(my_team, me.get("username",""), my_role, "kpi.log", "kpi", et, str(val))
                st.success("Logged.")
                st.rerun()

    # ---- Logs ----
    with tabs[8]:
        st.subheader("Audit Logs")
        conn = db_conn()
        logs = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 250",
            conn, params=(my_team,)
        )
        conn.close()
        st.dataframe(logs, width="stretch", hide_index=True)

    # ---- Tools (geo + plan agent locks) ----
    with tabs[9]:
        st.subheader("Tools")
        st.markdown("### 🗺️ Geo Catalog")
        with st.expander("Add a city", expanded=False):
            with st.form("geo_add"):
                stt = st.text_input("State")
                city = st.text_input("City")
                sub = st.form_submit_button("Add", use_container_width=True)
            if sub and stt and city:
                conn = db_conn()
                conn.execute("INSERT INTO geo_catalog (state, city) VALUES (?, ?)", (stt.strip(), city.strip()))
                conn.commit(); conn.close()
                st.success("Added. Reload sidebar to see it.")
                st.rerun()

        if can(my_role, "user_manage") or is_root:
            st.markdown("---")
            st.markdown("### 🤖 Agent Seat Locks")
            st.caption("This controls which agents are unlocked for your org. Locked agents are grayed out.")
            current_allowed = get_allowed_agents_for_org(org) if not is_root else list(AGENT_SPECS.keys())
            st.write("Current unlocked:", ", ".join(current_allowed))
            plan = org_plan
            limit = PLAN_AGENT_LIMIT.get(plan, 3)
            new_allowed = st.multiselect(f"Unlocked agents (max {limit})", options=list(AGENT_SPECS.keys()), default=current_allowed, key="org_allowed_agents")
            new_allowed = [a for a in new_allowed if a in AGENT_SPECS][:limit]
            if st.button("Save unlocked agents", use_container_width=True, key="save_allowed_agents"):
                conn = db_conn()
                conn.execute("UPDATE orgs SET allowed_agents_json=? WHERE team_id=?", (json.dumps(new_allowed), my_team))
                conn.commit(); conn.close()
                log_audit(my_team, me.get("username",""), my_role, "org.allowed_agents.update", "org", my_team, json.dumps(new_allowed))
                ui_toast("Updated unlocked agents.", icon="🤖")
                st.rerun()

# ============================================================
# ROOT ADMIN (global)
# ============================================================
def render_root_admin():
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend: global orgs/users/logs + plan/agent lock management.")

    tabs = st.tabs(["🏢 Orgs", "👥 Users", "📜 Logs", "🧪 System"])

    with tabs[0]:
        st.subheader("Organizations")
        conn = db_conn()
        df = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        st.markdown("### Set plan → auto-set allowed agents")
        team_id = st.text_input("Team ID", key="root_setplan_team")
        plan = st.selectbox("Plan", ["Lite","Pro","Enterprise","Unlimited"], index=0, key="root_setplan_plan")
        if st.button("Set plan → auto-set allowed agents", use_container_width=True, key="root_setplan_apply"):
            if not team_id.strip():
                st.error("Team ID required.")
            else:
                max_agents = PLAN_AGENT_LIMIT.get(plan, 3)
                allowed = PLAN_ALLOWED_AGENTS.get(plan, list(AGENT_SPECS.keys()))[:max_agents]
                conn = db_conn()
                conn.execute("UPDATE orgs SET plan=?, seats_allowed=?, allowed_agents_json=? WHERE team_id=?",
                             (plan, PLAN_SEATS.get(plan, 1), json.dumps(allowed), team_id.strip()))
                conn.commit(); conn.close()
                log_audit("ROOT", me.get("username","root"), "root", "org.plan.set", "org", team_id.strip(), f"plan={plan}")
                ui_toast("Plan updated and agent locks auto-set.", icon="🛡️")
                st.rerun()

        st.markdown("---")
        st.markdown("### Edit org agent locks (advanced)")
        edit_team = st.text_input("Team ID to edit", key="root_edit_team")
        if edit_team.strip():
            orgx = get_org(edit_team.strip())
            cur_allowed = get_allowed_agents_for_org(orgx)
            max_agents = PLAN_AGENT_LIMIT.get(str(orgx.get("plan","Lite")), 3)
            new_allowed = st.multiselect(f"Allowed agents (max {max_agents})", options=list(AGENT_SPECS.keys()), default=cur_allowed, key="root_allowed_agents")
            new_allowed = [a for a in new_allowed if a in AGENT_SPECS][:max_agents]
            if st.button("Save org allowed agents", use_container_width=True, key="root_save_allowed_agents"):
                conn = db_conn()
                conn.execute("UPDATE orgs SET allowed_agents_json=? WHERE team_id=?", (json.dumps(new_allowed), edit_team.strip()))
                conn.commit(); conn.close()
                log_audit("ROOT", me.get("username","root"), "root", "org.allowed_agents.update", "org", edit_team.strip(), json.dumps(new_allowed))
                ui_toast("Org agent locks updated.", icon="🤖")
                st.rerun()

    with tabs[1]:
        st.subheader("Users")
        conn = db_conn()
        df = pd.read_sql_query("SELECT username,name,email,role,active,credits,team_id,created_at,last_login_at FROM users ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

        st.markdown("### Manage user (global)")
        uname = st.text_input("Username", key="root_user_name")
        if uname.strip():
            u = get_user(uname.strip())
            if not u:
                st.warning("User not found.")
            else:
                st.write(f"Team: `{u.get('team_id')}` • Role: **{u.get('role')}**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    role = st.selectbox("Role", ["viewer","editor","admin"], index=["viewer","editor","admin"].index(normalize_role(u.get("role","viewer"))) if normalize_role(u.get("role","viewer")) in ["viewer","editor","admin"] else 0, key="root_user_role")
                with c2:
                    active = st.selectbox("Active", [1,0], index=0 if int(u.get("active",1))==1 else 1, key="root_user_active")
                with c3:
                    credits = st.number_input("Credits", min_value=0, value=int(u.get("credits") or 0), step=1, key="root_user_credits")
                new_pw = st.text_input("Reset password", type="password", key="root_user_pw")
                if st.button("Apply user changes", use_container_width=True, key="root_user_apply"):
                    team = u.get("team_id")
                    update_user_role(team, uname.strip(), role)
                    set_user_active(team, uname.strip(), int(active))
                    update_user_credits(team, uname.strip(), int(credits))
                    if new_pw.strip():
                        reset_user_password(team, uname.strip(), new_pw.strip())
                        st.session_state["auth_refresh_nonce"] += 1
                    log_audit("ROOT", me.get("username","root"), "root", "user.update", "user", uname.strip(), f"role={role} active={active} credits={credits}")
                    ui_toast("User updated.", icon="👥")
                    st.rerun()

    with tabs[2]:
        st.subheader("Audit Logs (global)")
        conn = db_conn()
        df = pd.read_sql_query("SELECT timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(df, width="stretch", hide_index=True)

    with tabs[3]:
        st.subheader("System Health")
        conn = db_conn()
        counts = {}
        for table in ["orgs","users","reports","campaigns","assets","workflows","integrations","kpi_events","kanban_cards","geo_catalog","audit_logs"]:
            try:
                counts[table] = int(pd.read_sql_query(f"SELECT COUNT(*) as n FROM {table}", conn).iloc[0]["n"])
            except Exception:
                counts[table] = 0
        conn.close()
        st.json(counts)
        st.info("Tip: If UI is blank, check Streamlit logs for redacted exception details.")

# ============================================================
# TABS
# ============================================================
tab_labels = ["📖 Guide"] + [t for (t, _) in AGENT_ORDER] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (title, key) in AGENT_ORDER:
    with TAB[title]:
        render_agent_seat(title, key, sidebar_ctx.get("custom_logo"))

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
