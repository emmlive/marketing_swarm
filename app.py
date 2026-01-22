# app.py — Marketing Swarm Intelligence (SaaS-ready, org-isolated, modern login, Team Intel minimal, Root Admin)
import os
import re
import csv
import json
import time
import base64
import sqlite3
import unicodedata
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from docx import Document
from fpdf import FPDF
import fpdf

from main import run_marketing_swarm

# ============================================================
# 0) CONFIG
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")

DB_PATH = "breatheeasy.db"

# Plans: include "Lite" (user-facing) + "Basic/Pro/Enterprise/Unlimited"
PLAN_SEATS = {
    "Lite": 1,
    "Basic": 1,
    "Pro": 5,
    "Enterprise": 20,
    "Unlimited": 9999,  # admin/root fallback
}

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
    "1) **Configure mission** in the sidebar (Brand, Location, Directives).",
    "2) **Select agents** (your plan limits how many can run).",
    "3) Click **LAUNCH OMNI-SWARM**.",
    "4) Review outputs in each **Agent Seat** and refine as needed.",
    "5) Export deliverables as **Word/PDF** and (optionally) use **Social Push** buttons to publish.",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

# ============================================================
# 1) DB HELPERS + SCHEMA
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

    # Organizations (tenants)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orgs (
            team_id TEXT PRIMARY KEY,
            org_name TEXT,
            plan TEXT DEFAULT 'Lite',
            seats_allowed INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT
        )
    """)

    # Users (tenant-scoped; root has team_id='ROOT')
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',         -- viewer/editor/admin/root
            active INTEGER DEFAULT 1,
            plan TEXT DEFAULT 'Lite',
            credits INTEGER DEFAULT 10,
            verified INTEGER DEFAULT 0,
            team_id TEXT DEFAULT 'ORG_001',
            created_at TEXT DEFAULT (datetime('now')),
            last_login_at TEXT
        )
    """)

    # Audit logs (ALWAYS tenant-scoped; root events stored as team_id='ROOT')
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

    # Team Intel objects (tenant-scoped)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            user TEXT,
            city TEXT,
            service TEXT,
            status TEXT DEFAULT 'Discovery',
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            name TEXT,
            channel TEXT,               -- email/social/ads
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
            asset_type TEXT,            -- image/template/copy
            content TEXT,               -- small text or metadata
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
            name TEXT,                  -- Salesforce/HubSpot/GA/Meta etc
            enabled INTEGER DEFAULT 0,
            config_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS kpi_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id TEXT,
            event_type TEXT,            -- lead/conversion/engagement/login/action/export
            value REAL DEFAULT 1,
            metadata_json TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """)

    # Migrations / safety
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")
    ensure_column(conn, "users", "active", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")
    ensure_column(conn, "users", "last_login_at", "TEXT")
    ensure_column(conn, "audit_logs", "team_id", "TEXT")
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")

    # Seed a ROOT org + ROOT user (superuser)
    cur.execute("""
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active')
    """)

    # Root password (change after first login)
    root_pw = stauth.Hasher.hash("root123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES
        ('root', 'root@tech.ai', 'Root Admin', ?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """, (root_pw,))

    # Seed a demo org if none exist besides ROOT
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    n_orgs = int(cur.fetchone()[0] or 0)
    if n_orgs == 0:
        cur.execute("""
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status)
            VALUES ('ORG_001', 'TechNovance Customer', 'Lite', 1, 'active')
        """)
        admin_pw = stauth.Hasher.hash("admin123")
        cur.execute("""
            INSERT OR REPLACE INTO users
            (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES
            ('admin', 'admin@customer.ai', 'Org Admin', ?, 'admin', 1, 'Lite', 999, 1, 'ORG_001')
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
    df = pd.read_sql_query("SELECT * FROM orgs WHERE team_id = ?", conn, params=(team_id,))
    conn.close()
    if df.empty:
        return {"team_id": team_id, "org_name": team_id, "plan": "Lite", "seats_allowed": 1, "status": "active"}
    return df.iloc[0].to_dict()

def get_user(username: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(username,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {}

def get_active_users_count(team_id: str) -> int:
    conn = db_conn()
    df = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM users WHERE team_id = ? AND active = 1 AND role != 'root'",
        conn, params=(team_id,)
    )
    conn.close()
    return int(df.iloc[0]["n"] or 0)

def seats_allowed_for_team(team_id: str) -> int:
    org = get_org(team_id)
    try:
        return int(org.get("seats_allowed") or PLAN_SEATS.get(str(org.get("plan", "Lite")), 1))
    except Exception:
        return 1

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
    role = normalize_role(role)
    perms = PERMISSIONS.get(role, {"read"})
    return "*" in perms or perm in perms or perm == "read"

init_db_once()

# ============================================================
# 2) FPDF HARDENING (keep your patch)
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

def export_pdf(content, title, plan: str, logo_file=None):
    """
    Executive-ready PDF:
    - Includes logo even for Lite (per your requirement).
    - If no logo uploaded, uses a small branded header.
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=14)

        # Header
        pdf.set_font("Arial", "B", 14)
        safe_title = nuclear_ascii(title)

        # Lite: still show logo header (either uploaded or default label)
        if logo_file is not None:
            try:
                # save logo to temp
                logo_bytes = logo_file.getvalue()
                tmp_path = "/tmp/logo.png"
                with open(tmp_path, "wb") as f:
                    f.write(logo_bytes)
                # draw image
                pdf.image(tmp_path, x=10, y=10, w=30)
                pdf.set_xy(45, 12)
            except Exception:
                pdf.set_xy(10, 12)
        else:
            pdf.set_xy(10, 12)

        pdf.cell(0, 8, f"{safe_title}", ln=True)

        pdf.set_font("Arial", size=10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 6, f"Plan: {nuclear_ascii(plan)} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

        # Body
        pdf.set_font("Arial", size=10)
        safe_body = nuclear_ascii(content).replace("\r", "")
        safe_body = "\n".join(line[:900] for line in safe_body.split("\n"))
        pdf.multi_cell(0, 6, safe_body)

        return pdf.output(dest="S").encode("latin-1")
    except Exception:
        fallback = FPDF()
        fallback.add_page()
        fallback.set_font("Arial", size=12)
        fallback.multi_cell(0, 10, "PDF GENERATION FAILED\n\nContent was sanitized.\nError was handled safely.")
        return fallback.output(dest="S").encode("latin-1")

def export_word(content, title):
    doc = Document()
    doc.add_heading(f"Intelligence Brief: {title}", 0)
    doc.add_paragraph(str(content))
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# ============================================================
# 3) AUTH (org isolation + no cross-org visibility)
# ============================================================
def get_db_creds() -> Dict[str, Any]:
    conn = db_conn()
    try:
        df = pd.read_sql_query(
            "SELECT username, email, name, password FROM users WHERE active = 1",
            conn
        )
        # IMPORTANT: Do not leak org membership here; authenticator only needs creds.
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

def upsert_org(team_id: str, org_name: str, plan: str):
    plan = (plan or "Lite").strip()
    seats = int(PLAN_SEATS.get(plan, 1))
    conn = db_conn()
    conn.execute("""
        INSERT OR REPLACE INTO orgs (team_id, org_name, plan, seats_allowed, status, created_at)
        VALUES (?, ?, ?, ?, 'active', COALESCE((SELECT created_at FROM orgs WHERE team_id = ?), datetime('now')))
    """, (team_id, org_name, plan, seats, team_id))
    conn.commit()
    conn.close()

def create_user(team_id: str, username: str, name: str, email: str, password_plain: str, role: str, plan: str) -> Tuple[bool, str]:
    username = (username or "").strip()
    if not username:
        return False, "Username is required."
    if username.lower() == "root":
        return False, "Reserved username."
    role = normalize_role(role)
    if role == "root":
        return False, "Root role cannot be assigned here."

    # Seat enforcement (counts only active non-root users)
    seats = seats_allowed_for_team(team_id)
    active_count = get_active_users_count(team_id)
    if active_count >= seats:
        return False, f"Seat limit reached ({active_count}/{seats}). Upgrade plan to add more users."

    hashed = stauth.Hasher.hash(password_plain)
    conn = db_conn()
    try:
        conn.execute("""
            INSERT INTO users (username, email, name, password, role, active, plan, credits, verified, team_id)
            VALUES (?, ?, ?, ?, ?, 1, ?, 10, 1, ?)
        """, (username, email, name, hashed, role, plan, team_id))
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def set_user_active(team_id: str, username: str, active: int) -> None:
    conn = db_conn()
    conn.execute(
        "UPDATE users SET active = ? WHERE username = ? AND team_id = ? AND role != 'root'",
        (int(active), username, team_id)
    )
    conn.commit()
    conn.close()

def update_user_role(team_id: str, username: str, role: str) -> None:
    role = normalize_role(role)
    if role == "root":
        return
    conn = db_conn()
    conn.execute(
        "UPDATE users SET role = ? WHERE username = ? AND team_id = ? AND role != 'root'",
        (role, username, team_id)
    )
    conn.commit()
    conn.close()

def bulk_import_users(team_id: str, plan: str, csv_bytes: bytes) -> Tuple[int, List[str]]:
    """
    CSV headers expected: username,name,email,role,password
    Enforces seat limit across all imports.
    """
    errors = []
    created = 0

    seats = seats_allowed_for_team(team_id)
    active_count = get_active_users_count(team_id)

    decoded = csv_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(decoded.splitlines())
    rows = list(reader)

    remaining = max(0, seats - active_count)
    if len(rows) > remaining:
        errors.append(f"Seat limit: you can add only {remaining} more user(s) on this plan ({active_count}/{seats}).")
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
        ok, msg = create_user(team_id, u, n, e, pw, ro, plan)
        if ok:
            created += 1
        else:
            errors.append(f"Row {i} ({u}): {msg}")

    return created, errors

# Initialize authenticator ONCE
if "authenticator" not in st.session_state:
    st.session_state.authenticator = stauth.Authenticate(
        get_db_creds(),
        st.secrets["cookie"]["name"],
        st.secrets["cookie"]["key"],
        30
    )
authenticator = st.session_state.authenticator

# ============================================================
# 4) MODERN LOGIN UI (centered, modern, less blinking)
# ============================================================
def inject_login_css():
    st.markdown(
        """
        <style>
        /* Hide Streamlit default header space a bit */
        header[data-testid="stHeader"] { height: 0px; }
        /* Page background */
        .app-bg {
          position: fixed;
          inset: 0;
          background:
            radial-gradient(1200px 500px at 50% 0%, rgba(99,102,241,0.20), rgba(255,255,255,0) 60%),
            radial-gradient(800px 400px at 10% 30%, rgba(16,185,129,0.14), rgba(255,255,255,0) 60%),
            radial-gradient(800px 400px at 90% 30%, rgba(236,72,153,0.12), rgba(255,255,255,0) 60%),
            linear-gradient(180deg, #ffffff 0%, #fbfbff 40%, #ffffff 100%);
          z-index: -1;
        }
        .login-shell {
          max-width: 1100px;
          margin: 0 auto;
          padding: 24px 12px 40px 12px;
        }
        .hero {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 18px;
          align-items: start;
          margin-top: 10px;
        }
        .hero-card {
          border: 1px solid rgba(2,6,23,0.08);
          border-radius: 18px;
          padding: 18px 18px;
          background: rgba(255,255,255,0.72);
          backdrop-filter: blur(10px);
          box-shadow: 0 20px 50px rgba(2,6,23,0.10);
        }
        .brandline {
          display:flex;
          gap:10px;
          align-items:center;
          margin-bottom: 10px;
        }
        .badge {
          font-size: 12px;
          padding: 4px 10px;
          border-radius: 999px;
          background: rgba(99,102,241,0.10);
          color: #3730a3;
          border: 1px solid rgba(99,102,241,0.18);
          display:inline-block;
        }
        .title {
          font-size: 44px;
          line-height: 1.05;
          font-weight: 800;
          margin: 6px 0 6px 0;
          color: #0f172a;
          letter-spacing: -0.02em;
        }
        .subtitle {
          font-size: 14px;
          color: #334155;
          margin-bottom: 14px;
        }
        .grid2 {
          display:grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          margin-top: 10px;
        }
        .feat {
          border: 1px solid rgba(2,6,23,0.08);
          border-radius: 14px;
          padding: 12px;
          background: rgba(255,255,255,0.72);
        }
        .feat b { color: #0f172a; }
        .login-card {
          border: 1px solid rgba(2,6,23,0.08);
          border-radius: 18px;
          padding: 18px 18px 10px 18px;
          background: rgba(255,255,255,0.85);
          backdrop-filter: blur(12px);
          box-shadow: 0 20px 50px rgba(2,6,23,0.10);
        }
        /* Make tab headers look cleaner */
        button[data-baseweb="tab"] {
          font-weight: 600 !important;
        }
        @media (max-width: 980px) {
          .hero { grid-template-columns: 1fr; }
          .title { font-size: 36px; }
        }
        </style>
        <div class="app-bg"></div>
        """,
        unsafe_allow_html=True
    )

def render_login_gate():
    inject_login_css()

    st.markdown('<div class="login-shell">', unsafe_allow_html=True)

    # Top brand row
    c1, c2, c3 = st.columns([1, 6, 1])
    with c1:
        if os.path.exists("Logo1.jpeg"):
            st.image("Logo1.jpeg", width=70)
        else:
            st.markdown("🧠")
    with c2:
        st.markdown('<div class="badge">AI Marketing OS • Secure • Organization-Scoped</div>', unsafe_allow_html=True)
        st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
        st.markdown('<div class="subtitle">Campaign ops, governance, analytics & executive reporting — built for multi-tenant SaaS.</div>', unsafe_allow_html=True)
    with c3:
        st.markdown("")

    st.markdown('<div class="hero">', unsafe_allow_html=True)

    # Left hero content
    st.markdown('<div class="hero-card">', unsafe_allow_html=True)
    st.markdown("#### What you get")
    st.markdown(
        """
        - **Org isolation**: users only see data inside their **Organization (Team ID)**  
        - **RBAC**: Admin / Editor / Viewer roles with feature permissions  
        - **Audit trails**: logins, provisioning, exports, changes  
        - **Executive outputs**: Word/PDF exports (logo included even on **Lite**)  
        """
    )
    st.markdown('<div class="grid2">', unsafe_allow_html=True)
    st.markdown('<div class="feat"><b>Team Intel</b><br/><span style="color:#475569;font-size:13px;">Customer dashboard: users, campaigns, assets, workflows, analytics, logs.</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="feat"><b>Root Admin</b><br/><span style="color:#475569;font-size:13px;">SaaS owner backend: orgs, global users, billing, compliance.</span></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(" ", unsafe_allow_html=True)
    st.info("🔐 **Security note:** In this Streamlit build, SSO/MFA are represented as configuration placeholders. Enforce them at your IdP (Okta/AzureAD/Google Workspace) for production.")
    st.markdown("</div>", unsafe_allow_html=True)

    # Right login card
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    auth_tabs = st.tabs(["🔑 Login", "✨ Create Org & Admin", "💳 Billing (Stripe)", "❓ Forgot Password"])

    with auth_tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            # update last_login_at + audit
            u = get_user(st.session_state.get("username"))
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at = ? WHERE username = ?", (datetime.utcnow().isoformat(), u.get("username")))
            conn.commit()
            conn.close()
            log_audit(u.get("team_id", ""), u.get("username", ""), u.get("role", ""), "auth.login", "user", u.get("username", ""), "login_success")
            st.rerun()

    with auth_tabs[1]:
        st.subheader("Create an Organization")
        with st.form("org_create_form"):
            team_id = st.text_input("Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
            org_name = st.text_input("Organization Name", placeholder="e.g., Acme Corp")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise"], index=0)
            admin_username = st.text_input("Org Admin Username", placeholder="e.g., acme_admin")
            admin_name = st.text_input("Admin Name", placeholder="e.g., Jane Doe")
            admin_email = st.text_input("Admin Email", placeholder="e.g., jane@acme.com")
            admin_password = st.text_input("Admin Password", type="password")
            submitted = st.form_submit_button("Create Org + Admin", use_container_width=True)

        if submitted:
            team_id = (team_id or "").strip()
            if not team_id or not org_name or not admin_username or not admin_password:
                st.error("Please fill required fields: Team ID, Org Name, Admin Username, Admin Password.")
            elif team_id.upper() == "ROOT":
                st.error("ROOT is reserved.")
            else:
                upsert_org(team_id, org_name, plan)
                ok, msg = create_user(team_id, admin_username, admin_name, admin_email, admin_password, "admin", plan)
                if ok:
                    log_audit(team_id, admin_username, "admin", "org.create", "org", team_id, f"plan={plan}")
                    st.success("Organization created. Go to Login tab to sign in.")
                    st.info(f"Seats allowed: {seats_allowed_for_team(team_id)}")
                else:
                    st.error(msg)

    with auth_tabs[2]:
        st.subheader("Billing (Stripe Checkout)")
        st.caption("This tab is a minimal Stripe integration scaffold. Configure price IDs + keys in Streamlit secrets for production.")
        stripe_ready = bool(st.secrets.get("STRIPE_SECRET_KEY")) and bool(st.secrets.get("STRIPE_PRICE_PRO")) and bool(st.secrets.get("STRIPE_PRICE_ENTERPRISE"))
        if not stripe_ready:
            st.warning("Stripe secrets missing. Add: STRIPE_SECRET_KEY, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE, STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL.")
        else:
            try:
                import stripe  # type: ignore
                stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
            except Exception as e:
                st.error(f"Stripe import/config error: {e}")
                stripe = None

            team_id = st.text_input("Your Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
            email = st.text_input("Billing Email", placeholder="billing@company.com")
            target = st.selectbox("Upgrade to", ["Pro", "Enterprise"], index=0)

            if st.button("Create Checkout Session", use_container_width=True, disabled=(stripe is None)):
                price_id = st.secrets["STRIPE_PRICE_PRO"] if target == "Pro" else st.secrets["STRIPE_PRICE_ENTERPRISE"]
                try:
                    session = stripe.checkout.Session.create(
                        mode="subscription",
                        line_items=[{"price": price_id, "quantity": 1}],
                        success_url=st.secrets["STRIPE_SUCCESS_URL"],
                        cancel_url=st.secrets["STRIPE_CANCEL_URL"],
                        customer_email=email if email else None,
                        metadata={"team_id": team_id, "target_plan": target},
                    )
                    st.success("Checkout session created.")
                    st.link_button("Open Stripe Checkout", session.url)
                    st.info("After successful payment, update org plan via webhook in production. This build provides the UI scaffold.")
                except Exception as e:
                    st.error(f"Stripe error: {e}")

    with auth_tabs[3]:
        authenticator.forgot_password(location="main")

    st.markdown("</div>", unsafe_allow_html=True)  # end login-card
    st.markdown("</div>", unsafe_allow_html=True)  # end hero

    st.markdown("</div>", unsafe_allow_html=True)  # end login-shell
    st.stop()

# Gate
if not st.session_state.get("authentication_status"):
    render_login_gate()

# ============================================================
# 5) LOAD USER + ORG CONTEXT (POST-AUTH)
# ============================================================
current_user = get_user(st.session_state["username"])
user_team_id = current_user.get("team_id", "ORG_001")
user_role = normalize_role(current_user.get("role", "viewer"))
is_root = (user_role == "root") or (user_team_id == "ROOT")

# Root sees everything; customers only see their org.
org = get_org(user_team_id)

# ============================================================
# 6) SIDEBAR (dynamic geo + agent toggles + limits)
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

def agent_limit_by_plan(plan: str) -> int:
    plan = (plan or "Lite").strip()
    if plan in {"Lite", "Basic"}:
        return 3
    if plan == "Pro":
        return 5
    return 8

def get_active_agents_count(agent_map, toggles_state: Dict[str, bool]) -> int:
    return sum(1 for _, k in agent_map if toggles_state.get(k, False))

with st.sidebar:
    st.image("Logo1.jpeg", width=110) if os.path.exists("Logo1.jpeg") else None
    st.subheader(f"Welcome, {current_user.get('name', current_user.get('username'))}")
    st.caption(f"Org: **{org.get('org_name','')}**  •  Team ID: `{user_team_id}`")

    # Plan + credits
    current_plan = (org.get("plan") or current_user.get("plan") or "Lite")
    current_credits = int(current_user.get("credits", 0) or 0)

    st.metric("Plan", f"{current_plan}")
    st.metric("Credits", f"{current_credits}")
    st.divider()

    # Mission config
    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp", value=st.session_state.get("biz_name", ""))
    st.session_state["biz_name"] = biz_name

    # Logo rules: per your requirement, Lite ALSO gets logo in executive report
    custom_logo = st.file_uploader("📤 Brand Logo (All Plans)", type=["png", "jpg", "jpeg"])

    # Dynamic geography: choose existing or add custom
    geo_dict = default_geo_data()
    states = sorted(list(geo_dict.keys()))
    state_mode = st.radio("Location Mode", ["Pick from list", "Add custom"], horizontal=True)
    if state_mode == "Pick from list":
        selected_state = st.selectbox("🎯 Target State", states)
        city_mode = st.radio("City Mode", ["Pick from list", "Add custom"], horizontal=True)
        if city_mode == "Pick from list":
            selected_city = st.selectbox("🏙️ Target City", sorted(geo_dict[selected_state]))
        else:
            selected_city = st.text_input("🏙️ Custom City", placeholder="Type city")
    else:
        selected_state = st.text_input("🎯 Custom State", placeholder="Type state")
        selected_city = st.text_input("🏙️ Custom City", placeholder="Type city")

    full_loc = f"{(selected_city or '').strip()}, {(selected_state or '').strip()}".strip(", ").strip()
    if not full_loc:
        full_loc = "USA"

    st.divider()

    agent_info = st.text_area(
        "✍️ Strategic Directives",
        placeholder="Injected into all agent prompts...",
        help="Define constraints like budget, premium positioning, urgency, etc.",
        value=st.session_state.get("agent_info", "")
    )
    st.session_state["agent_info"] = agent_info

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

    plan_agent_limit = 8 if is_root else agent_limit_by_plan(current_plan)

    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Max agents this run: **{plan_agent_limit}**")
        toggles = {}
        # Use previous states if present
        current_toggle_state = {k: bool(st.session_state.get(f"tg_{k}", False)) for _, k in agent_map}
        active_count = get_active_agents_count(agent_map, current_toggle_state)

        for title, key in agent_map:
            is_on = bool(st.session_state.get(f"tg_{key}", False))
            disable_toggle = (not is_root) and (active_count >= plan_agent_limit) and (not is_on)
            default_val = is_on
            # First-time defaults: keep it reasonable
            if f"tg_{key}" not in st.session_state:
                default_val = key in {"analyst", "creative", "strategist"} and active_count < 3
            toggles[key] = st.toggle(title, value=default_val, disabled=disable_toggle, key=f"tg_{key}")

            # refresh count as user toggles
            current_toggle_state[key] = bool(toggles[key])
            active_count = get_active_agents_count(agent_map, current_toggle_state)

        if not is_root and active_count >= plan_agent_limit:
            st.warning("Agent limit reached for your plan.")

    st.divider()

    # Verification gate
    run_btn = False
    if int(current_user.get("verified", 0) or 0) == 1:
        if current_credits > 0 or is_root:
            run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)
        else:
            st.error("💳 Out of credits.")
    else:
        st.error("🛡️ Verification required.")
        if st.button("🔓 One-Click Verify", use_container_width=True):
            conn = db_conn()
            conn.execute("UPDATE users SET verified=1 WHERE username=?", (current_user["username"],))
            conn.commit()
            conn.close()
            log_audit(user_team_id, current_user["username"], user_role, "user.verify", "user", current_user["username"], "one_click_verify")
            st.rerun()

    authenticator.logout("🔒 Sign Out", "sidebar")

# ============================================================
# 7) RUN SWARM (with safe error capture)
# ============================================================
def safe_run_swarm(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return run_marketing_swarm(payload) or {}
    except Exception as e:
        # If upstream (Gemini) rate-limits, show friendly info
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            st.error("LLM quota/rate limit hit (429). Try again in a bit or reduce agents per run.")
        else:
            st.error(f"Swarm error: {e}")
        log_audit(user_team_id, current_user["username"], user_role, "swarm.error", "swarm", "", msg[:4000])
        return {}

if run_btn:
    if not biz_name:
        st.error("🚨 Please enter a Brand Name before launching.")
    else:
        active_agents = [k for k, v in toggles.items() if v]
        if not active_agents:
            st.warning("Select at least one agent.")
        else:
            with st.status("🚀 Initializing Swarm Intelligence...", expanded=True) as status:
                st.write(f"📡 Dispatching {len(active_agents)} agent(s) for **{biz_name}** in **{full_loc}**")

                # Persist mission to session (for Guide display)
                st.session_state["biz_name"] = biz_name

                report = safe_run_swarm({
                    "city": full_loc,
                    "biz_name": biz_name,
                    "active_swarm": active_agents,
                    "package": current_plan,
                    "custom_logo": custom_logo,
                    "directives": agent_info
                })

                if report:
                    st.session_state.report = report
                    st.session_state.gen = True
                    log_audit(user_team_id, current_user["username"], user_role, "swarm.run", "swarm", biz_name, f"agents={active_agents}")
                    # Usage analytics
                    conn = db_conn()
                    conn.execute(
                        "INSERT INTO kpi_events (team_id, event_type, value, metadata_json) VALUES (?, ?, ?, ?)",
                        (user_team_id, "swarm_run", 1, json.dumps({"agents": active_agents, "biz": biz_name}))
                    )
                    conn.commit()
                    conn.close()

                    status.update(label="✅ Swarm Coordination Complete!", state="complete", expanded=False)
                else:
                    status.update(label="⚠️ Swarm did not return output.", state="error", expanded=True)

            st.rerun()

# ============================================================
# 8) DASHBOARD RENDERERS
# ============================================================
def show_deploy_guide(title: str, key: str):
    guide = {
        "analyst": "Identify price gaps and competitor fatigue.",
        "ads": "Convert insights into platform-ready ad structures.",
        "creative": "Produce creative directions, hooks, ad variants and prompt packs.",
        "strategist": "Turn everything into a 30-day execution roadmap.",
        "social": "Write posts + calendar that match the brand voice.",
        "geo": "Local dominance plan for maps + citations.",
        "audit": "Fix conversion friction and technical leaks.",
        "seo": "Publish authority content for SGE and clusters.",
    }.get(key, "Execute mission output.")
    st.markdown(
        f"""
        <div style="background-color:#f0f2f6; padding:14px; border-radius:12px;
                    border-left: 5px solid #2563EB; margin-bottom: 14px;">
            <b style="color:#0f172a;">🚀 {title.upper()} DEPLOYMENT GUIDE</b><br>
            <span style="color:#334155;">{guide}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_guide():
    st.header("📖 Agent Intelligence Manual")
    st.info(f"Command Center Active for: **{st.session_state.get('biz_name', 'Global Mission')}**")

    st.subheader("Agent Specializations")
    for _, desc in AGENT_SPECS.items():
        st.markdown(desc)

    st.markdown("---")
    st.subheader("🛡️ Swarm Execution Protocol")
    for line in DEPLOY_PROTOCOL:
        st.markdown(f"- {line}")

def social_push_panel(content: str, key: str):
    """
    Push panel is intentionally safe:
    - We provide "copy to clipboard" UX and open official publisher consoles.
    - Actual API posting requires OAuth + app review (done outside Streamlit).
    """
    st.markdown("#### 📣 Social Push")
    st.caption("Copy your finalized output and publish via your connected platform console.")
    st.text_area("Copy-ready content", value=str(content), height=140, key=f"push_copy_{key}")

    cols = st.columns(4)
    for i, (name, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
        with cols[i % 4]:
            st.link_button(name, url)

def render_agent_seat(title: str, key: str, plan: str, logo_file):
    st.subheader(f"🚀 {title} Seat")
    show_deploy_guide(title, key)

    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report:
        content = report.get(key)
        if content:
            edited = st.text_area("Refine Intel", value=str(content), height=420, key=f"ed_{key}")
            c1, c2, c3 = st.columns([1, 1, 1])

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
                    export_pdf(edited, title, plan=plan, logo_file=logo_file),
                    file_name=f"{key}.pdf",
                    key=f"p_{key}",
                    use_container_width=True
                )

            with c3:
                if can(user_role, "export") or is_root or user_role in {"admin", "editor"}:
                    # Log export intent (download is client-side, so we log button display + user action context)
                    if st.button("🧾 Log Export", use_container_width=True, key=f"log_export_{key}"):
                        log_audit(user_team_id, current_user["username"], user_role, "export.request", "seat", key, "export_logged")
                        conn = db_conn()
                        conn.execute(
                            "INSERT INTO kpi_events (team_id, event_type, value, metadata_json) VALUES (?, ?, ?, ?)",
                            (user_team_id, "export", 1, json.dumps({"seat": key}))
                        )
                        conn.commit()
                        conn.close()
                        st.success("Export logged.")

            # Social push appears where relevant
            if key in {"creative", "ads", "social"}:
                st.markdown("---")
                social_push_panel(edited, key)

        else:
            st.warning("Agent not selected for this run (or no output returned).")
    else:
        st.info("System standby. Launch from the sidebar.")

def render_vision():
    st.header("👁️ Visual Intelligence")
    st.write("Visual audits and image analysis results appear here.")

def render_veo():
    st.header("🎬 Veo Studio")
    st.write("AI video generation assets appear here.")

# ============================================================
# 9) TEAM INTEL (CUSTOMER DASHBOARD — MINIMAL + ORG-SCOPED)
# ============================================================
def team_intel_stats(team_id: str) -> Dict[str, int]:
    conn = db_conn()
    users_n = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM users WHERE team_id = ? AND active = 1 AND role != 'root'",
        conn, params=(team_id,)
    ).iloc[0]["n"]
    camps_n = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM campaigns WHERE team_id = ?",
        conn, params=(team_id,)
    ).iloc[0]["n"]
    assets_n = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM assets WHERE team_id = ?",
        conn, params=(team_id,)
    ).iloc[0]["n"]
    wf_n = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM workflows WHERE team_id = ? AND enabled = 1",
        conn, params=(team_id,)
    ).iloc[0]["n"]
    leads_n = pd.read_sql_query(
        "SELECT COUNT(*) AS n FROM leads WHERE team_id = ?",
        conn, params=(team_id,)
    ).iloc[0]["n"]
    conn.close()
    return {
        "Active Users": int(users_n or 0),
        "Campaigns": int(camps_n or 0),
        "Assets": int(assets_n or 0),
        "Enabled Workflows": int(wf_n or 0),
        "Leads": int(leads_n or 0),
    }

def render_team_intel_customer():
    st.header("🤝 Team Intel")
    st.caption("Organization-scoped SaaS dashboard. Data is restricted to your Organization (Team ID).")

    stats = team_intel_stats(user_team_id)
    cols = st.columns(5)
    for i, (k, v) in enumerate(stats.items()):
        cols[i].metric(k, v)

    st.markdown("---")

    sub_tabs = st.tabs(["👥 User & Access (RBAC)", "📣 Campaigns", "🧩 Assets", "🧠 Workflows", "🔌 Integrations", "📈 Analytics", "🔐 Security & Logs"])

    # --- User & Access (RBAC) ---
    with sub_tabs[0]:
        st.subheader("User & Access Management (RBAC)")
        st.caption("Admins can provision users up to seat limits. Editors can manage content. Viewers are read-only.")

        org_plan = str(org.get("plan", "Lite"))
        seats_allowed = seats_allowed_for_team(user_team_id)
        active_users = get_active_users_count(user_team_id)
        st.info(f"Plan: **{org_plan}**  •  Seats: **{active_users}/{seats_allowed}**")

        # List users (org-scoped; never show ROOT users)
        conn = db_conn()
        users_df = pd.read_sql_query(
            "SELECT username, name, email, role, active, created_at, last_login_at FROM users WHERE team_id = ? AND role != 'root' ORDER BY created_at DESC",
            conn, params=(user_team_id,)
        )
        conn.close()
        st.dataframe(users_df, width="stretch")

        if not can(user_role, "user_manage") and not is_root:
            st.warning("You don't have permission to manage users.")
        else:
            st.markdown("### ➕ Add a user")
            with st.form("add_user_form"):
                nu = st.text_input("Username")
                nn = st.text_input("Name")
                ne = st.text_input("Email")
                nr = st.selectbox("Role", ["viewer", "editor", "admin"], index=0)
                npw = st.text_input("Temporary Password", type="password")
                submit = st.form_submit_button("Create User", use_container_width=True)

            if submit:
                ok, msg = create_user(user_team_id, nu, nn, ne, npw, nr, org_plan)
                if ok:
                    log_audit(user_team_id, current_user["username"], user_role, "user.create", "user", nu, f"role={nr}")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            st.markdown("### 🔁 Activate/Deactivate user")
            ulist = users_df["username"].tolist() if not users_df.empty else []
            if ulist:
                sel = st.selectbox("Select user", ulist, key="ua_sel")
                colA, colB, colC = st.columns([1, 1, 1])
                with colA:
                    if st.button("Deactivate", use_container_width=True):
                        set_user_active(user_team_id, sel, 0)
                        log_audit(user_team_id, current_user["username"], user_role, "user.deactivate", "user", sel, "")
                        st.rerun()
                with colB:
                    if st.button("Activate", use_container_width=True):
                        # activating doesn't increase seats beyond limit; still allowed because it was previously a seat.
                        # If you want strict enforcement on reactivation, uncomment check below.
                        # if get_active_users_count(user_team_id) >= seats_allowed_for_team(user_team_id):
                        #     st.error("Seat limit reached. Deactivate another user or upgrade plan.")
                        # else:
                        set_user_active(user_team_id, sel, 1)
                        log_audit(user_team_id, current_user["username"], user_role, "user.activate", "user", sel, "")
                        st.rerun()
                with colC:
                    new_role = st.selectbox("Change role to", ["viewer", "editor", "admin"], key="ua_role")
                    if st.button("Update Role", use_container_width=True):
                        update_user_role(user_team_id, sel, new_role)
                        log_audit(user_team_id, current_user["username"], user_role, "user.role_update", "user", sel, f"role={new_role}")
                        st.rerun()
            else:
                st.info("No users in this organization yet.")

            st.markdown("### 📥 Bulk import users (CSV)")
            st.caption("CSV headers: username,name,email,role,password — seat limits enforced for the whole import.")
            csv_file = st.file_uploader("Upload CSV", type=["csv"], key="bulk_csv")
            if csv_file is not None:
                if st.button("Import Users", use_container_width=True):
                    created, errs = bulk_import_users(user_team_id, org_plan, csv_file.getvalue())
                    log_audit(user_team_id, current_user["username"], user_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                    if created:
                        st.success(f"Imported {created} user(s).")
                    if errs:
                        st.error("Import issues:")
                        for e in errs[:15]:
                            st.write(f"- {e}")
                    st.rerun()

        st.markdown("---")
        st.subheader("SSO / MFA (Configuration Placeholders)")
        st.info("For production SaaS, enforce SSO+MFA via Okta/AzureAD/Google Workspace. This Streamlit build provides placeholders and logs only.")

    # --- Campaigns ---
    with sub_tabs[1]:
        st.subheader("Campaign Management")
        st.caption("Create, schedule, manage and track multi-channel campaigns (email/social/ads).")

        conn = db_conn()
        camp_df = pd.read_sql_query(
            "SELECT id, name, channel, status, start_date, end_date, notes, created_at FROM campaigns WHERE team_id = ? ORDER BY id DESC",
            conn, params=(user_team_id,)
        )
        conn.close()
        st.dataframe(camp_df, width="stretch")

        if can(user_role, "campaign_write") or is_root:
            with st.form("camp_form"):
                name = st.text_input("Campaign name")
                channel = st.selectbox("Channel", ["email", "social", "ads"])
                status = st.selectbox("Status", ["draft", "scheduled", "running", "paused", "completed"], index=0)
                start = st.date_input("Start date", value=None)
                end = st.date_input("End date", value=None)
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Create Campaign", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("""
                    INSERT INTO campaigns (team_id, name, channel, status, start_date, end_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_team_id, name, channel, status, str(start) if start else None, str(end) if end else None, notes))
                conn.commit()
                conn.close()
                log_audit(user_team_id, current_user["username"], user_role, "campaign.create", "campaign", name, f"channel={channel}")
                st.success("Campaign created.")
                st.rerun()
        else:
            st.info("You have read-only access.")

    # --- Assets ---
    with sub_tabs[2]:
        st.subheader("Content & Asset Library")
        st.caption("Centralized storage for marketing assets (images/templates/copy).")

        conn = db_conn()
        assets_df = pd.read_sql_query(
            "SELECT id, name, asset_type, created_at FROM assets WHERE team_id = ? ORDER BY id DESC",
            conn, params=(user_team_id,)
        )
        conn.close()
        st.dataframe(assets_df, width="stretch")

        if can(user_role, "asset_write") or is_root:
            with st.form("asset_form"):
                aname = st.text_input("Asset name")
                atype = st.selectbox("Asset type", ["image", "template", "copy"])
                acontent = st.text_area("Content / Notes (small text)")
                submit = st.form_submit_button("Save Asset", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute(
                    "INSERT INTO assets (team_id, name, asset_type, content) VALUES (?, ?, ?, ?)",
                    (user_team_id, aname, atype, acontent)
                )
                conn.commit()
                conn.close()
                log_audit(user_team_id, current_user["username"], user_role, "asset.create", "asset", aname, f"type={atype}")
                st.success("Asset saved.")
                st.rerun()

    # --- Workflows ---
    with sub_tabs[3]:
        st.subheader("Automation & Workflows")
        st.caption("Automated sequences for nurturing, approvals, data syncing (basic scaffold).")

        conn = db_conn()
        wf_df = pd.read_sql_query(
            "SELECT id, name, enabled, trigger, created_at FROM workflows WHERE team_id = ? ORDER BY id DESC",
            conn, params=(user_team_id,)
        )
        conn.close()
        st.dataframe(wf_df, width="stretch")

        if can(user_role, "workflow_write") or is_root:
            with st.form("wf_form"):
                wname = st.text_input("Workflow name")
                trig = st.selectbox("Trigger", ["lead.created", "campaign.scheduled", "export.logged", "manual"])
                steps = st.text_area("Steps (JSON or bullets)")
                submit = st.form_submit_button("Create Workflow", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute(
                    "INSERT INTO workflows (team_id, name, enabled, trigger, steps) VALUES (?, ?, 0, ?, ?)",
                    (user_team_id, wname, trig, steps)
                )
                conn.commit()
                conn.close()
                log_audit(user_team_id, current_user["username"], user_role, "workflow.create", "workflow", wname, f"trigger={trig}")
                st.success("Workflow created.")
                st.rerun()

            if not wf_df.empty:
                sel_id = st.selectbox("Select workflow ID to toggle", wf_df["id"].tolist())
                if st.button("Toggle Enabled", use_container_width=True):
                    conn = db_conn()
                    cur = conn.cursor()
                    cur.execute("SELECT enabled FROM workflows WHERE id = ? AND team_id = ?", (int(sel_id), user_team_id))
                    row = cur.fetchone()
                    if row:
                        new_val = 0 if int(row[0] or 0) == 1 else 1
                        conn.execute("UPDATE workflows SET enabled = ? WHERE id = ? AND team_id = ?", (new_val, int(sel_id), user_team_id))
                        conn.commit()
                        log_audit(user_team_id, current_user["username"], user_role, "workflow.toggle", "workflow", str(sel_id), f"enabled={new_val}")
                    conn.close()
                    st.rerun()

    # --- Integrations ---
    with sub_tabs[4]:
        st.subheader("Integrations")
        st.caption("Connect CRM/analytics/social tools (config scaffold).")
        conn = db_conn()
        int_df = pd.read_sql_query(
            "SELECT id, name, enabled, created_at FROM integrations WHERE team_id = ? ORDER BY id DESC",
            conn, params=(user_team_id,)
        )
        conn.close()
        st.dataframe(int_df, width="stretch")

        if can(user_role, "workflow_write") or is_root:
            with st.form("int_form"):
                iname = st.selectbox("Integration", ["Salesforce", "HubSpot", "Google Analytics", "Meta", "Zapier/Webhook"])
                enabled = st.checkbox("Enabled", value=False)
                cfg = st.text_area("Config JSON (optional)")
                submit = st.form_submit_button("Save Integration", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute(
                    "INSERT INTO integrations (team_id, name, enabled, config_json) VALUES (?, ?, ?, ?)",
                    (user_team_id, iname, 1 if enabled else 0, cfg)
                )
                conn.commit()
                conn.close()
                log_audit(user_team_id, current_user["username"], user_role, "integration.save", "integration", iname, f"enabled={enabled}")
                st.success("Integration saved.")
                st.rerun()

    # --- Analytics ---
    with sub_tabs[5]:
        st.subheader("Analytics & Reporting")
        st.caption("Key KPIs + usage analytics (basic charts/table scaffold).")

        conn = db_conn()
        kpi_df = pd.read_sql_query(
            "SELECT timestamp, event_type, value, metadata_json FROM kpi_events WHERE team_id = ? ORDER BY id DESC LIMIT 200",
            conn, params=(user_team_id,)
        )
        conn.close()
        if kpi_df.empty:
            st.info("No analytics events yet.")
        else:
            st.dataframe(kpi_df, width="stretch")

            # Simple rollups
            roll = kpi_df.groupby("event_type")["value"].sum().reset_index().sort_values("value", ascending=False)
            st.markdown("#### KPI Rollup")
            st.dataframe(roll, width="stretch")

    # --- Security & Logs (ORG-SCOPED ONLY) ---
    with sub_tabs[6]:
        st.subheader("Security & Compliance")
        st.caption("Audit trails + monitoring. (SSO/MFA placeholders in this Streamlit build.)")

        conn = db_conn()
        # IMPORTANT: customer sees ONLY their team_id logs (no root logs)
        logs_df = pd.read_sql_query(
            """
            SELECT timestamp, actor, action_type, object_type, object_id, details
            FROM audit_logs
            WHERE team_id = ?
            ORDER BY id DESC
            LIMIT 200
            """,
            conn, params=(user_team_id,)
        )
        conn.close()

        st.dataframe(logs_df, width="stretch")
        st.info("SSO/MFA are placeholders in this Streamlit build. For real SaaS, enforce SSO+MFA at the IdP.")

# ============================================================
# 10) ROOT ADMIN (SaaS OWNER BACKEND — SUPERUSER)
# ============================================================
def render_root_admin():
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend. Root can manage orgs, global users, billing, and compliance.")

    tabs = st.tabs(["🏢 Organizations", "👥 Global Users", "📜 Compliance Logs", "💳 Billing", "⚙️ System"])

    with tabs[0]:
        st.subheader("Organizations")
        conn = db_conn()
        org_df = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, created_at FROM orgs WHERE team_id != 'ROOT' ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(org_df, width="stretch")

        st.markdown("### Create / Update org")
        with st.form("root_org_form"):
            team_id = st.text_input("Team ID")
            org_name = st.text_input("Org name")
            plan = st.selectbox("Plan", ["Lite", "Pro", "Enterprise"], index=0)
            status = st.selectbox("Status", ["active", "suspended"], index=0)
            submit = st.form_submit_button("Save", use_container_width=True)
        if submit:
            upsert_org(team_id, org_name, plan)
            conn = db_conn()
            conn.execute("UPDATE orgs SET status = ? WHERE team_id = ?", (status, team_id))
            conn.commit()
            conn.close()
            log_audit("ROOT", current_user["username"], user_role, "root.org_save", "org", team_id, f"plan={plan} status={status}")
            st.success("Org saved.")
            st.rerun()

    with tabs[1]:
        st.subheader("Global Users")
        conn = db_conn()
        udf = pd.read_sql_query(
            "SELECT username, name, email, role, active, team_id, created_at, last_login_at FROM users ORDER BY created_at DESC",
            conn
        )
        conn.close()
        st.dataframe(udf, width="stretch")

        st.markdown("### Force deactivate user (safety)")
        sel = st.selectbox("Select username", udf["username"].tolist() if not udf.empty else [])
        if st.button("Deactivate", use_container_width=True, disabled=(not sel)):
            conn = db_conn()
            conn.execute("UPDATE users SET active = 0 WHERE username = ? AND role != 'root'", (sel,))
            conn.commit()
            conn.close()
            log_audit("ROOT", current_user["username"], user_role, "root.user_deactivate", "user", sel, "")
            st.success("User deactivated.")
            st.rerun()

    with tabs[2]:
        st.subheader("Compliance Logs (All Tenants)")
        conn = db_conn()
        logs = pd.read_sql_query(
            "SELECT timestamp, team_id, actor, actor_role, action_type, object_type, object_id, details FROM audit_logs ORDER BY id DESC LIMIT 500",
            conn
        )
        conn.close()
        st.dataframe(logs, width="stretch")

    with tabs[3]:
        st.subheader("Billing")
        st.caption("Stripe webhook automation is recommended for real SaaS. This panel is an operator view scaffold.")
        conn = db_conn()
        bill_df = pd.read_sql_query(
            "SELECT team_id, org_name, plan, seats_allowed, stripe_customer_id, stripe_subscription_id, status FROM orgs WHERE team_id != 'ROOT' ORDER BY created_at DESC",
            conn
        )
        conn.close()
        st.dataframe(bill_df, width="stretch")

    with tabs[4]:
        st.subheader("System")
        st.info("Root login: `root` / `root123` (change password in production).")
        st.caption("This build keeps org isolation by filtering Team Intel data by team_id and keeping root logs in ROOT scope unless you intentionally view global logs here.")

# ============================================================
# 11) TAB BUILD (Guide + Agent Seats + Team Intel + Root Admin)
# ============================================================
agent_titles = [a[0] for a in agent_map]
tab_labels = ["📖 Guide"] + agent_titles + ["👁️ Vision", "🎬 Veo Studio", "🤝 Team Intel"]
if is_root:
    tab_labels.append("🛡️ Admin")

tabs_obj = st.tabs(tab_labels)
TAB = {name: tabs_obj[i] for i, name in enumerate(tab_labels)}

with TAB["📖 Guide"]:
    render_guide()

for (title, key) in agent_map:
    with TAB[title]:
        # IMPORTANT: we pass current plan + logo for executive-ready exports
        render_agent_seat(title, key, plan=current_plan, logo_file=custom_logo)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel_customer()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
