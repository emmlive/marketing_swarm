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
import streamlit.components.v1 as components
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

PLAN_SEATS = {
    "Lite": 1,
    "Basic": 1,
    "Pro": 5,
    "Enterprise": 20,
    "Unlimited": 9999,
}

# Agents that exist in the product (keys must match main.py)
AGENT_SPECS: Dict[str, str] = {
    "analyst": "🕵️ **Market Analyst**: competitor gaps, pricing, positioning, offers.",
    "marketing_adviser": "🧭 **Marketing Adviser**: messaging, channel priorities, next steps.",
    "market_researcher": "📊 **Market Researcher**: TAM/SAM/SOM assumptions, segments, competitors, insights.",
    "ecommerce_marketer": "🛒 **E‑Commerce Marketer**: product positioning, funnels, email/SMS, upsells.",
    "ads": "📺 **Ads Architect**: deployable ads for Google/Meta (tables).",
    "creative": "🎨 **Creative Director**: concepts + prompt packs + ad variants.",
    "guest_posting": "📰 **Guest Posting**: outreach list, pitches, topics, placement plan.",
    "strategist": "👔 **Strategist**: 30‑day execution roadmap + KPIs.",
    "social": "📱 **Social**: 30‑day engagement calendar.",
    "geo": "📍 **GEO**: local visibility & citations.",
    "audit": "🌐 **Audit**: website conversion friction (needs URL).",
    "seo": "✍️ **SEO**: authority article + cluster plan.",
}

# Plan → allowed agents (LOCKED unlock set per org)
PLAN_ALLOWED_AGENTS: Dict[str, List[str]] = {
    "Lite": ["analyst", "marketing_adviser", "strategist"],  # 3 agents
    "Basic": ["analyst", "marketing_adviser", "strategist"],
    "Pro": ["analyst", "marketing_adviser", "strategist", "ads", "creative"],  # 5 agents
    "Enterprise": list(AGENT_SPECS.keys()),  # all
    "Unlimited": list(AGENT_SPECS.keys()),  # all
}

DEPLOY_PROTOCOL = [
    "1) Configure mission (Brand, Location, Directives, URL if auditing).",
    "2) Select agents for this run (only unlocked agents are available).",
    "3) Click **LAUNCH OMNI‑SWARM** to generate executive reports.",
    "4) Review outputs in each seat, refine, then save to **Reports Vault**.",
    "5) Export as Word/PDF and deploy via your business platforms.",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

# ============================================================
# UI HELPERS + CSS / CHROME
# ============================================================

def _toast(message: str, icon: str | None = None):
    """Safe toast (falls back to st.success/info if toast isn't available)."""
    try:
        if hasattr(st, "toast"):
            st.toast(message, icon=icon)
        else:
            # basic fallback
            st.success(message)
    except Exception:
        # Never crash the app for a toast.
        pass

def _link_button(label: str, url: str):
    """Safe link button (falls back to a styled anchor if link_button isn't available)."""
    if hasattr(st, "link_button"):
        try:
            return st.link_button(label, url, use_container_width=True)
        except TypeError:
            return st.link_button(label, url)
    st.markdown(
        f"""<a class="linkbtn" href="{url}" target="_blank" rel="noopener">{label}</a>""",
        unsafe_allow_html=True,
    )

def inject_global_css():
    # Avoid reinjecting on every rerun.
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

          /* tabs spacing */
          .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}

          /* simple link button fallback */
          a.linkbtn {{
            display: inline-block;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(15,23,42,0.14);
            background: rgba(255,255,255,0.88);
            text-decoration: none;
            color: #0f172a;
            font-weight: 650;
            width: 100%;
            text-align: center;
          }}
          a.linkbtn:hover {{
            background: rgba(99,102,241,0.10);
            border-color: rgba(99,102,241,0.30);
          }}

          /* swarm banner */
          .swarmBanner {{
            position: sticky;
            top: 0;
            z-index: 99;
            border: 1px solid rgba(15,23,42,0.12);
            background: rgba(255,255,255,0.90);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 10px 12px;
            margin: 8px 0 12px;
            box-shadow: 0 16px 40px rgba(2,6,23,0.10);
          }}
          .swarmDot {{
            display:inline-block;
            width:10px;height:10px;border-radius:999px;
            background: #22c55e;
            margin-right:8px;
            animation: pulse 1.1s infinite;
          }}
          @keyframes pulse {{
            0% {{ transform: scale(0.9); opacity: 0.55; }}
            50% {{ transform: scale(1.05); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.55; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_global_css()

def _get_query_param(name: str, default: str = "") -> str:
    """Compatible query param getter across Streamlit versions."""
    try:
        # New API (dict-like)
        qp = st.query_params  # type: ignore[attr-defined]
        val = qp.get(name, default)
        if isinstance(val, list):
            return str(val[0]) if val else default
        return str(val)
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            vals = qp.get(name, [])
            return str(vals[0]) if vals else default
        except Exception:
            return default

def _schedule_autorun_refresh(delay_ms: int = 1300):
    """Soft auto-refresh so we can auto-run next agent while still allowing Pause/Stop clicks."""
    try:
        components.html(
            f"""<script>
              setTimeout(function() {{
                const url = new URL(window.parent.location.href);
                url.searchParams.set('tick', Date.now().toString());
                window.parent.location.replace(url.toString());
              }}, {delay_ms});
            </script>""",
            height=0,
        )
    except Exception:
        pass
def _rerun():
    try:
        _rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass


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


@st.cache_resource
def init_db_once() -> None:
    conn = db_conn()
    cur = conn.cursor()

    # Orgs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orgs (
            team_id TEXT PRIMARY KEY,
            org_name TEXT,
            plan TEXT DEFAULT 'Lite',
            seats_allowed INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            allowed_agents_json TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT
        )
    """
    )

    # Users
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

    # Audit logs
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

    # Core tables (org-scoped tools)
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

    # Reports Vault (store outputs)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reports_vault (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            biz_name TEXT,
            location TEXT,
            agents_json TEXT,
            report_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    # Kanban Leads
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            title TEXT,
            city TEXT,
            service TEXT,
            stage TEXT DEFAULT 'Discovery',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """
    )

    # Dynamic geo table (org-scoped)
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

    # Ensure columns for older DBs
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")
    ensure_column(conn, "orgs", "allowed_agents_json", "TEXT DEFAULT '[]'")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")
    ensure_column(conn, "users", "credits", "INTEGER DEFAULT 10")
    ensure_column(conn, "users", "last_login_at", "TEXT")

    # Seed ROOT org + root user
    cur.execute(
        """
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active', ?)
    """,
        (json.dumps(PLAN_ALLOWED_AGENTS.get("Unlimited", list(AGENT_SPECS.keys()))),),
    )
    root_pw = stauth.Hasher.hash("root123")
    cur.execute(
        """
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """,
        (root_pw,),
    )

    # Seed demo org
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        cur.execute(
            """
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json)
            VALUES ('ORG_001', 'TechNovance Customer', 'Lite', 1, 'active', ?)
        """,
            (json.dumps(PLAN_ALLOWED_AGENTS["Lite"]),),
        )
        admin_pw = stauth.Hasher.hash("admin123")
        cur.execute(
            """
            INSERT OR REPLACE INTO users
            (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES ('admin','admin@customer.ai','Org Admin',?, 'admin',1,'Lite',999,1,'ORG_001')
        """,
            (admin_pw,),
        )

        # Seed some geo rows for demo org
        demo_geo = [
            ("ORG_001", "Illinois", "Chicago"),
            ("ORG_001", "Illinois", "Naperville"),
            ("ORG_001", "Illinois", "Plainfield"),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO geo_locations (team_id, state, city) VALUES (?, ?, ?)",
            demo_geo,
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
                (details or "")[:2000],
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
        return {
            "team_id": team_id,
            "org_name": team_id,
            "plan": "Lite",
            "seats_allowed": 1,
            "status": "active",
            "allowed_agents_json": json.dumps(PLAN_ALLOWED_AGENTS["Lite"]),
        }
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


def agent_limit_by_plan(plan: str) -> int:
    if plan in {"Lite", "Basic"}:
        return 3
    if plan == "Pro":
        return 5
    return 9999


def allowed_agents_for_org(org_row: Dict[str, Any]) -> List[str]:
    raw = org_row.get("allowed_agents_json") or "[]"
    try:
        arr = json.loads(raw) if isinstance(raw, str) else list(raw)
        arr = [str(x).strip() for x in arr if str(x).strip() in AGENT_SPECS]
    except Exception:
        arr = []
    if not arr:
        # fallback to plan
        plan = str(org_row.get("plan", "Lite"))
        arr = [a for a in PLAN_ALLOWED_AGENTS.get(plan, []) if a in AGENT_SPECS]
    # enforce plan max if older DB has too many
    plan_max = agent_limit_by_plan(str(org_row.get("plan", "Lite")))
    if plan_max != 9999 and len(arr) > plan_max:
        arr = arr[:plan_max]
    return arr


def upsert_org(team_id: str, org_name: str, plan: str, status: str = "active", allowed_agents: Optional[List[str]] = None):
    plan = (plan or "Lite").strip()
    status = (status or "active").strip().lower()
    if status not in {"active", "suspended", "trial"}:
        status = "active"

    seats = PLAN_SEATS.get(plan, 1)
    if allowed_agents is None:
        allowed_agents = PLAN_ALLOWED_AGENTS.get(plan, PLAN_ALLOWED_AGENTS["Lite"])
    allowed_agents = [a for a in allowed_agents if a in AGENT_SPECS]

    conn = db_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO orgs (team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at)
        VALUES (
            ?, ?, ?, ?, ?, ?,
            COALESCE((SELECT created_at FROM orgs WHERE team_id=?), datetime('now'))
        )
    """,
        (
            team_id,
            org_name,
            plan,
            int(seats),
            status,
            json.dumps(allowed_agents),
            team_id,
        ),
    )
    conn.commit()
    conn.close()


def create_user(
    team_id: str,
    username: str,
    name: str,
    email: str,
    password_plain: str,
    role: str,
    credits: int = 10,
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

    if not (password_plain or "").strip():
        return False, "Password required."

    hashed = stauth.Hasher.hash(password_plain)
    conn = db_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES (?, ?, ?, ?, ?, 1, (SELECT plan FROM orgs WHERE team_id=?), ?, 1, ?)
        """,
            (username, email, name, hashed, role, team_id, int(credits), team_id),
        )
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()


def delete_user(team_id: str, username: str) -> None:
    if (username or "").lower() == "root":
        return
    conn = db_conn()
    conn.execute("DELETE FROM users WHERE username=? AND team_id=? AND role!='root'", (username, team_id))
    conn.commit()
    conn.close()


def set_user_active(team_id: str, username: str, active: int):
    if (username or "").lower() == "root":
        return
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
    if (username or "").lower() == "root":
        return
    conn = db_conn()
    conn.execute(
        "UPDATE users SET role=? WHERE username=? AND team_id=? AND role!='root'",
        (role, username, team_id),
    )
    conn.commit()
    conn.close()


def update_user_credits(team_id: str, username: str, credits: int):
    if (username or "").lower() == "root":
        return
    conn = db_conn()
    conn.execute(
        "UPDATE users SET credits=? WHERE username=? AND team_id=? AND role!='root'",
        (int(credits), username, team_id),
    )
    conn.commit()
    conn.close()


def reset_user_password(team_id: str, username: str, new_password: str):
    if (username or "").lower() == "root":
        return
    if not (new_password or "").strip():
        return
    hashed = stauth.Hasher.hash(new_password)
    conn = db_conn()
    conn.execute(
        "UPDATE users SET password=? WHERE username=? AND team_id=? AND role!='root'",
        (hashed, username, team_id),
    )
    conn.commit()
    conn.close()


def bulk_import_users(team_id: str, csv_bytes: bytes) -> Tuple[int, List[str]]:
    errors: List[str] = []
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
        cr = int((r.get("credits") or "10") or 10)
        if not u or not pw:
            errors.append(f"Row {i}: missing username or password.")
            continue
        ok, msg = create_user(team_id, u, n, e, pw, ro, credits=cr)
        if ok:
            created += 1
        else:
            errors.append(f"Row {i} ({u}): {msg}")

    return created, errors


def add_geo_location(team_id: str, state: str, city: str) -> Tuple[bool, str]:
    state = (state or "").strip()
    city = (city or "").strip()
    if not state or not city:
        return False, "State and City are required."
    conn = db_conn()
    conn.execute(
        "INSERT INTO geo_locations (team_id, state, city) VALUES (?, ?, ?)",
        (team_id, state, city),
    )
    conn.commit()
    conn.close()
    return True, "Location added."


@st.cache_data(ttl=300)
def get_geo_locations(team_id: str) -> Dict[str, List[str]]:
    conn = db_conn()
    df = pd.read_sql_query(
        "SELECT state, city FROM geo_locations WHERE team_id=? ORDER BY state, city",
        conn,
        params=(team_id,),
    )
    conn.close()

    # fallback defaults if no rows
    if df.empty:
        defaults = {
            "Alabama": ["Birmingham", "Huntsville", "Mobile"],
            "Arizona": ["Phoenix", "Scottsdale", "Tucson"],
            "California": ["Los Angeles", "San Francisco", "San Diego"],
            "Florida": ["Miami", "Orlando", "Tampa"],
            "Illinois": ["Chicago", "Naperville", "Plainfield"],
            "Texas": ["Austin", "Dallas", "Houston"],
        }
        return defaults

    out: Dict[str, List[str]] = {}
    for _, r in df.iterrows():
        out.setdefault(str(r["state"]), []).append(str(r["city"]))
    # de-dupe
    for k in list(out.keys()):
        out[k] = sorted(list(dict.fromkeys(out[k])))
    return out


def save_report_to_vault(team_id: str, report: Dict[str, Any], biz_name: str, location: str, agents: List[str]) -> int:
    conn = db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reports_vault (team_id, biz_name, location, agents_json, report_json)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            team_id,
            biz_name,
            location,
            json.dumps(agents),
            json.dumps(report),
        ),
    )
    conn.commit()
    rid = int(cur.lastrowid or 0)
    conn.close()
    return rid


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
def _get_cookie_secret(key_path: Tuple[str, str], default: str) -> str:
    try:
        outer, inner = key_path
        if outer in st.secrets and inner in st.secrets[outer]:
            val = st.secrets[outer][inner]
            if val:
                return str(val)
    except Exception:
        pass
    return default


def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query("SELECT username, email, name, password FROM users WHERE active=1", conn)
        users = {}
        for _, r in df.iterrows():
            users[str(r["username"])] = {
                "email": r.get("email", "") or "",
                "name": r.get("name", r["username"]) or r["username"],
                "password": r["password"],
            }
        return {"usernames": users}
    finally:
        conn.close()


def build_authenticator():
    cookie_name = _get_cookie_secret(("cookie", "name"), "ms_cookie")
    cookie_key = _get_cookie_secret(("cookie", "key"), "ms_cookie_key_change_me")
    return stauth.Authenticate(get_db_creds(), cookie_name, cookie_key, 30)


if "authenticator" not in st.session_state:
    st.session_state.authenticator = build_authenticator()
authenticator = st.session_state.authenticator


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
      .shell { max-width: 1100px; margin: 0 auto; padding: 30px 14px 60px; }
      .grid { display:grid; grid-template-columns: 1.05fr 0.95fr; gap: 16px; align-items: start; }
      .card { border:1px solid rgba(15,23,42,0.10); border-radius: 18px; background: rgba(255,255,255,0.86);
              box-shadow: 0 24px 60px rgba(2,6,23,0.08); padding: 16px; }
      .badge { font-size:12px; padding: 5px 10px; border-radius: 999px; border:1px solid rgba(99,102,241,0.20);
              background: rgba(99,102,241,0.08); color:#3730a3; display:inline-block; }
      .title { font-size: 46px; font-weight: 850; letter-spacing:-0.02em; margin: 8px 0 10px; color:#0f172a; }
      .sub { color:#334155; font-size:14px; margin:0 0 16px; }
      .pricing { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
      .pricecard { border:1px solid rgba(15,23,42,0.10); border-radius: 16px; padding: 12px; background: rgba(255,255,255,0.95); }
      .price { font-size: 26px; font-weight: 900; }
      .muted { color:#475569; font-size:13px; }
      .li { margin: 0 0 6px; }
      @media (max-width: 980px){
        .grid { grid-template-columns: 1fr; }
        .pricing { grid-template-columns: 1fr; }
        .title{font-size:36px;}
      }
    </style>
    <div class="bg"></div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="shell">', unsafe_allow_html=True)

    # Top header
    ctop1, ctop2 = st.columns([0.12, 0.88], vertical_alignment="center")
    with ctop1:
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=64)
    with ctop2:
        st.markdown('<div class="badge">AI Marketing OS • Secure • Multi‑Tenant</div>', unsafe_allow_html=True)
        st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sub">Campaign ops, governance, agent execution & executive reporting — scoped to your organization.</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="grid">', unsafe_allow_html=True)

    # Left card: product summary + packages
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### What you get")
    st.markdown(
        """
- Org isolation (Team ID)  
- RBAC (Admin / Editor / Viewer)  
- Audit trails (logins, exports, changes)  
- Reports Vault + Kanban leads  
- Executive exports (Word/PDF)  
        """
    )
    st.markdown("### Price Packages")
    st.markdown('<div class="pricing">', unsafe_allow_html=True)
    st.markdown(
        """
      <div class="pricecard">
        <b>🥉 LITE</b><div class="price">$99/mo</div>
        <div class="muted">1 seat • 3 unlocked agents</div>
        <div class="muted" style="margin-top:8px">
          <div class="li">• Analyst</div>
          <div class="li">• Marketing Adviser</div>
          <div class="li">• Strategist</div>
        </div>
      </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
      <div class="pricecard">
        <b>🥈 PRO</b><div class="price">$299/mo</div>
        <div class="muted">5 seats • 5 unlocked agents</div>
        <div class="muted" style="margin-top:8px">
          <div class="li">• Analyst + Adviser + Strategist</div>
          <div class="li">• Ads Architect</div>
          <div class="li">• Creative Director</div>
        </div>
      </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
      <div class="pricecard">
        <b>🥇 ENTERPRISE</b><div class="price">$999/mo</div>
        <div class="muted">20 seats • all agents</div>
        <div class="muted" style="margin-top:8px">
          <div class="li">• Full Swarm (all seats)</div>
          <div class="li">• Reports Vault + tools</div>
          <div class="li">• Priority support</div>
        </div>
      </div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Later: you can move packages to a dedicated landing page and route package → signup automatically.")
    st.markdown('</div>', unsafe_allow_html=True)

    # Right card: auth tabs
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tabs = st.tabs(["🔑 Login", "✨ Create Org & Admin", "💳 Billing (Stripe)", "❓ Forgot Password", "🔄 Refresh Credentials"])

    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state["username"])
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u.get("username")))
            conn.commit()
            conn.close()
            log_audit(u.get("team_id", ""), u.get("username", ""), u.get("role", ""), "auth.login", "user", u.get("username", ""), "login_success")
            _rerun()

    with tabs[1]:
        st.subheader("Create Organization")
        with st.form("org_create_form"):
            team_id = st.text_input("Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
            org_name = st.text_input("Organization Name", placeholder="e.g., Acme Corp")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise"], index=0)
            st.caption("Unlocked agents are auto‑set from the plan. Root can adjust later.")
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
                upsert_org(team_id, org_name, plan, status="active", allowed_agents=PLAN_ALLOWED_AGENTS.get(plan, PLAN_ALLOWED_AGENTS["Lite"]))
                ok, msg = create_user(team_id, admin_username, admin_name, admin_email, admin_password, "admin", credits=50)
                if ok:
                    log_audit(team_id, admin_username, "admin", "org.create", "org", team_id, f"plan={plan}")
                    st.success("Organization created. Use Login tab to sign in.")
                    # Refresh creds so new org admin can log in right away
                    st.session_state.authenticator = build_authenticator()
                else:
                    st.error(msg)

    with tabs[2]:
        st.subheader("Stripe Billing (Scaffold)")
        st.info("Add Stripe secrets + webhook handling later to auto‑upgrade plans and seats.")

    with tabs[3]:
        try:
            authenticator.forgot_password(location="main")
        except Exception:
            st.info("Forgot password is available when SMTP is configured. For now, ask an admin to reset your password.")

    with tabs[4]:
        st.caption("If you created users/orgs and login doesn't recognize them yet, refresh credentials.")
        if st.button("Refresh Now", use_container_width=True):
            st.session_state.authenticator = build_authenticator()
            _toast("✅ Credentials refreshed")
            _rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # card
    st.markdown("</div>", unsafe_allow_html=True)  # grid
    st.markdown("</div>", unsafe_allow_html=True)  # shell
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
allowed_agents = allowed_agents_for_org(org)

# Init session defaults (avoid Streamlit state mutation errors)
st.session_state.setdefault("biz_name", "")
st.session_state.setdefault("directives", "")
st.session_state.setdefault("website_url", "")
st.session_state.setdefault("report", {})
st.session_state.setdefault("gen", False)

# Swarm run-state machine
st.session_state.setdefault("swarm_running", False)
st.session_state.setdefault("swarm_paused", False)
st.session_state.setdefault("swarm_stop", False)
st.session_state.setdefault("swarm_queue", [])
st.session_state.setdefault("swarm_done", [])
st.session_state.setdefault("swarm_started_at", "")
st.session_state.setdefault("swarm_last_agent", "")
st.session_state.setdefault("swarm_next_ready", False)  # between-agent pause point

st.session_state.setdefault("swarm_auto", True)  # auto-run remaining agents (uses soft auto-refresh)
st.session_state.setdefault("swarm_payload", {})  # stored base payload for auto-run steps
st.session_state.setdefault("swarm_autotick_last", "")  # last processed auto-refresh tick

# ============================================================
# SIDEBAR
# ============================================================
def render_sidebar(org_row: Dict[str, Any], allowed: List[str]) -> Dict[str, Any]:
    with st.sidebar:
        if os.path.exists(APP_LOGO_PATH):
            st.image(APP_LOGO_PATH, width=110)

        st.subheader(org_row.get("org_name", "Organization"))
        st.caption(f"Team: `{my_team}` • Role: **{my_role.upper()}**")
        st.metric("Plan", org_plan)
        st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")
        st.markdown(f"<span class='ms-pill'>Unlocked agents: {len(allowed)}/{agent_limit_by_plan(org_plan) if not is_root else '∞'}</span>", unsafe_allow_html=True)
        st.divider()

        biz_name = st.text_input("🏢 Brand Name", value=st.session_state.get("biz_name", ""))
        st.session_state["biz_name"] = biz_name

        custom_logo = st.file_uploader("📤 Brand Logo (All plans)", type=["png", "jpg", "jpeg"])

        # Website URL (needed for audit)
        website_url = st.text_input("🔗 Website URL (for Auditor)", value=st.session_state.get("website_url", ""), placeholder="https://example.com")
        st.session_state["website_url"] = website_url

        # GEO (dynamic)
        geo = get_geo_locations(my_team)

        states_sorted = sorted(geo.keys()) if geo else ["Illinois"]
        if "selected_state" not in st.session_state:
            st.session_state["selected_state"] = states_sorted[0]
        selected_state = st.selectbox("🎯 Target State", states_sorted, index=states_sorted.index(st.session_state["selected_state"]) if st.session_state["selected_state"] in states_sorted else 0)
        st.session_state["selected_state"] = selected_state

        mode = st.radio("City", ["Pick from list", "Add custom"], horizontal=True, index=0)
        city_list = geo.get(selected_state, []) if geo else []
        selected_city = ""
        if mode == "Pick from list":
            if not city_list:
                st.info("No cities found for this state. Add a custom city.")
                selected_city = st.text_input("Target City", value="")
            else:
                if "selected_city" not in st.session_state or st.session_state["selected_city"] not in city_list:
                    st.session_state["selected_city"] = city_list[0]
                selected_city = st.selectbox("🏙️ Target City", city_list, index=city_list.index(st.session_state["selected_city"]) if st.session_state["selected_city"] in city_list else 0)
                st.session_state["selected_city"] = selected_city
        else:
            c_state = st.text_input("State", value=selected_state)
            c_city = st.text_input("City name")
            if st.button("➕ Save location", use_container_width=True):
                ok, msg = add_geo_location(my_team, c_state, c_city)
                if ok:
                    get_geo_locations.clear()
                    _toast("✅ Location added")
                    _rerun()
                else:
                    st.error(msg)
            selected_city = c_city or "City"

        full_loc = f"{selected_city}, {selected_state}".strip(", ")

        st.divider()
        directives = st.text_area("✍️ Strategic Directives", value=st.session_state.get("directives", ""), placeholder="Goals, constraints, tone, offers, budget, etc.")
        st.session_state["directives"] = directives

        # Agent toggles for THIS RUN (unlocked agents only)
        agent_map = [
            ("🕵️ Analyst", "analyst"),
            ("🧭 Marketing Adviser", "marketing_adviser"),
            ("📊 Market Research", "market_researcher"),
            ("🛒 E‑Commerce", "ecommerce_marketer"),
            ("📺 Ads", "ads"),
            ("🎨 Creative", "creative"),
            ("📰 Guest Posting", "guest_posting"),
            ("👔 Strategist", "strategist"),
            ("📱 Social", "social"),
            ("📍 GEO", "geo"),
            ("🌐 Auditor", "audit"),
            ("✍ SEO", "seo"),
        ]

        st.divider()

        # If org is locked, disable toggles for agents not in allowed list.
        with st.expander("🤖 Swarm Personnel", expanded=True):
            st.caption("Toggle which unlocked agents should run now.")
            toggles: Dict[str, bool] = {}
            for label, key in agent_map:
                # set defaults before widget
                st.session_state.setdefault(f"tg_{key}", True if key in allowed else False)
                disabled = (not is_root) and (key not in allowed)
                toggles[key] = st.toggle(label, value=bool(st.session_state.get(f"tg_{key}", False)), key=f"tg_{key}", disabled=disabled)

        # Run controls
        st.divider()

        # Running status block
        if st.session_state.get("swarm_running"):
            st.markdown("### 🟡 Swarm Status")
            q = st.session_state.get("swarm_queue", [])
            done = st.session_state.get("swarm_done", [])
            last = st.session_state.get("swarm_last_agent", "")
            started = st.session_state.get("swarm_started_at", "")
            st.write(f"Started: **{started}**")
            if last:
                st.write(f"Last: **{last}**")
            st.write(f"Done: **{len(done)}** • Remaining: **{len(q)}**")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("⏸ Pause", use_container_width=True, disabled=st.session_state.get("swarm_paused")):
                    st.session_state["swarm_paused"] = True
                    st.session_state["swarm_next_ready"] = True
                    _toast("⏸ Paused (between agents)")
                    _rerun()
            with c2:
                if st.button("▶ Resume", use_container_width=True, disabled=not st.session_state.get("swarm_paused")):
                    st.session_state["swarm_paused"] = False
                    _toast("▶ Resumed")
                    _rerun()

            c3, c4 = st.columns(2)
            with c3:
                if st.button("🛑 Stop after current agent", use_container_width=True):
                    st.session_state["swarm_stop"] = True
                    _toast("🛑 Will stop after current agent")
            with c4:
                if st.button("🧹 Reset run", use_container_width=True):
                    _reset_swarm_state()
                    _toast("🧹 Reset")
                    _rerun()

            st.caption("Stop/Pause take effect **between** agents (Streamlit is synchronous).")
        else:
            run_btn = st.button("🚀 LAUNCH OMNI‑SWARM", type="primary", use_container_width=True)
            st.session_state["run_btn_clicked"] = bool(run_btn)

        authenticator.logout("🔒 Sign Out", "sidebar")

    return {
        "biz_name": biz_name,
        "custom_logo": custom_logo,
        "full_loc": full_loc,
        "directives": directives,
        "toggles": toggles,
        "website_url": website_url,
        "agent_map": agent_map,
    }


def _reset_swarm_state():
    st.session_state["swarm_running"] = False
    st.session_state["swarm_paused"] = False
    st.session_state["swarm_stop"] = False
    st.session_state["swarm_queue"] = []
    st.session_state["swarm_done"] = []
    st.session_state["swarm_started_at"] = ""
    st.session_state["swarm_last_agent"] = ""
    st.session_state["swarm_next_ready"] = False


sidebar_ctx = render_sidebar(org, allowed_agents)
biz_name = sidebar_ctx["biz_name"]
custom_logo = sidebar_ctx["custom_logo"]
full_loc = sidebar_ctx["full_loc"]
directives = sidebar_ctx["directives"]
toggles = sidebar_ctx["toggles"]
agent_map = sidebar_ctx["agent_map"]
website_url = sidebar_ctx["website_url"]

# ============================================================
# RUN SWARM (one agent per step for stop/pause)
# ============================================================
def _is_placeholder(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    bad = [
        "agent not selected for this run",
        "full report not generated",
        "selected, but returned placeholder",
        "placeholder/empty output",
    ]
    return any(b in t for b in bad)


def safe_run_one(agent_key: str, payload: Dict[str, Any]) -> str:
    """Runs ONE agent by calling main.py with active_swarm=[agent_key]."""
    try:
        out = run_marketing_swarm({**payload, "active_swarm": [agent_key]}) or {}
        txt = out.get(agent_key, "") or ""
        return str(txt)
    except Exception as e:
        msg = str(e)
        st.error(f"Swarm error ({agent_key}): {msg}")
        log_audit(my_team, me.get("username", ""), my_role, "swarm.error", "agent", agent_key, msg[:2000])
        return ""


def build_full_report(biz: str, loc: str, plan: str, report: Dict[str, Any]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    def get(k: str) -> str:
        v = report.get(k) or "—"
        return str(v)

    return (
        f"# {biz} Intelligence Report\n"
        f"**Date:** {now} | **Location:** {loc} | **Plan:** {plan}\n"
        f"---\n\n"
        f"## 🕵️ Market Analysis\n{get('analyst')}\n\n"
        f"## 🧭 Marketing Adviser\n{get('marketing_adviser')}\n\n"
        f"## 📊 Market Research\n{get('market_researcher')}\n\n"
        f"## 🛒 E‑Commerce\n{get('ecommerce_marketer')}\n\n"
        f"## 🌐 Website Audit\n{get('audit')}\n\n"
        f"## 👔 Executive Strategy\n{get('strategist')}\n\n"
        f"## 📺 Ads Output\n{get('ads')}\n\n"
        f"## 🎨 Creative Pack\n{get('creative')}\n\n"
        f"## 📰 Guest Posting\n{get('guest_posting')}\n\n"
        f"## ✍️ SEO\n{get('seo')}\n\n"
        f"## 📍 GEO\n{get('geo')}\n\n"
        f"## 📱 Social\n{get('social')}\n"
    )


def start_swarm_run(selected_agents: List[str]):
    # start queue
    st.session_state["swarm_running"] = True
    st.session_state["swarm_paused"] = False
    st.session_state["swarm_stop"] = False
    st.session_state["swarm_queue"] = list(selected_agents)
    st.session_state["swarm_done"] = []
    st.session_state["swarm_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state["swarm_last_agent"] = ""
    st.session_state["swarm_next_ready"] = True  # requires click Continue for next step
    st.session_state["gen"] = False
    st.session_state["report"] = {}
    log_audit(my_team, me.get("username", ""), my_role, "swarm.start", "swarm", biz_name, f"agents={selected_agents}")


def run_next_agent_step(payload: Dict[str, Any]):
    """Runs the next agent from queue (one step)."""
    q: List[str] = st.session_state.get("swarm_queue", [])
    if not q:
        # finalize
        report = st.session_state.get("report") or {}
        report["full_report"] = build_full_report(biz_name, full_loc, org_plan, report)
        st.session_state["report"] = report
        st.session_state["gen"] = True
        st.session_state["swarm_running"] = False
        st.session_state["swarm_next_ready"] = False
        log_audit(my_team, me.get("username", ""), my_role, "swarm.complete", "swarm", biz_name, f"done={st.session_state.get('swarm_done', [])}")
        _toast("✅ Swarm complete")
        return

    agent_key = q[0]

    # If stop was requested, stop before running next agent
    if st.session_state.get("swarm_stop") and st.session_state.get("swarm_done"):
        st.session_state["swarm_running"] = False
        st.session_state["swarm_next_ready"] = False
        _toast("🛑 Stopped")
        log_audit(my_team, me.get("username", ""), my_role, "swarm.stopped", "swarm", biz_name, "stop_requested")
        return

    # Audit URL requirement guard: avoid wasting calls if missing
    if agent_key == "audit" and not (payload.get("url") or "").strip():
        st.session_state.setdefault("report", {})
        st.session_state["report"]["audit"] = "Missing website URL. Add it in the sidebar (Website URL) and run Auditor again."
        st.session_state["swarm_done"] = st.session_state.get("swarm_done", []) + ["audit"]
        st.session_state["swarm_queue"] = q[1:]
        st.session_state["swarm_last_agent"] = "audit"
        _toast("⚠️ Auditor skipped (missing URL)")
        st.session_state["swarm_next_ready"] = True
        return

    with st.status(f"🚀 Running: {agent_key}", expanded=True) as status:
        txt = safe_run_one(agent_key, payload).strip()
        if not txt:
            txt = "Selected, but returned placeholder/empty output. Check provider limits or main.py."
        st.session_state.setdefault("report", {})
        st.session_state["report"][agent_key] = txt
        st.session_state["swarm_done"] = st.session_state.get("swarm_done", []) + [agent_key]
        st.session_state["swarm_queue"] = q[1:]
        st.session_state["swarm_last_agent"] = agent_key
        log_audit(my_team, me.get("username", ""), my_role, "swarm.agent_done", "agent", agent_key, f"len={len(txt)}")
        status.update(label=f"✅ Done: {agent_key}", state="complete", expanded=False)

    _toast(f"✅ {agent_key} finished")
    st.session_state["swarm_next_ready"] = True


# Start run if user clicked Launch
if st.session_state.get("run_btn_clicked"):
    selected = [k for k, v in toggles.items() if bool(v)]
    # Only allow unlocked agents for non-root
    if not is_root:
        selected = [k for k in selected if k in allowed_agents]

    if not biz_name:
        st.error("Enter Brand Name first.")
    elif not selected:
        st.warning("Select at least one unlocked agent.")
    else:
        # Start run and immediately run first agent step
        start_swarm_run(selected)
        payload = {
            "city": full_loc,
            "biz_name": biz_name,
            "package": org_plan,
            "custom_logo": custom_logo,
            "directives": directives,
            "url": website_url,
        }
        run_next_agent_step(payload)
    st.session_state["run_btn_clicked"] = False

# If swarm is running and user clicks Continue
def render_run_banner():
    if not st.session_state.get("swarm_running"):
        return

    q = st.session_state.get("swarm_queue", [])
    done = st.session_state.get("swarm_done", [])
    last = st.session_state.get("swarm_last_agent", "")
    total = len(q) + len(done)
    pct = int((len(done) / total) * 100) if total else 0

    st.markdown(
        f"""
    <div class="ms-banner">
      <div style="display:flex; align-items:center; justify-content:space-between; gap: 12px;">
        <div>
          <div style="font-size:16px; font-weight:800;">🚀 Swarm running</div>
          <div class="ms-muted">Done: <span class="ms-kpi">{len(done)}</span> / {total} • Last: <b>{last or "—"}</b> • Next: <b>{q[0] if q else "finalizing"}</b></div>
        </div>
        <div class="ms-pill">{pct}%</div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    st.write("")


def continue_button(payload: Dict[str, Any]):
    """Shown on every tab so the user can keep browsing while the swarm runs."""
    if not st.session_state.get("swarm_running"):
        return

    # Always show current progress
    queue = st.session_state.get("swarm_queue", []) or []
    completed = st.session_state.get("swarm_completed", []) or []
    total = max(1, len(queue) + len(completed))
    st.progress(min(1.0, len(completed) / total), text=f"Swarm progress: {len(completed)}/{total} complete")

    if st.session_state.get("swarm_stop_requested"):
        st.warning("🛑 Stop requested — the swarm will end after the current agent completes.")
        return

    if st.session_state.get("swarm_paused"):
        st.info("⏸️ Paused. Resume from the sidebar when you're ready.")
        return

    # If we're between agents, either auto-run (soft refresh) or show a manual button
    if st.session_state.get("swarm_next_ready"):
        if st.session_state.get("swarm_auto", True):
            st.info("⚡ Auto-run is ON. Next agent will start shortly (you can Pause/Stop from the sidebar).")
            _schedule_autorun_refresh(delay_ms=1200)
            if st.button("▶️ Run next agent now", key="run_next_now", use_container_width=True):
                run_next_agent_step(st.session_state.get("swarm_payload") or payload)
                _rerun()
        else:
            if st.button("▶️ Run next agent", key="run_next_agent", use_container_width=True):
                run_next_agent_step(st.session_state.get("swarm_payload") or payload)
                _rerun()


# ============================================================
# RENDERERS
# ============================================================
AGENT_GUIDES: Dict[str, List[str]] = {
    "analyst": [
        "Pick 1–2 offers from the pricing gaps and test them on your homepage and ads this week.",
        "Use competitor notes to differentiate messaging (1 headline + 3 proof points).",
        "Turn the top quick wins into a 7‑day sprint checklist.",
    ],
    "marketing_adviser": [
        "Use the channel priority list to decide where to focus budget and time for the next 2 weeks.",
        "Copy the recommended messaging into your website hero, GBP description, and ads.",
    ],
    "market_researcher": [
        "Validate segments by asking 5 prospects the exact questions suggested in the report.",
        "Use insights to refine targeting (age/job/industry/problems) in ads and outreach.",
    ],
    "ecommerce_marketer": [
        "Implement the funnel steps (PDP improvements, email/SMS flows) in order of impact.",
        "Test 1 upsell + 1 cross‑sell offer in checkout this week.",
    ],
    "ads": [
        "Paste Google Search table into your ads manager; launch 1–2 ad groups first.",
        "Rotate hooks weekly and pause variants with low CTR after ~200 impressions.",
    ],
    "creative": [
        "Pick 2 concepts, produce 3–5 creatives each, and A/B test against one control.",
        "Use the prompt pack to generate images, then convert into ad variants.",
    ],
    "guest_posting": [
        "Start with 10 outreach targets; send 3 pitches per site (use the templates).",
        "Track replies in Kanban and log placements into Assets or Vault.",
    ],
    "strategist": [
        "Turn the 30‑day plan into weekly sprints and assign owners.",
        "Track KPIs in your reporting spreadsheet; log key events in Team Intel.",
    ],
    "social": [
        "Schedule the first 7 posts today; reuse winning hooks weekly.",
        "Repurpose top posts into short video + carousel variants.",
    ],
    "geo": [
        "Apply the GBP checklist immediately, then run citations week‑by‑week.",
        "Track ranking changes weekly; refresh photos/posts consistently.",
    ],
    "audit": [
        "Fix high‑impact conversion leaks first (hero, CTA, speed/mobile).",
        "Re‑run audit after changes and compare before/after KPIs.",
    ],
    "seo": [
        "Publish the authority article, then build the suggested cluster posts.",
        "Add FAQ schema and internal links; update content monthly.",
    ],
}


def render_guide():
    render_run_banner()
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: **{st.session_state.get('biz_name','Global Mission')}**")

    # Full report (if generated)
    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report.get("full_report"):
        st.markdown("### 📚 Full Intelligence Report")
        full_txt = st.text_area("Full report (editable)", value=str(report.get("full_report","")), height=380, key="full_report_editor")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("📄 Word", export_word(full_txt, "Full Report"), file_name="full_report.docx", use_container_width=True)
        with c2:
            st.download_button("📕 PDF", export_pdf(full_txt, "Full Report", custom_logo), file_name="full_report.pdf", use_container_width=True)
        with c3:
            if st.button("💾 Save full report to Vault", use_container_width=True):
                selected_agents = [k for k, v in toggles.items() if bool(v)]
                if not is_root:
                    selected_agents = [k for k in selected_agents if k in allowed_agents]
                report["full_report"] = full_txt
                rid = save_report_to_vault(my_team, report, biz_name, full_loc, selected_agents)
                log_audit(my_team, me.get("username",""), my_role, "vault.save", "report", str(rid), f"agents={selected_agents}")
                _toast("✅ Saved")
                _rerun()
        st.markdown("---")

    st.subheader("Agent Specializations")
    for k in AGENT_SPECS.keys():
        st.markdown(AGENT_SPECS[k])

    st.markdown("---")
    st.subheader("🛡️ Swarm Execution Protocol")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")

    st.markdown("---")
    st.subheader("How to implement the reports (quick playbook)")
    st.markdown(
        """
- **Start with Strategy + Adviser**: confirm offer + message + channels.  
- **Then fix blockers**: if running Auditor, apply the top conversion fixes.  
- **Deploy acquisition**: Ads + Creative + Social + GEO.  
- **Scale authority**: SEO + Guest Posting.  
- Save each run to **Reports Vault**, track leads in **Kanban**, iterate weekly.
        """
    )


def render_agent_seat(title: str, key: str):
    render_run_banner()
    st.subheader(f"{title} Seat")
    st.caption(AGENT_SPECS.get(key, ""))

    report = st.session_state.get("report") or {}
    selected_this_run = bool(st.session_state.get(f"tg_{key}", False))
    st.write(f"Selected this run: {'✅ YES' if selected_this_run else '⬜ NO'}")
    if report:
        st.caption(f"Last report keys: {list(report.keys())}")

    # Show special URL reminder for auditor
    if key == "audit" and not st.session_state.get("website_url", "").strip():
        st.warning("Auditor needs a website URL. Add it in the sidebar and run again.")

    out = report.get(key) if st.session_state.get("gen") else report.get(key)
    if out and not _is_placeholder(str(out)):
        edited = st.text_area("Refine Intel", value=str(out), height=420, key=f"ed_{key}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("📄 Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
        with c2:
            st.download_button("📕 PDF", export_pdf(edited, title, custom_logo), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)
        with c3:
            if st.button("💾 Save to Vault", key=f"save_{key}", use_container_width=True):
                vault_report = {key: edited}
                rid = save_report_to_vault(my_team, vault_report, biz_name, full_loc, [key])
                log_audit(my_team, me.get("username",""), my_role, "vault.save", "report", str(rid), f"agent={key}")
                _toast("✅ Saved")

        st.markdown("---")
        st.markdown("#### ✅ How to implement this output")
        for step in AGENT_GUIDES.get(key, ["Apply the recommendations as a checklist."]):
            st.markdown(f"- {step}")

        if key in {"ads", "creative", "social"}:
            st.markdown("---")
            st.markdown("#### 📣 Publish / Push")
            st.text_area("Copy-ready content", value=edited, height=140, key=f"push_{key}")
            cols = st.columns(4)
            for i, (nm, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
                with cols[i % 4]:
                    _link_button(nm, url)

    else:
        if selected_this_run:
            st.markdown(
                "<div class='ms-danger'><b>Selected, but returned placeholder/empty output.</b> "
                "Check provider limits, rate‑limits (429), or main.py agent prompts.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Agent not selected for this run.")

        # Provide a re-run helper
        if selected_this_run and st.button("🔁 Run this agent now", key=f"rerun_{key}", use_container_width=True):
            start_swarm_run([key])
            payload = {
                "city": full_loc,
                "biz_name": biz_name,
                "package": org_plan,
                "custom_logo": custom_logo,
                "directives": directives,
                "url": website_url,
            }
            run_next_agent_step(payload)
            _rerun()


def render_vision():
    render_run_banner()
    st.header("👁️ Vision")
    st.caption("Reserved for future photo/asset analysis workflows.")
    st.info("Vision module is enabled, but no vision pipeline is wired yet.")


def render_veo():
    render_run_banner()
    st.header("🎬 Veo Studio")
    st.caption("Reserved for future video generation workflows.")
    st.info("Veo Studio module is enabled, but no video pipeline is wired yet.")


def render_team_intel():
    render_run_banner()
    st.header("🤝 Team Intel")
    st.caption("Org‑scoped tools for managing your team, leads, and saved reports.")

    users_n = active_user_count(my_team)
    seats = seats_allowed_for_team(my_team)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Users", users_n)
    c2.metric("Seats Allowed", seats)
    c3.metric("Plan", org_plan)
    c4.metric("Credits (you)", int(me.get("credits") or 0))

    intel_tabs = st.tabs(["🗂️ Kanban Leads", "🗄️ Reports Vault", "👥 Users & RBAC", "📣 Campaigns", "🧩 Assets", "🧪 Workflows", "🔌 Integrations", "🔐 Security Logs"])

    # Kanban
    with intel_tabs[0]:
        st.subheader("Kanban Board")
        st.caption("Track leads through stages.")
        stages = ["Discovery", "Execution", "ROI Verified"]

        with st.expander("➕ Add Lead", expanded=True):
            with st.form("lead_add"):
                title = st.text_input("Lead name/title")
                city = st.text_input("City")
                service = st.text_input("Service")
                notes = st.text_area("Notes (optional)", height=90)
                stage = st.selectbox("Stage", stages, index=0)
                submit = st.form_submit_button("Create Lead", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute(
                    "INSERT INTO leads (team_id, title, city, service, stage, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (my_team, title, city, service, stage, notes, datetime.utcnow().isoformat()),
                )
                conn.commit()
                conn.close()
                log_audit(my_team, me.get("username",""), my_role, "lead.create", "lead", title, f"stage={stage}")
                _toast("✅ Lead created")
                _rerun()

        conn = db_conn()
        ldf = pd.read_sql_query(
            "SELECT id, title, city, service, stage, updated_at FROM leads WHERE team_id=? ORDER BY updated_at DESC",
            conn,
            params=(my_team,),
        )
        conn.close()

        if ldf.empty:
            st.info("No leads yet. Add your first lead above.")
        else:
            cols = st.columns(3)
            for i, s in enumerate(stages):
                with cols[i]:
                    st.markdown(f"### {s}")
                    sub = ldf[ldf["stage"] == s]
                    for _, r in sub.iterrows():
                        with st.container(border=True):
                            st.write(f"**{r['title']}**")
                            st.caption(f"{r['city']} • {r['service']}")
                            cA, cB = st.columns(2)
                            with cA:
                                new_stage = st.selectbox("Move to", stages, index=stages.index(s), key=f"mv_{r['id']}")
                            with cB:
                                if st.button("Update", key=f"upd_{r['id']}", use_container_width=True):
                                    conn = db_conn()
                                    conn.execute(
                                        "UPDATE leads SET stage=?, updated_at=? WHERE id=? AND team_id=?",
                                        (new_stage, datetime.utcnow().isoformat(), int(r["id"]), my_team),
                                    )
                                    conn.commit()
                                    conn.close()
                                    log_audit(my_team, me.get("username",""), my_role, "lead.update", "lead", str(r["id"]), f"stage={new_stage}")
                                    _toast("✅ Updated")
                                    _rerun()

    # Vault
    
    # Vault
    with intel_tabs[1]:
        st.subheader("Reports Vault")
        st.caption("Saved swarm runs and individual agent outputs. Use this as your team’s knowledge base.")

        # Save full report from current session
        if st.session_state.get("gen") and st.session_state.get("report"):
            st.markdown("### Save current run")
            selected_agents = [k for k, v in toggles.items() if bool(v)]
            if not is_root:
                selected_agents = [k for k in selected_agents if k in allowed_agents]
            if st.button("💾 Save full run to Vault", use_container_width=True):
                rid = save_report_to_vault(my_team, st.session_state["report"], biz_name, full_loc, selected_agents)
                log_audit(my_team, me.get("username",""), my_role, "vault.save", "report", str(rid), f"agents={selected_agents}")
                _toast("✅ Saved")
                _rerun()
        else:
            st.info("Run the swarm to generate reports, then save here.")

        conn = db_conn()
        vdf = pd.read_sql_query(
            "SELECT id, biz_name, location, agents_json, created_at FROM reports_vault WHERE team_id=? ORDER BY id DESC LIMIT 75",
            conn,
            params=(my_team,),
        )
        conn.close()

        if vdf.empty:
            st.caption("No saved reports yet.")
        else:
            st.dataframe(vdf, width="stretch")

            colA, colB = st.columns([0.35, 0.65])
            with colA:
                rid = st.number_input("Open report ID", min_value=0, step=1, value=0)
                open_btn = st.button("Open report", use_container_width=True)
            with colB:
                st.caption("Tip: Save full runs for end‑to‑end planning. Save individual agent outputs for quick reference.")

            if rid and open_btn:
                conn = db_conn()
                df = pd.read_sql_query(
                    "SELECT id, biz_name, location, agents_json, report_json, created_at FROM reports_vault WHERE team_id=? AND id=?",
                    conn,
                    params=(my_team, int(rid)),
                )
                conn.close()
                if df.empty:
                    st.error("Report not found.")
                else:
                    row = df.iloc[0].to_dict()
                    st.markdown("---")
                    st.markdown(f"## 🗄️ Vault Report #{int(row['id'])}")
                    st.caption(f"Brand: **{row.get('biz_name','')}** • Location: **{row.get('location','')}** • Saved: {row.get('created_at','')}")
                    try:
                        agents_used = json.loads(row.get("agents_json") or "[]")
                    except Exception:
                        agents_used = []
                    st.write("Agents:", ", ".join(agents_used) if agents_used else "—")

                    try:
                        rjson = json.loads(row.get("report_json") or "{}")
                    except Exception:
                        rjson = {}

                    # Build / ensure full report
                    if "full_report" not in rjson:
                        rjson["full_report"] = build_full_report(row.get("biz_name","Brand"), row.get("location",""), org_plan, rjson)

                    st.markdown("### Full report")
                    full_txt = st.text_area("Full report (editable)", value=str(rjson.get("full_report","")), height=360, key=f"vault_full_{rid}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.download_button("📄 Word (Full)", export_word(full_txt, f"Vault Report {rid}"), file_name=f"vault_report_{rid}.docx", use_container_width=True)
                    with c2:
                        st.download_button("📕 PDF (Full)", export_pdf(full_txt, f"Vault Report {rid}", custom_logo), file_name=f"vault_report_{rid}.pdf", use_container_width=True)
                    with c3:
                        if can(my_role, "export") or is_root:
                            if st.button("🔁 Save edited full report back to Vault", use_container_width=True):
                                rjson["full_report"] = full_txt
                                conn = db_conn()
                                conn.execute(
                                    "UPDATE reports_vault SET report_json=? WHERE team_id=? AND id=?",
                                    (json.dumps(rjson), my_team, int(rid)),
                                )
                                conn.commit(); conn.close()
                                log_audit(my_team, me.get("username",""), my_role, "vault.update", "report", str(rid), "full_report_edited")
                                _toast("✅ Updated")
                                _rerun()

                    st.markdown("---")
                    st.markdown("### Agent outputs")
                    keys_sorted = [k for k in AGENT_SPECS.keys() if k in rjson] + [k for k in rjson.keys() if k not in AGENT_SPECS and k != "full_report"]
                    for k in keys_sorted:
                        if k == "full_report":
                            continue
                        with st.expander(f"{k}", expanded=False):
                            st.text_area("Output", value=str(rjson.get(k, "")), height=220, key=f"vault_{rid}_{k}")

                    st.markdown("---")
                    if can(my_role, "export") or is_root:
                        if st.button("🗑️ Delete this vault report", use_container_width=True):
                            conn = db_conn()
                            conn.execute("DELETE FROM reports_vault WHERE team_id=? AND id=?", (my_team, int(rid)))
                            conn.commit(); conn.close()
                            log_audit(my_team, me.get("username",""), my_role, "vault.delete", "report", str(rid), "deleted")
                            _toast("✅ Deleted")
                            _rerun()
        

    # Users & RBAC
    with intel_tabs[2]:
        st.subheader("Users & Access (RBAC)")
        conn = db_conn()
        udf = pd.read_sql_query(
            "SELECT username,name,email,role,active,credits,last_login_at,created_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(udf, width="stretch")

        if can(my_role, "user_manage") or is_root:
            st.markdown("### ➕ Add user")
            with st.form("add_user"):
                u = st.text_input("Username")
                n = st.text_input("Name")
                e = st.text_input("Email")
                r = st.selectbox("Role", ["viewer", "editor", "admin"])
                cr = st.number_input("Credits", min_value=0, value=10, step=1)
                pw = st.text_input("Temp Password", type="password")
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                ok, msg = create_user(my_team, u, n, e, pw, r, credits=int(cr))
                if ok:
                    log_audit(my_team, me.get("username",""), my_role, "user.create", "user", u, f"role={r} credits={cr}")
                    _toast("✅ User created")
                    st.session_state.authenticator = build_authenticator()
                    _rerun()
                else:
                    st.error(msg)

            st.markdown("### 🛠️ Manage user")
            if not udf.empty:
                pick = st.selectbox("Select username", udf["username"].tolist())
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_role = st.selectbox("Role", ["viewer", "editor", "admin"], key="ur_role")
                    if st.button("Update Role", use_container_width=True):
                        update_user_role(my_team, pick, new_role)
                        log_audit(my_team, me.get("username",""), my_role, "user.role_update", "user", pick, f"role={new_role}")
                        _toast("✅ Updated")
                        _rerun()
                with col2:
                    new_cr = st.number_input("Credits", min_value=0, value=int(udf[udf["username"] == pick]["credits"].iloc[0] or 0), step=1, key="ur_credits")
                    if st.button("Update Credits", use_container_width=True):
                        update_user_credits(my_team, pick, int(new_cr))
                        log_audit(my_team, me.get("username",""), my_role, "user.credits_update", "user", pick, f"credits={new_cr}")
                        _toast("✅ Updated")
                        _rerun()
                with col3:
                    active_val = st.selectbox("Active", [1, 0], index=0, key="ur_active")
                    if st.button("Set Active", use_container_width=True):
                        set_user_active(my_team, pick, int(active_val))
                        log_audit(my_team, me.get("username",""), my_role, "user.active_update", "user", pick, f"active={active_val}")
                        _toast("✅ Updated")
                        _rerun()

                st.markdown("### 🔑 Reset password")
                new_pw = st.text_input("New password", type="password", key="pw_reset")
                if st.button("Reset Password", use_container_width=True):
                    reset_user_password(my_team, pick, new_pw)
                    log_audit(my_team, me.get("username",""), my_role, "user.password_reset", "user", pick, "reset")
                    _toast("✅ Reset")
                    st.session_state.authenticator = build_authenticator()
                    _rerun()

                st.markdown("### 🗑️ Delete user")
                if st.button("Delete Selected User", use_container_width=True):
                    delete_user(my_team, pick)
                    log_audit(my_team, me.get("username",""), my_role, "user.delete", "user", pick, "deleted")
                    _toast("✅ Deleted")
                    st.session_state.authenticator = build_authenticator()
                    _rerun()

            st.markdown("### 📥 Bulk import (CSV)")
            st.caption("Headers: username,name,email,role,password,credits • seat limits enforced")
            up = st.file_uploader("Upload CSV", type=["csv"], key="csv_import")
            if up and st.button("Import", use_container_width=True):
                created, errs = bulk_import_users(my_team, up.getvalue())
                log_audit(my_team, me.get("username",""), my_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                if created:
                    st.success(f"Imported {created} user(s).")
                if errs:
                    st.error("Issues:")
                    for x in errs[:15]:
                        st.write(f"- {x}")
                st.session_state.authenticator = build_authenticator()
                _rerun()
        else:
            st.info("Only Admin can manage users.")

    # Campaigns
    with intel_tabs[3]:
        st.subheader("Campaigns")
        conn = db_conn()
        cdf = pd.read_sql_query(
            "SELECT id,name,channel,status,start_date,end_date,created_at FROM campaigns WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(cdf, width="stretch")

        if can(my_role, "campaign_write") or is_root:
            with st.expander("➕ Create campaign", expanded=False):
                with st.form("camp_add"):
                    name = st.text_input("Campaign name")
                    channel = st.text_input("Channel (e.g., Google Ads, Meta, Email)")
                    status = st.selectbox("Status", ["draft", "active", "paused", "completed"], index=0)
                    start = st.text_input("Start date (YYYY-MM-DD)", value="")
                    end = st.text_input("End date (YYYY-MM-DD)", value="")
                    notes = st.text_area("Notes", height=90)
                    submit = st.form_submit_button("Create", use_container_width=True)
                if submit:
                    conn = db_conn()
                    conn.execute(
                        "INSERT INTO campaigns (team_id, name, channel, status, start_date, end_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (my_team, name, channel, status, start, end, notes),
                    )
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me.get("username",""), my_role, "campaign.create", "campaign", name, status)
                    _toast("✅ Created")
                    _rerun()

    # Assets
    with intel_tabs[4]:
        st.subheader("Assets")
        conn = db_conn()
        adf = pd.read_sql_query(
            "SELECT id,name,asset_type,created_at FROM assets WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(adf, width="stretch")

        if can(my_role, "asset_write") or is_root:
            with st.expander("➕ Add asset", expanded=False):
                with st.form("asset_add"):
                    name = st.text_input("Asset name")
                    atype = st.selectbox("Type", ["copy", "creative", "prompt", "link", "doc"], index=0)
                    content = st.text_area("Content", height=140)
                    submit = st.form_submit_button("Save", use_container_width=True)
                if submit:
                    conn = db_conn()
                    conn.execute(
                        "INSERT INTO assets (team_id, name, asset_type, content) VALUES (?, ?, ?, ?)",
                        (my_team, name, atype, content),
                    )
                    conn.commit()
                    conn.close()
                    log_audit(my_team, me.get("username",""), my_role, "asset.create", "asset", name, atype)
                    _toast("✅ Saved")
                    _rerun()

    # Workflows
    with intel_tabs[5]:
        st.subheader("Workflows")
        conn = db_conn()
        wdf = pd.read_sql_query(
            "SELECT id,name,enabled,trigger,created_at FROM workflows WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(wdf, width="stretch")
        st.info("Workflow execution engine is a future sprint; UI scaffolding is ready.")

    # Integrations
    with intel_tabs[6]:
        st.subheader("Integrations")
        conn = db_conn()
        idf = pd.read_sql_query(
            "SELECT id,name,enabled,created_at FROM integrations WHERE team_id=? ORDER BY id DESC",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(idf, width="stretch")
        st.info("Add config_json forms per integration in a future sprint (e.g., HubSpot, Mailchimp, Zapier).")

    # Security logs
    with intel_tabs[7]:
        st.subheader("Security Logs")
        conn = db_conn()
        logs = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 200",
            conn,
            params=(my_team,),
        )
        conn.close()
        st.dataframe(logs, width="stretch")


def render_root_admin():
    render_run_banner()
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend: orgs, users, credits, upgrades, security, site health.")

    tabs = st.tabs(["🏢 Orgs", "👥 Users", "💳 Credits", "🧠 Plan → Auto Agents", "📜 Global Logs", "🩺 Site Health"])

    with tabs[0]:
        conn = db_conn()
        odf = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, allowed_agents_json, created_at FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(odf, width="stretch")

        st.markdown("### Create / Update Org")
        with st.form("root_org_upsert"):
            team_id = st.text_input("Team ID")
            org_name = st.text_input("Org name")
            plan = st.selectbox("Plan", list(PLAN_SEATS.keys()), index=0)
            status = st.selectbox("Status", ["active", "trial", "suspended"], index=0)
            submit = st.form_submit_button("Save Org", use_container_width=True)
        if submit:
            if not team_id.strip():
                st.error("Team ID required.")
            elif team_id.strip().upper() == "ROOT":
                st.error("ROOT reserved. Edit via Plan/Agents tab if needed.")
            else:
                upsert_org(team_id.strip(), org_name.strip() or team_id.strip(), plan, status=status)
                log_audit("ROOT", me.get("username",""), my_role, "root.org_upsert", "org", team_id.strip(), f"plan={plan} status={status}")
                _toast("✅ Saved")
                _rerun()

    with tabs[1]:
        conn = db_conn()
        udf = pd.read_sql_query("SELECT username,name,email,role,active,credits,team_id,created_at,last_login_at FROM users ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(udf, width="stretch")

        st.markdown("### Add user to org")
        with st.form("root_add_user"):
            team_id = st.text_input("Team ID", value="ORG_001")
            username = st.text_input("Username")
            name = st.text_input("Name")
            email = st.text_input("Email")
            role = st.selectbox("Role", ["viewer", "editor", "admin"], index=2)
            credits = st.number_input("Credits", min_value=0, value=50, step=1)
            pw = st.text_input("Temp Password", type="password")
            submit = st.form_submit_button("Create User", use_container_width=True)
        if submit:
            ok, msg = create_user(team_id.strip(), username, name, email, pw, role, credits=int(credits))
            if ok:
                log_audit("ROOT", me.get("username",""), my_role, "root.user_create", "user", username, f"team: {team_id}")
                _toast("✅ Created")
                st.session_state.authenticator = build_authenticator()
                _rerun()
            else:
                st.error(msg)

        st.markdown("### Manage any user")
        pick = st.text_input("Username to manage", value="")
        if pick:
            col1, col2, col3 = st.columns(3)
            with col1:
                new_team = st.text_input("Move to team", value="")
                if st.button("Move Team", use_container_width=True):
                    if pick.lower() != "root":
                        conn = db_conn()
                        conn.execute("UPDATE users SET team_id=? WHERE username=? AND role!='root'", (new_team.strip(), pick.strip()))
                        conn.commit()
                        conn.close()
                        log_audit("ROOT", me.get("username",""), my_role, "root.user_move_team", "user", pick, f"to={new_team}")
                        _toast("✅ Moved")
                        st.session_state.authenticator = build_authenticator()
                        _rerun()
            with col2:
                new_role = st.selectbox("Role", ["viewer","editor","admin"], index=2, key="root_role")
                if st.button("Set Role", use_container_width=True):
                    if pick.lower() != "root":
                        conn = db_conn()
                        conn.execute("UPDATE users SET role=? WHERE username=? AND role!='root'", (new_role, pick.strip()))
                        conn.commit()
                        conn.close()
                        log_audit("ROOT", me.get("username",""), my_role, "root.user_role", "user", pick, new_role)
                        _toast("✅ Updated")
                        st.session_state.authenticator = build_authenticator()
                        _rerun()
            with col3:
                new_active = st.selectbox("Active", [1,0], index=0, key="root_active")
                if st.button("Set Active", use_container_width=True):
                    if pick.lower() != "root":
                        conn = db_conn()
                        conn.execute("UPDATE users SET active=? WHERE username=? AND role!='root'", (int(new_active), pick.strip()))
                        conn.commit()
                        conn.close()
                        log_audit("ROOT", me.get("username",""), my_role, "root.user_active", "user", pick, str(new_active))
                        _toast("✅ Updated")
                        st.session_state.authenticator = build_authenticator()
                        _rerun()

            st.markdown("### Credits + Password")
            c4, c5 = st.columns(2)
            with c4:
                new_cr = st.number_input("Credits", min_value=0, value=50, step=1, key="root_credits")
                if st.button("Update Credits", use_container_width=True):
                    if pick.lower() != "root":
                        conn = db_conn()
                        conn.execute("UPDATE users SET credits=? WHERE username=? AND role!='root'", (int(new_cr), pick.strip()))
                        conn.commit(); conn.close()
                        log_audit("ROOT", me.get("username",""), my_role, "root.user_credits", "user", pick, str(new_cr))
                        _toast("✅ Updated")
                        _rerun()
            with c5:
                npw = st.text_input("New password", type="password", key="root_newpw")
                if st.button("Reset Password", use_container_width=True):
                    if pick.lower() != "root" and npw.strip():
                        hashed = stauth.Hasher.hash(npw)
                        conn = db_conn()
                        conn.execute("UPDATE users SET password=? WHERE username=? AND role!='root'", (hashed, pick.strip()))
                        conn.commit(); conn.close()
                        log_audit("ROOT", me.get("username",""), my_role, "root.user_pw_reset", "user", pick, "reset")
                        _toast("✅ Reset")
                        st.session_state.authenticator = build_authenticator()
                        _rerun()

            st.markdown("### Delete user")
            if st.button("Delete User", use_container_width=True):
                if pick.lower() != "root":
                    conn = db_conn()
                    conn.execute("DELETE FROM users WHERE username=? AND role!='root'", (pick.strip(),))
                    conn.commit(); conn.close()
                    log_audit("ROOT", me.get("username",""), my_role, "root.user_delete", "user", pick, "deleted")
                    _toast("✅ Deleted")
                    st.session_state.authenticator = build_authenticator()
                    _rerun()

    with tabs[2]:
        st.subheader("Credits")
        st.caption("Add or remove credits for any user (non-root).")
        username = st.text_input("Username", value="")
        delta = st.number_input("Delta (+ add, - remove)", value=10, step=1)
        if st.button("Apply", use_container_width=True):
            if username.strip() and username.lower() != "root":
                conn = db_conn()
                cur = conn.cursor()
                cur.execute("SELECT credits FROM users WHERE username=? AND role!='root'", (username.strip(),))
                row = cur.fetchone()
                if row is None:
                    st.error("User not found.")
                else:
                    new_val = max(0, int(row[0] or 0) + int(delta))
                    cur.execute("UPDATE users SET credits=? WHERE username=?", (new_val, username.strip()))
                    conn.commit()
                    log_audit("ROOT", me.get("username",""), my_role, "root.credits_apply", "user", username.strip(), f"delta={delta} new={new_val}")
                    _toast("✅ Applied")
                conn.close()

    with tabs[3]:
        st.subheader("Set plan → auto‑set allowed agents")
        st.caption("This button updates org.plan, org.seats_allowed, and org.allowed_agents_json from plan defaults.")

        conn = db_conn()
        odf = pd.read_sql_query("SELECT team_id, org_name, plan, status FROM orgs ORDER BY team_id", conn)
        conn.close()
        if odf.empty:
            st.info("No orgs.")
        else:
            team = st.selectbox("Select org", odf["team_id"].tolist())
            plan = st.selectbox("New plan", list(PLAN_SEATS.keys()), index=list(PLAN_SEATS.keys()).index("Lite"))
            if st.button("✅ Set plan → auto‑set allowed agents", use_container_width=True):
                org_row = get_org(team)
                allowed = PLAN_ALLOWED_AGENTS.get(plan, PLAN_ALLOWED_AGENTS["Lite"])
                upsert_org(team, org_row.get("org_name", team), plan, status=org_row.get("status", "active"), allowed_agents=allowed)
                log_audit("ROOT", me.get("username",""), my_role, "root.plan_autoset", "org", team, f"plan={plan} agents={allowed}")
                _toast("✅ Updated")
                _rerun()

        st.markdown("---")
        st.subheader("Override allowed agents (advanced)")
        st.caption("Optional: manually override allowed agents list per org.")
        team2 = st.text_input("Team ID (override)", value="")
        if team2:
            current = allowed_agents_for_org(get_org(team2))
            pick_agents = st.multiselect("Allowed agents", list(AGENT_SPECS.keys()), default=current)
            if st.button("Save override", use_container_width=True):
                org_row = get_org(team2)
                upsert_org(team2, org_row.get("org_name", team2), org_row.get("plan", "Lite"), status=org_row.get("status", "active"), allowed_agents=pick_agents)
                log_audit("ROOT", me.get("username",""), my_role, "root.allowed_override", "org", team2, f"agents={pick_agents}")
                _toast("✅ Saved")
                _rerun()

    with tabs[4]:
        st.subheader("Global Logs")
        conn = db_conn()
        gdf = pd.read_sql_query("SELECT timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(gdf, width="stretch")

    with tabs[5]:
        st.subheader("Site Health")
        st.caption("Quick checks for deployment health and config.")
        conn = db_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orgs")
        org_count = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM audit_logs")
        log_count = int(cur.fetchone()[0] or 0)
        conn.close()

        c1, c2, c3 = st.columns(3)
        c1.metric("Orgs", org_count)
        c2.metric("Users", user_count)
        c3.metric("Audit log rows", log_count)

        st.markdown("### Secrets")
        st.write("Cookie name/key loaded:", "✅" if _get_cookie_secret(("cookie","name"), "") else "⚠️ using fallback")
        # Don't print GOOGLE_API_KEY etc

        st.markdown("### Database file")
        st.code(os.path.abspath(DB_PATH))

# ============================================================
# TABS (Main UI)
# ============================================================
agent_tabs = [
    ("🕵️ Analyst", "analyst"),
    ("🧭 Marketing Adviser", "marketing_adviser"),
    ("📊 Market Research", "market_researcher"),
    ("🛒 E‑Commerce", "ecommerce_marketer"),
    ("📺 Ads", "ads"),
    ("🎨 Creative", "creative"),
    ("📰 Guest Posting", "guest_posting"),
    ("👔 Strategist", "strategist"),
    ("📱 Social", "social"),
    ("📍 GEO", "geo"),
    ("🌐 Auditor", "audit"),
    ("✍ SEO", "seo"),
]

tab_labels = ["📖 Guide"] + [t for t, _ in agent_tabs] + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

payload_for_continue = {
    "city": full_loc,
    "biz_name": biz_name,
    "package": org_plan,
    "custom_logo": custom_logo,
    "directives": directives,
    "url": website_url,
}


# ============================================================
# AUTO-RUN REMAINING AGENTS (soft refresh tick)
# ============================================================
if (
    st.session_state.get("swarm_running")
    and st.session_state.get("swarm_auto", True)
    and st.session_state.get("swarm_next_ready")
    and (not st.session_state.get("swarm_paused"))
    and (not st.session_state.get("swarm_stop_requested"))
):
    _tick = _get_query_param("tick", "")
    if _tick and _tick != st.session_state.get("swarm_autotick_last", ""):
        st.session_state["swarm_autotick_last"] = _tick
        run_next_agent_step(st.session_state.get("swarm_payload") or payload_for_continue)
        _rerun()

# Continue button visible on every tab (top) so user can browse while running
with TAB["📖 Guide"]:
    continue_button(payload_for_continue)
    render_guide()

for (title, key) in agent_tabs:
    with TAB[title]:
        continue_button(payload_for_continue)
        render_agent_seat(title, key)

with TAB["👁️ Vision"]:
    continue_button(payload_for_continue)
    render_vision()

with TAB["🎬 Veo Studio"]:
    continue_button(payload_for_continue)
    render_veo()

with TAB["🤝 Team Intel"]:
    continue_button(payload_for_continue)
    render_team_intel()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        continue_button(payload_for_continue)
        render_root_admin()
