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

PRODUCTION_MODE = True  # hide Streamlit chrome (not Cloud overlays)
SWARM_STEP_MODE_DEFAULT = True  # run agents one-by-one (Pause/Stop works between agents)

PLAN_SEATS = {
    "Lite": 1,
    "Basic": 1,
    "Pro": 5,
    "Enterprise": 20,
    "Unlimited": 9999,
}

# Plan → max agents (also used for auto-allowed agents if not customized)
PLAN_AGENT_LIMIT = {
    "Lite": 3,
    "Basic": 3,
    "Pro": 5,
    "Enterprise": 8,
    "Unlimited": 8,
}

ALL_AGENT_KEYS = ["analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo"]

AGENT_SPECS = {
    "analyst": "🕵️ **Market Analyst**: competitor gaps, pricing, positioning.",
    "ads": "📺 **Ads Architect**: deployable ads for Google/Meta.",
    "creative": "🎨 **Creative Director**: concepts + prompt packs + ad variants.",
    "strategist": "👔 **Strategist**: 30-day execution roadmap.",
    "social": "📱 **Social**: engagement content calendar.",
    "geo": "📍 **GEO**: local visibility and citations.",
    "audit": "🌐 **Audit**: website conversion friction.",
    "seo": "✍️ **SEO**: authority article + cluster plan.",
}

DEPLOY_PROTOCOL = [
    "1) **Configure mission** in the sidebar (Brand, Location, Directives, URL).",
    "2) Agents are **locked by plan** (selected during org creation or by Root Admin).",
    "3) Click **LAUNCH OMNI-SWARM** to start the run.",
    "4) The swarm runs **one agent at a time** (Pause/Stop works between agents).",
    "5) Review outputs in each **Agent Seat**, export Word/PDF, and save to **Reports Vault**.",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

AGENT_UI_MAP = [
    ("🕵️ Analyst", "analyst"),
    ("📺 Ads", "ads"),
    ("🎨 Creative", "creative"),
    ("👔 Strategist", "strategist"),
    ("📱 Social", "social"),
    ("📍 GEO", "geo"),
    ("🌐 Auditor", "audit"),
    ("✍ SEO", "seo"),
]

# ============================================================
# CSS / CHROME
# ============================================================
def inject_global_css():
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

    st.markdown(
        f"""
    <style>
      {hide_chrome}
      .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
      .msi-banner {{
        border: 1px solid rgba(15,23,42,.10);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(255,255,255,.85);
        box-shadow: 0 18px 40px rgba(2,6,23,.06);
        margin-bottom: 10px;
      }}
      .msi-muted {{ color: #64748b; font-size: 13px; }}
      .msi-chip {{
        display: inline-block;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(99,102,241,.18);
        background: rgba(99,102,241,.08);
        color: #3730a3;
        margin-left: 8px;
      }}
    </style>
    """,
        unsafe_allow_html=True,
    )


inject_global_css()

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


def _try_json_list(x) -> List[str]:
    try:
        if x is None:
            return []
        if isinstance(x, list):
            return [str(i) for i in x]
        s = str(x).strip()
        if not s:
            return []
        v = json.loads(s)
        if isinstance(v, list):
            return [str(i) for i in v]
        return []
    except Exception:
        return []


def _default_allowed_agents_for_plan(plan: str) -> List[str]:
    plan = (plan or "Lite").strip()
    limit = PLAN_AGENT_LIMIT.get(plan, 3)
    # sensible defaults: Lite => analyst/creative/strategist, then add others
    order = ["analyst", "creative", "strategist", "ads", "social", "geo", "audit", "seo"]
    return order[: max(1, min(limit, len(order)))]


def _hash_password(pw: str) -> str:
    """
    streamlit_authenticator has changed hashing APIs across versions.
    This helper tries multiple known patterns.
    """
    pw = pw or ""
    # v0.4+ style sometimes has Hasher.hash
    try:
        if hasattr(stauth, "Hasher") and hasattr(stauth.Hasher, "hash"):
            return stauth.Hasher.hash(pw)
    except Exception:
        pass
    # older style: Hasher([pw]).generate()[0]
    try:
        return stauth.Hasher([pw]).generate()[0]
    except Exception:
        pass
    # last resort: keep plaintext (NOT recommended) — but better than breaking auth entirely
    return pw


@st.cache_resource
def init_db_once() -> None:
    conn = db_conn()
    cur = conn.cursor()

    cur.execute(
        """
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
    """
    )

    cur.execute(
        """
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
    """
    )

    cur.execute(
        """
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
    """
    )

    cur.execute(
        """
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
    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            asset_type TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            enabled INTEGER DEFAULT 0,
            trigger TEXT,
            steps TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            enabled INTEGER DEFAULT 0,
            config_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kpi_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            event_type TEXT,
            value REAL DEFAULT 1,
            metadata_json TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """
    )

    # Kanban leads + report vault + custom geo
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            title TEXT,
            city TEXT,
            service TEXT,
            stage TEXT DEFAULT 'Discovery',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    cur.execute(
        """
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
    """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS geo_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            state TEXT,
            city TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    # Ensure missing columns for older DBs
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")
    ensure_column(conn, "orgs", "allowed_agents_json", "TEXT DEFAULT ''")
    ensure_column(conn, "orgs", "status", "TEXT DEFAULT 'active'")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")

    # Seed ROOT org + root user
    cur.execute(
        """
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active', '')
    """
    )
    root_pw = _hash_password(os.getenv("ROOT_PASSWORD", "root123"))
    cur.execute(
        """
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """,
        (root_pw,),
    )

    # Seed demo org if none exists
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        allowed = json.dumps(_default_allowed_agents_for_plan("Lite"))
        cur.execute(
            """
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
            VALUES ('ORG_001', 'TechNovance Customer', 'Lite', 1, 'active', ?)
        """,
            (allowed,),
        )
        admin_pw = _hash_password("admin123")
        cur.execute(
            """
            INSERT OR REPLACE INTO users
            (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES ('admin','admin@customer.ai','Org Admin',?, 'admin',1,'Lite',999,1,'ORG_001')
        """,
            (admin_pw,),
        )

    conn.commit()
    conn.close()


def log_audit(
    team_id: str,
    actor: str,
    actor_role: str,
    action_type: str,
    object_type: str = "",
    object_id: str = "",
    details: str = "",
) -> None:
    try:
        conn = db_conn()
        conn.execute(
            """
            INSERT INTO audit_logs (timestamp, team_id, actor, actor_role, action_type, object_type, object_id, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.utcnow().isoformat(),
                team_id,
                actor,
                actor_role,
                action_type,
                object_type,
                object_id,
                details[:4000],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


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
    df = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM users WHERE team_id=? AND active=1 AND role!='root'",
        conn,
        params=(team_id,),
    )
    conn.close()
    return int(df.iloc[0]["n"] or 0)


def normalize_role(role: str) -> str:
    role = (role or "").strip().lower()
    return role if role in {"viewer", "editor", "admin", "root"} else "viewer"


PERMISSIONS = {
    "viewer": {"read"},
    "editor": {"read", "campaign_write", "asset_write", "workflow_write"},
    "admin": {"read", "campaign_write", "asset_write", "workflow_write", "user_manage", "export"},
    "root": {"*"},
}


def can(role: str, perm: str) -> bool:
    perms = PERMISSIONS.get(normalize_role(role), {"read"})
    return ("*" in perms) or (perm in perms) or (perm == "read")


def upsert_org(team_id: str, org_name: str, plan: str, status: str = "active", allowed_agents: Optional[List[str]] = None):
    plan = (plan or "Lite").strip()
    seats = PLAN_SEATS.get(plan, 1)

    allowed_agents = allowed_agents or []
    allowed_agents = [a for a in allowed_agents if a in ALL_AGENT_KEYS]

    conn = db_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM orgs WHERE team_id=?), datetime('now')))
    """,
        (team_id, org_name, plan, seats, status, json.dumps(allowed_agents), team_id),
    )
    conn.commit()
    conn.close()


def set_org_plan(team_id: str, plan: str):
    plan = (plan or "Lite").strip()
    seats = PLAN_SEATS.get(plan, 1)
    conn = db_conn()
    conn.execute("UPDATE orgs SET plan=?, seats_allowed=? WHERE team_id=?", (plan, seats, team_id))
    conn.commit()
    conn.close()


def set_org_allowed_agents(team_id: str, agents: List[str]):
    agents = [a for a in (agents or []) if a in ALL_AGENT_KEYS]
    conn = db_conn()
    conn.execute("UPDATE orgs SET allowed_agents_json=? WHERE team_id=?", (json.dumps(agents), team_id))
    conn.commit()
    conn.close()


def set_org_plan_and_auto_agents(team_id: str, plan: str) -> List[str]:
    set_org_plan(team_id, plan)
    agents = _default_allowed_agents_for_plan(plan)
    set_org_allowed_agents(team_id, agents)
    return agents


def create_user(
    team_id: str,
    username: str,
    name: str,
    email: str,
    password_plain: str,
    role: str,
) -> Tuple[bool, str]:
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

    hashed = _hash_password(password_plain)
    conn = db_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES (?, ?, ?, ?, ?, 1, (SELECT plan FROM orgs WHERE team_id=?), 10, 1, ?)
        """,
            (username, email, name, hashed, role, team_id, team_id),
        )
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def set_user_active(team_id: str, username: str, active: int):
    conn = db_conn()
    conn.execute(
        "UPDATE users SET active=? WHERE username=? AND team_id=? AND role!='root'",
        (int(active), username, team_id),
    )
    conn.commit()
    conn.close()


def update_user_role(team_id: str, username: str, role: str):
    role = normalize_role(role)
    if role == "root":
        return
    conn = db_conn()
    conn.execute(
        "UPDATE users SET role=? WHERE username=? AND team_id=? AND role!='root'",
        (role, username, team_id),
    )
    conn.commit()
    conn.close()


def reset_user_password(team_id: str, username: str, new_password: str):
    if not new_password:
        return
    hashed = _hash_password(new_password)
    conn = db_conn()
    conn.execute(
        "UPDATE users SET password=? WHERE username=? AND team_id=? AND role!='root'",
        (hashed, username, team_id),
    )
    conn.commit()
    conn.close()


def add_user_credits(team_id: str, username: str, delta: int):
    conn = db_conn()
    conn.execute(
        "UPDATE users SET credits=COALESCE(credits,0)+? WHERE username=? AND team_id=? AND role!='root'",
        (int(delta), username, team_id),
    )
    conn.commit()
    conn.close()


def set_user_credits(team_id: str, username: str, value: int):
    conn = db_conn()
    conn.execute(
        "UPDATE users SET credits=? WHERE username=? AND team_id=? AND role!='root'",
        (int(value), username, team_id),
    )
    conn.commit()
    conn.close()


def delete_user(team_id: str, username: str):
    conn = db_conn()
    conn.execute("DELETE FROM users WHERE username=? AND team_id=? AND role!='root'", (username, team_id))
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


def get_allowed_agents_for_team(team_id: str) -> List[str]:
    org = get_org(team_id)
    agents = _try_json_list(org.get("allowed_agents_json"))
    if agents:
        return [a for a in agents if a in ALL_AGENT_KEYS]
    # If empty, auto-set based on plan (and persist)
    auto = _default_allowed_agents_for_plan(org.get("plan", "Lite"))
    try:
        set_org_allowed_agents(team_id, auto)
    except Exception:
        pass
    return auto


# Initialize DB
init_db_once()

# ============================================================
# FPDF PATCH (kept)
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
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        body = nuclear_ascii(content).replace("\r", "")
        body = "\n".join(line[:900] for line in body.split("\n"))
        pdf.multi_cell(0, 6, body)

        return pdf.output(dest="S").encode("latin-1")
    except Exception:
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Arial", size=12)
        fallback.multi_cell(0, 10, "PDF GENERATION FAILED\n\nContent sanitized.\nError handled safely.")
        return fallback.output(dest="S").encode("latin-1")


def export_word(content, title):
    doc = Document()
    doc.add_heading(f"Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


# ============================================================
# AUTHENTICATION
# ============================================================
def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users WHERE active=1", conn)
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


def _cookie_secrets():
    # safer local defaults if cookie secrets missing
    try:
        ck = st.secrets.get("cookie", {})
        return {
            "name": ck.get("name", "msi_cookie"),
            "key": ck.get("key", "msi_cookie_key_change_me"),
            "expiry_days": int(ck.get("expiry_days", 30)),
        }
    except Exception:
        return {"name": "msi_cookie", "key": "msi_cookie_key_change_me", "expiry_days": 30}


# Build authenticator fresh each run so new users/logins work without manual restarts
cookie = _cookie_secrets()
authenticator = stauth.Authenticate(
    get_db_creds(),
    cookie["name"],
    cookie["key"],
    cookie["expiry_days"],
)

# ============================================================
# LOGIN PAGE
# ============================================================
def login_page():
    st.markdown(
        """
    <style>
      [data-testid="stSidebar"] { display:none; }
      .bg {
        position: fixed; inset: 0;
        background:
          radial-gradient(1200px 600px at 50% 0%, rgba(99,102,241,0.20), transparent 60%),
          radial-gradient(900px 500px at 10% 30%, rgba(16,185,129,0.16), transparent 60%),
          radial-gradient(900px 500px at 90% 30%, rgba(236,72,153,0.14), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #fafafe 60%, #ffffff 100%);
        z-index: -1;
      }
      .shell { max-width: 1080px; margin: 0 auto; padding: 26px 12px 50px; }
      .hero { display:flex; align-items:flex-start; justify-content:space-between; gap: 18px; }
      .badge { font-size:12px; padding: 5px 10px; border-radius: 999px; border:1px solid rgba(99,102,241,0.20); background: rgba(99,102,241,0.08); color:#3730a3; display:inline-block; }
      .title { font-size: 46px; font-weight: 850; letter-spacing:-0.02em; margin: 8px 0 6px; color:#0f172a; }
      .sub { color:#334155; font-size:14px; margin:0 0 16px; }
      .grid { display:grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; }
      .card { border:1px solid rgba(15,23,42,0.10); border-radius: 18px; background: rgba(255,255,255,0.86); box-shadow: 0 24px 60px rgba(2,6,23,0.08); padding: 16px; }
      .pricing { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 8px;}
      .pricecard { border:1px solid rgba(15,23,42,0.10); border-radius: 16px; padding: 12px; background: rgba(255,255,255,0.92); }
      .price { font-size: 26px; font-weight: 900; }
      .pill { font-size:12px; color:#0f172a; background: rgba(15,23,42,.04); border: 1px solid rgba(15,23,42,.08); padding: 4px 8px; border-radius: 999px; display:inline-block; margin-top: 6px;}
      .feat { color:#475569; font-size:13px; margin-top: 6px; line-height: 1.35;}
      @media (max-width: 980px){ .grid { grid-template-columns: 1fr; } .pricing { grid-template-columns: 1fr; } .title{font-size:36px;} }
    </style>
    <div class="bg"></div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="shell">', unsafe_allow_html=True)

    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=70)

    st.markdown('<div class="badge">AI Marketing OS • Secure • Multi-Tenant</div>', unsafe_allow_html=True)
    st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub">Campaign ops, governance, analytics, Kanban + Reports Vault — organization-scoped.</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="grid">', unsafe_allow_html=True)

    # Left: value + pricing
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### What you get")
    st.markdown(
        """
- Org isolation (Team ID)  
- RBAC (Admin / Editor / Viewer)  
- Audit trails (logins, exports, changes)  
- Reports Vault + Kanban leads  
- Executive exports (logo supported)  
"""
    )
    st.markdown("### Price Packages")
    st.markdown('<div class="pricing">', unsafe_allow_html=True)
    st.markdown(
        """
      <div class="pricecard"><b>🥉 LITE</b><div class="price">$99/mo</div>
      <div class="pill">1 seat • 3 locked agents</div>
      <div class="feat">Best for solo operators. Analyst + Creative + Strategist by default.</div></div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
      <div class="pricecard"><b>🥈 PRO</b><div class="price">$299/mo</div>
      <div class="pill">5 seats • 5 locked agents</div>
      <div class="feat">Team workflows, more channels, deeper execution outputs.</div></div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
      <div class="pricecard"><b>🥇 ENTERPRISE</b><div class="price">$999/mo</div>
      <div class="pill">20 seats • 8 locked agents</div>
      <div class="feat">Full stack swarm + governance. Best for agencies & growth teams.</div></div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Right: auth
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tabs = st.tabs(["🔑 Login", "✨ Create Org & Admin", "❓ Forgot Password", "🔄 Refresh Credentials"])

    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state["username"])
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u["username"]))
            conn.commit()
            conn.close()
            log_audit(u.get("team_id", ""), u["username"], u.get("role", ""), "auth.login", "user", u["username"], "login_success")
            st.rerun()

        st.caption("Root login: `root / root123` (or ROOT_PASSWORD env var).")

    with tabs[1]:
        st.subheader("Create Organization")
        with st.form("org_create_form"):
            team_id = st.text_input("Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
            org_name = st.text_input("Organization Name", placeholder="e.g., Acme Corp")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise"], index=0)

            # choose locked agents at signup (limited by plan)
            limit = PLAN_AGENT_LIMIT.get(plan, 3)
            default_agents = _default_allowed_agents_for_plan(plan)
            chosen = st.multiselect(
                f"Locked Agents (max {limit})",
                ALL_AGENT_KEYS,
                default=default_agents,
                help="These are the only agents this org can run until upgraded.",
            )
            if len(chosen) > limit:
                chosen = chosen[:limit]

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
                upsert_org(team_id, org_name, plan, status="active", allowed_agents=chosen)
                ok, msg = create_user(team_id, admin_username, admin_name, admin_email, admin_password, "admin")
                if ok:
                    log_audit(team_id, admin_username, "admin", "org.create", "org", team_id, f"plan={plan} agents={chosen}")
                    st.success("Organization created. Use Login tab to sign in.")
                else:
                    st.error(msg)

    with tabs[2]:
        authenticator.forgot_password(location="main")

    with tabs[3]:
        st.info("If you just created users/orgs and login isn’t seeing them, refresh your browser or rerun the app.")
        if st.button("Rerun Now", use_container_width=True):
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
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
org_status = str(org.get("status", "active"))
unlocked_agents = ALL_AGENT_KEYS if is_root else get_allowed_agents_for_team(my_team)

# If org disabled, block
if (not is_root) and org_status != "active":
    st.error("This organization is not active. Contact support.")
    st.stop()

# ============================================================
# GEO DATA (defaults + custom per org)
# ============================================================
@st.cache_data(ttl=3600)
def default_geo_data() -> Dict[str, List[str]]:
    return {
        "Alabama": ["Birmingham", "Huntsville", "Mobile", "Montgomery"],
        "Arizona": ["Phoenix", "Scottsdale", "Tucson", "Mesa"],
        "California": ["Los Angeles", "San Francisco", "San Diego", "Sacramento", "San Jose"],
        "Florida": ["Miami", "Orlando", "Tampa", "Jacksonville"],
        "Georgia": ["Atlanta", "Savannah", "Augusta"],
        "Illinois": ["Chicago", "Naperville", "Plainfield", "Aurora", "Rockford"],
        "Indiana": ["Indianapolis", "Fort Wayne", "Evansville"],
        "Michigan": ["Detroit", "Grand Rapids", "Ann Arbor"],
        "New York": ["New York", "Buffalo", "Rochester"],
        "North Carolina": ["Charlotte", "Raleigh", "Durham"],
        "Ohio": ["Columbus", "Cleveland", "Cincinnati"],
        "Pennsylvania": ["Philadelphia", "Pittsburgh", "Allentown"],
        "Texas": ["Austin", "Dallas", "Houston", "San Antonio", "Fort Worth"],
        "Virginia": ["Richmond", "Virginia Beach", "Norfolk"],
        "Washington": ["Seattle", "Spokane", "Tacoma"],
        "Wisconsin": ["Milwaukee", "Madison", "Green Bay"],
    }


def load_custom_geo(team_id: str) -> Dict[str, List[str]]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT state, city FROM geo_locations WHERE team_id=? ORDER BY state, city", conn, params=(team_id,))
    finally:
        conn.close()
    out: Dict[str, List[str]] = {}
    if df.empty:
        return out
    for _, r in df.iterrows():
        s = str(r["state"] or "").strip()
        c = str(r["city"] or "").strip()
        if not s or not c:
            continue
        out.setdefault(s, [])
        if c not in out[s]:
            out[s].append(c)
    return out


def add_custom_geo(team_id: str, state: str, city: str):
    state = (state or "").strip()
    city = (city or "").strip()
    if not state or not city:
        return
    conn = db_conn()
    conn.execute("INSERT INTO geo_locations (team_id,state,city) VALUES (?,?,?)", (team_id, state, city))
    conn.commit()
    conn.close()


# ============================================================
# SWARM RUN STATE (step-mode runner)
# ============================================================
def _swarm_state_init():
    if "swarm_run" not in st.session_state:
        st.session_state["swarm_run"] = {
            "running": False,
            "paused": False,
            "stopped": False,
            "queue": [],
            "idx": 0,
            "started_at": None,
            "last_agent": "",
            "payload": {},
            "mode_step": SWARM_STEP_MODE_DEFAULT,
        }


def _compose_full_report(biz: str, loc: str, plan: str, report: Dict[str, Any]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    def g(k): return str(report.get(k) or "").strip()

    header = f"# {biz} Intelligence Report\n**Date:** {now} | **Location:** {loc} | **Plan:** {plan}\n---\n"
    sections = [
        ("## 🕵️ Market Analysis", g("analyst")),
        ("## 🌐 Website Audit", g("audit")),
        ("## 👔 Executive Strategy", g("strategist")),
        ("## 📺 Ads Output", g("ads")),
        ("## 🎨 Creative Pack", g("creative")),
        ("## ✍️ SEO Authority Article", g("seo")),
        ("## 📍 GEO Intelligence", g("geo")),
        ("## 📱 Social Roadmap", g("social")),
    ]
    body = "\n\n".join([f"{t}\n{c if c else '—'}" for t, c in sections])
    return header + body + "\n"


def _swarm_start(queue: List[str], payload: Dict[str, Any], step_mode: bool):
    _swarm_state_init()
    st.session_state["swarm_run"].update(
        {
            "running": True,
            "paused": False,
            "stopped": False,
            "queue": queue[:],
            "idx": 0,
            "started_at": datetime.utcnow().isoformat(),
            "last_agent": "",
            "payload": payload,
            "mode_step": bool(step_mode),
        }
    )
    st.session_state["gen"] = False
    st.session_state.setdefault("report", {})
    st.session_state["last_active_swarm"] = queue[:]


def _swarm_pause(val: bool):
    _swarm_state_init()
    st.session_state["swarm_run"]["paused"] = bool(val)


def _swarm_stop():
    _swarm_state_init()
    st.session_state["swarm_run"]["stopped"] = True
    st.session_state["swarm_run"]["running"] = False
    st.session_state["swarm_run"]["paused"] = False


def _swarm_tick_run_one_agent() -> bool:
    """
    Runs exactly ONE agent from the queue, merges output into st.session_state['report'].
    Returns True if it ran an agent, False otherwise.
    """
    _swarm_state_init()
    run = st.session_state["swarm_run"]
    if not run.get("running"):
        return False
    if run.get("paused"):
        return False
    if run.get("stopped"):
        return False

    queue = run.get("queue") or []
    idx = int(run.get("idx") or 0)
    if idx >= len(queue):
        run["running"] = False
        return False

    agent_key = queue[idx]
    run["last_agent"] = agent_key

    payload = dict(run.get("payload") or {})
    payload["active_swarm"] = [agent_key]  # run one agent at a time

    with st.status(f"🚀 Running {agent_key.upper()}…", expanded=True) as status:
        try:
            out = run_marketing_swarm(payload) or {}
        except Exception as e:
            msg = str(e)
            st.error(f"Swarm error: {msg}")
            log_audit(my_team, me["username"], my_role, "swarm.error", "agent", agent_key, msg[:2000])
            out = {}

        # Merge outputs
        rep = st.session_state.get("report") or {}
        # If main.py returns only full_report sometimes, still keep key present for visibility
        if agent_key not in out:
            out[agent_key] = rep.get(agent_key, "")  # preserve previous if any

        rep.update(out)
        # Always rebuild a full_report from merged dict (do not re-run main.py for this)
        rep["full_report"] = _compose_full_report(
            payload.get("biz_name", ""),
            payload.get("city", ""),
            payload.get("package", ""),
            rep,
        )
        st.session_state["report"] = rep

        status.update(label=f"✅ {agent_key.upper()} complete", state="complete", expanded=False)

    run["idx"] = idx + 1

    # If step mode, pause after each agent so user can navigate / stop / continue
    if run.get("mode_step", True):
        run["paused"] = True

    # If finished, end
    if run["idx"] >= len(queue):
        run["running"] = False
        run["paused"] = False
        st.session_state["gen"] = True
        st.toast("✅ Swarm completed", icon="✅")
        log_audit(my_team, me["username"], my_role, "swarm.run.complete", "swarm", payload.get("biz_name", ""), f"agents={queue}")
    else:
        st.toast(f"✅ {agent_key} complete. Continue when ready.", icon="✅")

    return True


_swarmsafe = {"ran_tick": False}

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=110)

    st.subheader(org.get("org_name", "Organization"))
    st.caption(f"Team: `{my_team}` • Role: **{my_role.upper()}**")
    st.metric("Plan", org_plan)
    st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")

    if not is_root:
        st.metric("Unlocked agents", f"{len(unlocked_agents)}/{PLAN_AGENT_LIMIT.get(org_plan, len(unlocked_agents))}")

    st.divider()

    biz_name = st.text_input("🏢 Brand Name", value=st.session_state.get("biz_name", ""))
    st.session_state["biz_name"] = biz_name

    website_url = st.text_input(
        "🔗 Website URL (for Auditor)",
        value=st.session_state.get("website_url", ""),
        placeholder="https://example.com",
    )
    st.session_state["website_url"] = website_url

    custom_logo = st.file_uploader("📤 Brand Logo (All plans)", type=["png", "jpg", "jpeg"])

    geo_default = default_geo_data()
    geo_custom = load_custom_geo(my_team) if not is_root else {}
    geo = dict(geo_default)
    # Merge custom
    for s, cities in geo_custom.items():
        geo.setdefault(s, [])
        for c in cities:
            if c not in geo[s]:
                geo[s].append(c)

    selected_state = st.selectbox("🎯 Target State", sorted(geo.keys()), index=0 if "Illinois" not in geo else sorted(geo.keys()).index("Illinois"))
    pick_mode = st.radio("City", ["Pick from list", "Add custom"], horizontal=True, index=0)
    if pick_mode == "Pick from list":
        selected_city = st.selectbox("🏙️ Target City", sorted(geo[selected_state]))
    else:
        selected_city = st.text_input("🏙️ Target City (custom)", value="")
        if st.button("➕ Save custom city", use_container_width=True):
            add_custom_geo(my_team, selected_state, selected_city)
            st.success("Saved.")
            st.rerun()

    full_loc = f"{selected_city}, {selected_state}".strip(", ")

    st.divider()
    directives = st.text_area("✍️ Strategic Directives", value=st.session_state.get("directives", ""))
    st.session_state["directives"] = directives

    # Locked selection: users cannot swap agents; root can (for testing)
    st.divider()
    _swarm_state_init()
    run = st.session_state["swarm_run"]

    step_mode = st.toggle("🧭 Step Mode (Pause between agents)", value=bool(run.get("mode_step", SWARM_STEP_MODE_DEFAULT)))

    with st.expander("🤖 Swarm Personnel (Locked)" if not is_root else "🤖 Swarm Personnel", expanded=True):
        st.caption(f"Unlocked for this org: {unlocked_agents}")
        toggles: Dict[str, bool] = {}

        # IMPORTANT: set defaults BEFORE widgets to avoid session_state mutation exceptions
        for _, k in AGENT_UI_MAP:
            keyname = f"tg_{k}"
            if keyname not in st.session_state:
                # default ON only if unlocked (for customers)
                st.session_state[keyname] = (k in unlocked_agents) if not is_root else False
            # enforce locked OFF for locked agents (customers only) BEFORE widget renders
            if (not is_root) and (k not in unlocked_agents):
                st.session_state[keyname] = False
            # enforce locked ON for unlocked agents (customers only)
            if (not is_root) and (k in unlocked_agents):
                st.session_state[keyname] = True

        for label, k in AGENT_UI_MAP:
            disabled = (not is_root)  # customers cannot change locked selection
            toggles[k] = st.toggle(label, value=bool(st.session_state.get(f"tg_{k}", False)), key=f"tg_{k}", disabled=disabled)

    st.divider()

    # Buttons (Launch/Continue/Pause/Stop)
    if run.get("running"):
        st.markdown("**Swarm Status**")
        st.write(f"Running: `{run.get('running')}` • Paused: `{run.get('paused')}` • Next: `{(run.get('queue') or ['-'])[int(run.get('idx') or 0)] if int(run.get('idx') or 0) < len(run.get('queue') or []) else '-'}`")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("⏸ Pause", use_container_width=True):
                _swarm_pause(True)
                st.rerun()
            if st.button("▶ Resume", use_container_width=True):
                _swarm_pause(False)
                # run one tick immediately on resume
                st.rerun()
        with c2:
            if st.button("🛑 Stop", type="secondary", use_container_width=True):
                _swarm_stop()
                st.toast("Swarm stopped.", icon="🛑")
                st.rerun()

    # Launch / Continue
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True, disabled=bool(run.get("running")))

    if run.get("running") and run.get("paused"):
        continue_btn = st.button("➡️ Run Next Agent", use_container_width=True)
    else:
        continue_btn = False

    authenticator.logout("🔒 Sign Out", "sidebar")


# ============================================================
# START / TICK SWARM
# ============================================================
def _current_queue_from_ui() -> List[str]:
    if is_root:
        return [k for k, v in (toggles or {}).items() if v]
    # customers: always run unlocked (locked-on)
    return unlocked_agents[:]


if run_btn:
    queue = _current_queue_from_ui()
    if not biz_name:
        st.error("Enter Brand Name first.")
    elif not queue:
        st.warning("No agents available for this org (check allowed agents).")
    else:
        payload = {
            "city": full_loc,
            "biz_name": biz_name,
            "package": org_plan,
            "custom_logo": custom_logo,
            "directives": directives,
            "url": website_url,  # IMPORTANT for Auditor
        }
        _swarm_start(queue, payload, step_mode=step_mode)
        log_audit(my_team, me["username"], my_role, "swarm.run.start", "swarm", biz_name, f"agents={queue} loc={full_loc}")
        # Immediately run first agent
        st.session_state["swarm_run"]["paused"] = False
        st.rerun()

if continue_btn:
    st.session_state["swarm_run"]["paused"] = False
    st.rerun()

# Run one agent tick if appropriate (never loops endlessly)
if st.session_state.get("swarm_run", {}).get("running") and (not st.session_state["swarm_run"].get("paused")):
    if not _swarmsafe["ran_tick"]:
        _swarmsafe["ran_tick"] = True
        _swarm_tick_run_one_agent()
        # after tick, rerun to refresh UI
        st.rerun()

# ============================================================
# TOP BANNER (progress + navigation)
# ============================================================
run = st.session_state.get("swarm_run", {})
if run.get("running"):
    queue = run.get("queue") or []
    idx = int(run.get("idx") or 0)
    last_agent = run.get("last_agent") or ""
    total = len(queue)
    status_txt = f"Swarm running — {idx}/{total} complete"
    if last_agent:
        status_txt += f" (last: {last_agent})"
    next_agent = queue[idx] if idx < total else "—"
    st.markdown(
        f"""
        <div class="msi-banner">
          <b>🚀 {status_txt}</b>
          <span class="msi-chip">Next: {next_agent}</span>
          <div class="msi-muted">You can switch tabs while paused. Use <b>Run Next Agent</b> to continue.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# RENDERERS
# ============================================================
def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: **{st.session_state.get('biz_name','Global Mission')}**")
    st.subheader("Agent Specializations")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)
    st.markdown("---")
    st.subheader("🛡️ Swarm Execution Protocol")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")


def render_agent_seat(title: str, key: str, custom_logo_file):
    st.subheader(f"{title} Seat")
    st.caption(AGENT_SPECS.get(key, ""))

    is_unlocked = (key in unlocked_agents) or is_root
    report = st.session_state.get("report") or {}
    last_agents = st.session_state.get("last_active_swarm") or []

    # Show lock status
    if not is_unlocked:
        st.warning("🔒 Locked for your plan. Upgrade to unlock this agent.")
        return

    # Helpful debug row (kept light)
    st.caption(f"Selected this org: ✅ YES • Last report keys: {list(report.keys())[:12]}")

    raw = report.get(key)
    if not raw:
        if key in last_agents:
            st.info("⏳ Pending — this agent hasn’t run yet in the current swarm.")
        else:
            st.info("This agent is available, but not in the last swarm run.")
        return

    # Detect placeholder
    if isinstance(raw, str) and ("Agent not selected" in raw or "not generated" in raw):
        st.error("Selected, but returned placeholder/empty output. This usually means main.py didn’t capture the agent output.")
        st.code(str(raw)[:800])
        return

    edited = st.text_area("Refine Intel", value=str(raw), height=420, key=f"ed_{key}")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "📄 Word",
            export_word(edited, title),
            file_name=f"{key}.docx",
            key=f"w_{key}",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "📕 PDF",
            export_pdf(edited, title, custom_logo_file),
            file_name=f"{key}.pdf",
            key=f"p_{key}",
            use_container_width=True,
        )

    # Push links for social-y agents
    if key in {"ads", "creative", "social"}:
        st.markdown("---")
        st.markdown("#### 📣 Publish / Push")
        st.text_area("Copy-ready content", value=edited, height=140, key=f"push_{key}")
        cols = st.columns(4)
        for i, (nm, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
            with cols[i % 4]:
                st.link_button(nm, url)


def render_vision():
    st.header("👁️ Vision")
    st.caption("Reserved for future photo/asset analysis workflows.")
    st.info("Vision module is enabled, but no vision pipeline is wired yet.")


def render_veo():
    st.header("🎬 Veo Studio")
    st.caption("Reserved for future video generation workflows.")
    st.info("Veo Studio module is enabled, but no video pipeline is wired yet.")


def render_team_intel():
    st.header("🤝 Team Intel")
    st.caption("Org-scoped tools for managing your team, leads, and saved reports.")
    st.write(f"Unlocked agents: `{unlocked_agents}`")

    users_n = active_user_count(my_team)
    seats = seats_allowed_for_team(my_team)
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Users", users_n)
    c2.metric("Seats Allowed", seats)
    c3.metric("Plan", org_plan)

    tabs = st.tabs(["🗂 Kanban Leads", "🧾 Reports Vault", "👥 Users & RBAC", "📣 Campaigns", "🧩 Assets", "⚙️ Workflows", "🔌 Integrations", "🔐 Security Logs"])

    # --- Kanban
    with tabs[0]:
        st.subheader("Kanban Board")
        st.caption("Track leads through stages.")
        stages = ["Discovery", "Execution", "ROI Verified"]

        with st.expander("➕ Add Lead", expanded=True):
            with st.form("lead_add"):
                title = st.text_input("Lead name/title")
                city = st.text_input("City")
                service = st.text_input("Service")
                stage = st.selectbox("Stage", stages, index=0)
                submit = st.form_submit_button("Create Lead", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute(
                    "INSERT INTO leads (team_id,title,city,service,stage) VALUES (?,?,?,?,?)",
                    (my_team, title, city, service, stage),
                )
                conn.commit()
                conn.close()
                log_audit(my_team, me["username"], my_role, "lead.create", "lead", "", f"{title} {stage}")
                st.success("Lead created.")
                st.rerun()

        conn = db_conn()
        df = pd.read_sql_query("SELECT id,title,city,service,stage,created_at FROM leads WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()

        if df.empty:
            st.info("No leads yet.")
        else:
            # simple grouped tables by stage
            for s in stages:
                st.markdown(f"### {s}")
                sdf = df[df["stage"] == s].copy()
                st.dataframe(sdf, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader("Update / Remove")
            lead_id = st.number_input("Lead ID", min_value=1, step=1)
            new_stage = st.selectbox("Move to stage", stages, index=0)
            cA, cB = st.columns(2)
            with cA:
                if st.button("Move Lead", use_container_width=True):
                    conn = db_conn()
                    conn.execute("UPDATE leads SET stage=? WHERE id=? AND team_id=?", (new_stage, int(lead_id), my_team))
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me["username"], my_role, "lead.move", "lead", str(lead_id), f"stage={new_stage}")
                    st.success("Updated.")
                    st.rerun()
            with cB:
                if st.button("Delete Lead", type="secondary", use_container_width=True):
                    conn = db_conn()
                    conn.execute("DELETE FROM leads WHERE id=? AND team_id=?", (int(lead_id), my_team))
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me["username"], my_role, "lead.delete", "lead", str(lead_id), "")
                    st.success("Deleted.")
                    st.rerun()

    # --- Reports Vault
    with tabs[1]:
        st.subheader("Reports Vault")
        st.caption("Save and reload swarm reports for your org.")

        rep = st.session_state.get("report") or {}
        if rep:
            with st.expander("💾 Save current report", expanded=True):
                with st.form("save_report"):
                    name = st.text_input("Report name", value=f"{biz_name or 'Report'} • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                    submit = st.form_submit_button("Save to Vault", use_container_width=True)
                if submit:
                    conn = db_conn()
                    conn.execute(
                        """
                        INSERT INTO reports_vault (team_id,name,created_by,location,biz_name,selected_agents_json,report_json,full_report)
                        VALUES (?,?,?,?,?,?,?,?)
                        """,
                        (
                            my_team,
                            name,
                            me["username"],
                            full_loc,
                            biz_name,
                            json.dumps(st.session_state.get("last_active_swarm") or []),
                            json.dumps(rep),
                            str(rep.get("full_report") or ""),
                        ),
                    )
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me["username"], my_role, "report.save", "report", "", name)
                    st.success("Saved.")
                    st.rerun()
        else:
            st.info("No report currently loaded. Run the swarm first.")

        conn = db_conn()
        vdf = pd.read_sql_query(
            "SELECT id,name,biz_name,location,created_by,created_at FROM reports_vault WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(vdf, use_container_width=True, hide_index=True)

        st.markdown("---")
        rid = st.number_input("Vault report ID", min_value=1, step=1)
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Load report", use_container_width=True):
                conn = db_conn()
                df = pd.read_sql_query("SELECT report_json FROM reports_vault WHERE id=? AND team_id=?", conn, params=(int(rid), my_team))
                conn.close()
                if df.empty:
                    st.error("Not found.")
                else:
                    st.session_state["report"] = json.loads(df.iloc[0]["report_json"] or "{}")
                    st.session_state["gen"] = True
                    st.success("Loaded into workspace.")
                    st.rerun()
        with c2:
            if st.button("Delete report", type="secondary", use_container_width=True):
                conn = db_conn()
                conn.execute("DELETE FROM reports_vault WHERE id=? AND team_id=?", (int(rid), my_team))
                conn.commit()
                conn.close()
                log_audit(my_team, me["username"], my_role, "report.delete", "report", str(rid), "")
                st.success("Deleted.")
                st.rerun()
        with c3:
            if st.button("Download FULL PDF", use_container_width=True):
                # download full report as PDF from session if loaded
                rep = st.session_state.get("report") or {}
                pdf_bytes = export_pdf(str(rep.get("full_report") or "No report."), f"{biz_name} Full Report", custom_logo)
                st.download_button("Click to download", pdf_bytes, file_name="full_report.pdf", use_container_width=True)

    # --- Users & RBAC
    with tabs[2]:
        st.subheader("User & Access (RBAC)")
        conn = db_conn()
        udf = pd.read_sql_query(
            "SELECT username,name,email,role,credits,active,last_login_at,created_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(udf, use_container_width=True, hide_index=True)

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
                    log_audit(my_team, me["username"], my_role, "user.create", "user", u, f"role={r}")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.markdown("### 🔧 Manage user")
            username = st.text_input("Target username")
            new_role = st.selectbox("Set role", ["viewer", "editor", "admin"], index=0)
            new_pw = st.text_input("Reset password", type="password")
            credit_delta = st.number_input("Add credits (+/-)", value=0, step=1)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("Set Role", use_container_width=True):
                    update_user_role(my_team, username, new_role)
                    log_audit(my_team, me["username"], my_role, "user.role", "user", username, f"role={new_role}")
                    st.success("Updated.")
                    st.rerun()
            with c2:
                if st.button("Reset PW", use_container_width=True):
                    reset_user_password(my_team, username, new_pw)
                    log_audit(my_team, me["username"], my_role, "user.reset_pw", "user", username, "")
                    st.success("Updated.")
                    st.rerun()
            with c3:
                if st.button("Apply Credits", use_container_width=True):
                    if credit_delta != 0:
                        add_user_credits(my_team, username, int(credit_delta))
                        log_audit(my_team, me["username"], my_role, "user.credits", "user", username, f"delta={credit_delta}")
                        st.success("Updated.")
                        st.rerun()
            with c4:
                if st.button("Deactivate", type="secondary", use_container_width=True):
                    set_user_active(my_team, username, 0)
                    log_audit(my_team, me["username"], my_role, "user.deactivate", "user", username, "")
                    st.success("Updated.")
                    st.rerun()

            st.markdown("### 📥 Bulk import (CSV)")
            st.caption("Headers: username,name,email,role,password • seat limits enforced")
            up = st.file_uploader("Upload CSV", type=["csv"])
            if up and st.button("Import", use_container_width=True):
                created, errs = bulk_import_users(my_team, up.getvalue())
                log_audit(my_team, me["username"], my_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                if created:
                    st.success(f"Imported {created} user(s).")
                if errs:
                    st.error("Issues:")
                    for x in errs[:15]:
                        st.write(f"- {x}")
                st.rerun()
        else:
            st.info("Only Admin can manage users.")

    # --- Campaigns
    with tabs[3]:
        conn = db_conn()
        df = pd.read_sql_query(
            "SELECT id,name,channel,status,created_at FROM campaigns WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        if can(my_role, "campaign_write") or is_root:
            with st.expander("➕ Create campaign", expanded=False):
                with st.form("camp_new"):
                    name = st.text_input("Campaign name")
                    channel = st.text_input("Channel (e.g., Google, Meta)")
                    status = st.selectbox("Status", ["draft", "active", "paused", "done"])
                    submit = st.form_submit_button("Create", use_container_width=True)
                if submit:
                    conn = db_conn()
                    conn.execute(
                        "INSERT INTO campaigns (team_id,name,channel,status) VALUES (?,?,?,?)",
                        (my_team, name, channel, status),
                    )
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me["username"], my_role, "campaign.create", "campaign", "", name)
                    st.success("Created.")
                    st.rerun()

    # --- Assets
    with tabs[4]:
        conn = db_conn()
        df = pd.read_sql_query(
            "SELECT id,name,asset_type,created_at FROM assets WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        if can(my_role, "asset_write") or is_root:
            with st.expander("➕ Create asset", expanded=False):
                with st.form("asset_new"):
                    name = st.text_input("Asset name")
                    a_type = st.selectbox("Type", ["prompt_pack", "ad_copy", "landing_copy", "creative_brief", "other"])
                    content = st.text_area("Content", height=140)
                    submit = st.form_submit_button("Save", use_container_width=True)
                if submit:
                    conn = db_conn()
                    conn.execute(
                        "INSERT INTO assets (team_id,name,asset_type,content) VALUES (?,?,?,?)",
                        (my_team, name, a_type, content),
                    )
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me["username"], my_role, "asset.create", "asset", "", name)
                    st.success("Saved.")
                    st.rerun()

    # --- Workflows
    with tabs[5]:
        conn = db_conn()
        df = pd.read_sql_query(
            "SELECT id,name,enabled,trigger,created_at FROM workflows WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Integrations
    with tabs[6]:
        conn = db_conn()
        df = pd.read_sql_query(
            "SELECT id,name,enabled,created_at FROM integrations WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Security Logs
    with tabs[7]:
        conn = db_conn()
        logs = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 250",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(logs, use_container_width=True, hide_index=True)


def render_root_admin():
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend: orgs, users, credits, upgrades, security, site health.")
    tabs = st.tabs(["🏢 Orgs", "👥 Users", "💳 Credits", "🪄 Plan → Auto Agents", "📜 Global Logs", "🩺 Site Health"])

    with tabs[0]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Create / Update Org")
        with st.form("root_org_upsert"):
            team_id = st.text_input("Team ID")
            org_name = st.text_input("Org name")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise", "Unlimited"], index=0)
            status = st.selectbox("Status", ["active", "disabled"], index=0)
            limit = PLAN_AGENT_LIMIT.get(plan, 8)
            allowed = st.multiselect(f"Allowed agents (max {limit})", ALL_AGENT_KEYS, default=_default_allowed_agents_for_plan(plan))
            if len(allowed) > limit:
                allowed = allowed[:limit]
            submit = st.form_submit_button("Save Org", use_container_width=True)
        if submit:
            if not team_id or not org_name:
                st.error("Team ID + Org name required")
            elif team_id.upper() == "ROOT":
                st.error("ROOT cannot be edited here.")
            else:
                upsert_org(team_id.strip(), org_name.strip(), plan, status=status, allowed_agents=allowed)
                log_audit("ROOT", me["username"], my_role, "root.org.upsert", "org", team_id, f"plan={plan} status={status} agents={allowed}")
                st.success("Saved.")
                st.rerun()

    with tabs[1]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT username,name,email,role,credits,active,team_id,created_at,last_login_at FROM users ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Manage User")
        team_id = st.text_input("Team ID (for user)")
        username = st.text_input("Username (target)")
        c1, c2, c3 = st.columns(3)
        with c1:
            role = st.selectbox("Role", ["viewer", "editor", "admin"], index=0)
            if st.button("Set Role", use_container_width=True):
                update_user_role(team_id, username, role)
                log_audit("ROOT", me["username"], my_role, "root.user.role", "user", username, f"team={team_id} role={role}")
                st.success("Updated.")
                st.rerun()
        with c2:
            pw = st.text_input("Reset PW", type="password")
            if st.button("Reset Password", use_container_width=True):
                reset_user_password(team_id, username, pw)
                log_audit("ROOT", me["username"], my_role, "root.user.reset_pw", "user", username, f"team={team_id}")
                st.success("Updated.")
                st.rerun()
        with c3:
            if st.button("Delete User", type="secondary", use_container_width=True):
                delete_user(team_id, username)
                log_audit("ROOT", me["username"], my_role, "root.user.delete", "user", username, f"team={team_id}")
                st.success("Deleted.")
                st.rerun()

    with tabs[2]:
        st.subheader("Credits")
        team_id = st.text_input("Team ID", key="rc_team")
        username = st.text_input("Username", key="rc_user")
        delta = st.number_input("Credit delta (+/-)", value=10, step=1, key="rc_delta")
        if st.button("Apply Credits", use_container_width=True):
            add_user_credits(team_id, username, int(delta))
            log_audit("ROOT", me["username"], my_role, "root.credits.apply", "user", username, f"team={team_id} delta={delta}")
            st.success("Applied.")
            st.rerun()

    with tabs[3]:
        st.subheader("Set plan → auto-set allowed agents")
        conn = db_conn()
        odf = pd.read_sql_query("SELECT team_id, org_name, plan FROM orgs WHERE team_id!='ROOT' ORDER BY created_at DESC", conn)
        conn.close()
        if odf.empty:
            st.info("No orgs.")
        else:
            st.dataframe(odf, use_container_width=True, hide_index=True)

        team_id = st.text_input("Target Team ID", key="auto_team")
        plan = st.selectbox("New Plan", ["Lite", "Pro", "Enterprise", "Unlimited"], index=0, key="auto_plan")
        if st.button("✅ Set Plan → Auto-set Allowed Agents", use_container_width=True):
            agents = set_org_plan_and_auto_agents(team_id.strip(), plan)
            log_audit("ROOT", me["username"], my_role, "root.org.plan_auto_agents", "org", team_id, f"plan={plan} agents={agents}")
            st.success(f"Updated: {team_id} → {plan} with agents {agents}")
            st.rerun()

    with tabs[4]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[5]:
        st.subheader("Site Health")
        st.write(f"Python: `{os.sys.version.split()[0]}`")
        st.write(f"DB Path: `{DB_PATH}`")
        conn = db_conn()
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn)
        conn.close()
        st.dataframe(tables, use_container_width=True, hide_index=True)


# ============================================================
# MAIN TABS
# ============================================================
agent_titles = [a[0] for a in AGENT_UI_MAP]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (title, key) in AGENT_UI_MAP:
    with TAB[title]:
        render_agent_seat(title, key, custom_logo)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
