import os
import re
import csv
import json
import time
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
# SETTINGS
# ============================================================
st.set_page_config(page_title="Marketing Swarm Intelligence", layout="wide")
DB_PATH = "breatheeasy.db"
APP_LOGO_PATH = "Logo1.jpeg"

# Set True when you deploy outside Streamlit Cloud (or want less chrome).
# NOTE: This cannot remove Streamlit Cloud overlays like “Share” / “Manage app”.
PRODUCTION_MODE = True

PLAN_SEATS = {
    "Lite": 1,
    "Basic": 1,
    "Pro": 5,
    "Enterprise": 20,
    "Unlimited": 9999,
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
    "5) Export deliverables as **Word/PDF** and publish using your platform console.",
]

SOCIAL_PUSH_PLATFORMS = [
    ("Google Business Profile", "https://business.google.com/"),
    ("Meta Business Suite (FB/IG)", "https://business.facebook.com/"),
    ("LinkedIn Company Page", "https://www.linkedin.com/company/"),
    ("X (Twitter)", "https://twitter.com/compose/tweet"),
]

# ============================================================
# UI CHROME / CSS
# ============================================================
def inject_global_css():
    if st.session_state.get("_css_loaded"):
        return
    st.session_state["_css_loaded"] = True

    # Hide Streamlit chrome (not Streamlit Cloud overlays)
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

      /* Cleaner sidebar */
      [data-testid="stSidebar"] {{
        border-right: 1px solid rgba(15,23,42,0.08);
      }}

      /* Reduce accidental object repr rendering */
      pre, code {{ display:none; }}

      /* Make tabs tighter */
      .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}

      /* Smooth cards */
      .card {{
        border: 1px solid rgba(15,23,42,0.10);
        border-radius: 18px;
        background: rgba(255,255,255,0.85);
        box-shadow: 0 20px 60px rgba(2,6,23,0.08);
        padding: 16px;
      }}
    </style>
    """, unsafe_allow_html=True)

inject_global_css()

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
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            password TEXT,
            role TEXT DEFAULT 'viewer',       -- viewer/editor/admin/root
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

    # Migrations
    ensure_column(conn, "orgs", "seats_allowed", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "role", "TEXT DEFAULT 'viewer'")
    ensure_column(conn, "users", "active", "INTEGER DEFAULT 1")
    ensure_column(conn, "users", "team_id", "TEXT DEFAULT 'ORG_001'")

    # Seed ROOT org + root user
    cur.execute("""
        INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status)
        VALUES ('ROOT', 'SaaS Root', 'Unlimited', 9999, 'active')
    """)
    root_pw = stauth.Hasher.hash("root123")
    cur.execute("""
        INSERT OR REPLACE INTO users
        (username, email, name, password, role, active, plan, credits, verified, team_id)
        VALUES ('root','root@tech.ai','Root Admin',?, 'root', 1, 'Unlimited', 9999, 1, 'ROOT')
    """, (root_pw,))

    # Seed demo org
    cur.execute("SELECT COUNT(*) FROM orgs WHERE team_id != 'ROOT'")
    if int(cur.fetchone()[0] or 0) == 0:
        cur.execute("""
            INSERT OR IGNORE INTO orgs (team_id, org_name, plan, seats_allowed, status)
            VALUES ('ORG_001','TechNovance Customer','Lite',1,'active')
        """)
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
    df = pd.read_sql_query("SELECT * FROM orgs WHERE team_id = ?", conn, params=(team_id,))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else {"team_id": team_id, "org_name": team_id, "plan": "Lite", "seats_allowed": 1}

def get_user(username: str) -> Dict[str, Any]:
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM users WHERE username = ?", conn, params=(username,))
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

PERMISSIONS = {
    "viewer": {"read"},
    "editor": {"read", "campaign_write", "asset_write", "workflow_write"},
    "admin": {"read", "campaign_write", "asset_write", "workflow_write", "user_manage", "export"},
    "root": {"*"},
}
def can(role: str, perm: str) -> bool:
    perms = PERMISSIONS.get(normalize_role(role), {"read"})
    return ("*" in perms) or (perm in perms) or (perm == "read")

def upsert_org(team_id: str, org_name: str, plan: str):
    plan = (plan or "Lite").strip()
    seats = PLAN_SEATS.get(plan, 1)
    conn = db_conn()
    conn.execute("""
        INSERT OR REPLACE INTO orgs (team_id, org_name, plan, seats_allowed, status, created_at)
        VALUES (?, ?, ?, ?, 'active', COALESCE((SELECT created_at FROM orgs WHERE team_id = ?), datetime('now')))
    """, (team_id, org_name, plan, seats, team_id))
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

def bulk_import_users(team_id: str, csv_bytes: bytes) -> Tuple[int, List[str]]:
    # headers: username,name,email,role,password
    errors = []
    created = 0
    seats = seats_allowed_for_team(team_id)
    used = active_user_count(team_id)
    remaining = max(0, seats - used)

    decoded = csv_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(decoded.splitlines())
    rows = list(reader)

    if len(rows) > remaining:
        errors.append(f"Seat limit: you can add only {remaining} more user(s) ({used}/{seats}). Extra rows ignored.")
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

init_db_once()

# ============================================================
# 2) PDF HARDENING
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
    """
    Executive-ready PDF:
    - Always includes a logo (uploaded if provided, else Logo1.jpeg if present)
    """
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=14)

        # Logo
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

        safe_body = nuclear_ascii(content).replace("\r", "")
        safe_body = "\n".join(line[:900] for line in safe_body.split("\n"))
        pdf.multi_cell(0, 6, safe_body)

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
                    "email": r.get("email",""),
                    "name": r.get("name", r["username"]),
                    "password": r["password"]
                } for _, r in df.iterrows()
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

# ============================================================
# LOGIN PAGE (Futuristic + Pricing Packages restored)
# ============================================================
def login_page():
    st.markdown("""
    <style>
      [data-testid="stSidebar"] { display: none; }  /* hide sidebar on login */
      .bg {
        position: fixed; inset: 0;
        background:
          radial-gradient(1200px 600px at 50% 0%, rgba(99,102,241,0.20), transparent 60%),
          radial-gradient(900px 500px at 10% 30%, rgba(16,185,129,0.16), transparent 60%),
          radial-gradient(900px 500px at 90% 30%, rgba(236,72,153,0.14), transparent 60%),
          linear-gradient(180deg, #ffffff 0%, #fafafe 60%, #ffffff 100%);
        z-index: -1;
      }
      .shell { max-width: 1120px; margin: 0 auto; padding: 26px 12px 50px; }
      .top { display:flex; align-items:center; gap: 14px; }
      .badge { font-size:12px; padding: 5px 10px; border-radius: 999px; border:1px solid rgba(99,102,241,0.20); background: rgba(99,102,241,0.08); color:#3730a3; }
      .title { font-size: 46px; font-weight: 850; letter-spacing:-0.02em; margin: 6px 0 8px; color:#0f172a; }
      .sub { color:#334155; font-size:14px; margin:0 0 16px; }
      .grid { display:grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; }
      .card { border:1px solid rgba(15,23,42,0.10); border-radius: 18px; background: rgba(255,255,255,0.82); box-shadow: 0 24px 60px rgba(2,6,23,0.08); padding: 16px; }
      .kpis { display:grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin-top: 10px; }
      .kpi { border:1px solid rgba(15,23,42,0.08); border-radius: 14px; padding: 12px; background: rgba(255,255,255,0.9); }
      .kpi b { color:#0f172a; }
      .kpi span { color:#475569; font-size:12px; }
      .pricing { display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
      .pricecard { border:1px solid rgba(15,23,42,0.10); border-radius: 16px; padding: 12px; background: rgba(255,255,255,0.92); }
      .price { font-size: 26px; font-weight: 900; }
      @media (max-width: 980px){ .grid { grid-template-columns: 1fr; } .pricing { grid-template-columns: 1fr; } .title{font-size:36px;} }
    </style>
    <div class="bg"></div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="shell">', unsafe_allow_html=True)

    # Header
    st.markdown('<div class="top">', unsafe_allow_html=True)
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=64)
    st.markdown('<div class="badge">AI Marketing OS • Secure • Multi-Tenant</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="title">Marketing Swarm Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub">Modern SaaS for campaign ops, governance, analytics & executive reporting — organization-scoped.</div>', unsafe_allow_html=True)

    st.markdown('<div class="grid">', unsafe_allow_html=True)

    # Left: Value + Pricing Packages (restored)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### What you get")
    st.markdown("""
- Org isolation: users only see data inside their Organization (Team ID)  
- RBAC: Admin / Editor / Viewer roles with permissions  
- Audit trails: logins, provisioning, exports, changes  
- Executive outputs: Word/PDF exports (**logo supported for all plans**)  
""")

    st.markdown("### Price Packages")
    st.markdown('<div class="pricing">', unsafe_allow_html=True)
    st.markdown("""
      <div class="pricecard">
        <b>🥉 LITE</b><div class="price">$99/mo</div>
        <div style="color:#475569;font-size:13px;">1 seat • up to 3 agents • exports</div>
      </div>
    """, unsafe_allow_html=True)
    st.markdown("""
      <div class="pricecard">
        <b>🥈 PRO</b><div class="price">$299/mo</div>
        <div style="color:#475569;font-size:13px;">5 seats • up to 5 agents • Team Intel</div>
      </div>
    """, unsafe_allow_html=True)
    st.markdown("""
      <div class="pricecard">
        <b>🥇 ENTERPRISE</b><div class="price">$999/mo</div>
        <div style="color:#475569;font-size:13px;">20 seats • up to 8 agents • Integrations</div>
      </div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Right: Auth tabs
    st.markdown('<div class="card">', unsafe_allow_html=True)
    tabs = st.tabs(["🔑 Login", "✨ Create Org & Admin", "💳 Billing (Stripe)", "❓ Forgot Password"])

    with tabs[0]:
        authenticator.login(location="main")
        if st.session_state.get("authentication_status"):
            u = get_user(st.session_state.get("username"))
            conn = db_conn()
            conn.execute("UPDATE users SET last_login_at=? WHERE username=?", (datetime.utcnow().isoformat(), u["username"]))
            conn.commit()
            conn.close()
            log_audit(u["team_id"], u["username"], u["role"], "auth.login", "user", u["username"], "login_success")
            st.rerun()

    with tabs[1]:
        st.subheader("Create Organization")
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
                st.error("Team ID, Org Name, Admin Username, Admin Password are required.")
            elif team_id.upper() == "ROOT":
                st.error("ROOT is reserved.")
            else:
                upsert_org(team_id, org_name, plan)
                ok, msg = create_user(team_id, admin_username, admin_name, admin_email, admin_password, "admin")
                if ok:
                    log_audit(team_id, admin_username, "admin", "org.create", "org", team_id, f"plan={plan}")
                    st.success("Organization created. Use Login tab to sign in.")
                    st.info(f"Seats allowed: {seats_allowed_for_team(team_id)}")
                else:
                    st.error(msg)

    with tabs[2]:
        st.subheader("Stripe Billing")
        st.caption("Scaffold. For production, use Stripe webhooks to update plan + seats automatically.")
        stripe_ready = bool(st.secrets.get("STRIPE_SECRET_KEY")) and bool(st.secrets.get("STRIPE_PRICE_PRO")) and bool(st.secrets.get("STRIPE_PRICE_ENTERPRISE"))
        if not stripe_ready:
            st.warning("Add secrets: STRIPE_SECRET_KEY, STRIPE_PRICE_PRO, STRIPE_PRICE_ENTERPRISE, STRIPE_SUCCESS_URL, STRIPE_CANCEL_URL")
        else:
            try:
                import stripe  # type: ignore
                stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
                team_id = st.text_input("Your Organization (Team ID)", placeholder="e.g., ORG_ACME_2026")
                email = st.text_input("Billing Email", placeholder="billing@company.com")
                target = st.selectbox("Upgrade to", ["Pro", "Enterprise"], index=0)

                if st.button("Create Checkout Session", use_container_width=True):
                    price_id = st.secrets["STRIPE_PRICE_PRO"] if target == "Pro" else st.secrets["STRIPE_PRICE_ENTERPRISE"]
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
                    st.info("After payment, update org plan via webhook (recommended).")
            except Exception as e:
                st.error(f"Stripe error: {e}")

    with tabs[3]:
        authenticator.forgot_password(location="main")

    st.markdown('</div>', unsafe_allow_html=True)  # end auth card
    st.markdown('</div>', unsafe_allow_html=True)  # end grid
    st.markdown('</div>', unsafe_allow_html=True)  # end shell
    st.stop()

# Gate
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

# ============================================================
# SIDEBAR (fix: NO inline expression printing)
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

with st.sidebar:
    # ✅ FIXED: no more DeltaGenerator output
    if os.path.exists(APP_LOGO_PATH):
        st.image(APP_LOGO_PATH, width=110)

    st.subheader(f"{org.get('org_name','Organization')}")
    st.caption(f"Team ID: `{my_team}`  •  Role: **{my_role.upper()}**")
    st.metric("Plan", org_plan)
    st.metric("Seats", f"{active_user_count(my_team)}/{seats_allowed_for_team(my_team)}")
    st.divider()

    biz_name = st.text_input("🏢 Brand Name", placeholder="Acme Corp", value=st.session_state.get("biz_name", ""))
    st.session_state["biz_name"] = biz_name

    # Logo upload (all plans)
    custom_logo = st.file_uploader("📤 Brand Logo (All plans)", type=["png","jpg","jpeg"])

    geo = default_geo_data()
    state_mode = st.radio("Location Mode", ["Pick from list", "Add custom"], horizontal=True)
    if state_mode == "Pick from list":
        selected_state = st.selectbox("🎯 Target State", sorted(geo.keys()))
        city_mode = st.radio("City Mode", ["Pick from list", "Add custom"], horizontal=True)
        if city_mode == "Pick from list":
            selected_city = st.selectbox("🏙️ Target City", sorted(geo[selected_state]))
        else:
            selected_city = st.text_input("🏙️ Custom City")
    else:
        selected_state = st.text_input("🎯 Custom State")
        selected_city = st.text_input("🏙️ Custom City")

    full_loc = f"{(selected_city or '').strip()}, {(selected_state or '').strip()}".strip(", ").strip() or "USA"

    st.divider()
    directives = st.text_area("✍️ Strategic Directives", value=st.session_state.get("directives",""), placeholder="Injected into prompts…")
    st.session_state["directives"] = directives

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

    limit = 8 if is_root else agent_limit_by_plan(org_plan)

    with st.expander("🤖 Swarm Personnel", expanded=True):
        st.caption(f"Max agents: {limit}")
        toggles = {}
        active = 0
        for t, k in agent_map:
            is_on = bool(st.session_state.get(f"tg_{k}", False))
            toggles[k] = st.toggle(t, value=is_on, key=f"tg_{k}")
        active = sum(1 for v in toggles.values() if v)
        if not is_root and active > limit:
            st.warning(f"Selected {active}. Limit is {limit}. Turn some off.")

    st.divider()
    run_btn = st.button("🚀 LAUNCH OMNI-SWARM", type="primary", use_container_width=True)

    authenticator.logout("🔒 Sign Out", "sidebar")

# ============================================================
# RUN SWARM
# ============================================================
def safe_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return run_marketing_swarm(payload) or {}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            st.error("Rate limit hit (429). Try again shortly or select fewer agents.")
        else:
            st.error(f"Swarm error: {e}")
        log_audit(my_team, me["username"], my_role, "swarm.error", "swarm", "", msg[:2000])
        return {}

if run_btn:
    agents = [k for k, v in toggles.items() if v]
    if not biz_name:
        st.error("Enter Brand Name first.")
    elif not agents:
        st.warning("Select at least one agent.")
    else:
        with st.status("🚀 Running Swarm…", expanded=True) as status:
            report = safe_run({
                "city": full_loc,
                "biz_name": biz_name,
                "active_swarm": agents,
                "package": org_plan,
                "custom_logo": custom_logo,
                "directives": directives,
            })
            if report:
                st.session_state["report"] = report
                st.session_state["gen"] = True
                log_audit(my_team, me["username"], my_role, "swarm.run", "swarm", biz_name, f"agents={agents}")
                status.update(label="✅ Complete", state="complete", expanded=False)
            else:
                st.session_state["gen"] = False
                status.update(label="⚠️ No output returned", state="error", expanded=True)
        st.rerun()

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

def render_agent_seat(title: str, key: str):
    st.subheader(f"{title} Seat")
    st.caption(AGENT_SPECS.get(key, ""))

    report = st.session_state.get("report") or {}
    if st.session_state.get("gen") and report.get(key):
        edited = st.text_area("Refine Intel", value=str(report.get(key)), height=420, key=f"ed_{key}")

        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📄 Word", export_word(edited, title), file_name=f"{key}.docx", key=f"w_{key}", use_container_width=True)
        with c2:
            st.download_button("📕 PDF", export_pdf(edited, title, custom_logo), file_name=f"{key}.pdf", key=f"p_{key}", use_container_width=True)

        if key in {"ads","creative","social"}:
            st.markdown("---")
            st.markdown("#### 📣 Publish / Push")
            st.text_area("Copy-ready content", value=edited, height=140, key=f"push_{key}")
            cols = st.columns(4)
            for i, (nm, url) in enumerate(SOCIAL_PUSH_PLATFORMS):
                with cols[i % 4]:
                    st.link_button(nm, url)

    else:
        st.info("Agent not selected for this run.")

def render_team_intel_minimal():
    st.header("🤝 Team Intel")
    st.caption("Customer dashboard (org-scoped). Root backend is separate and hidden from customers.")

    # Stats
    conn = db_conn()
    users_n = pd.read_sql_query("SELECT COUNT(*) AS n FROM users WHERE team_id=? AND active=1 AND role!='root'", conn, params=(my_team,)).iloc[0]["n"]
    camps_n = pd.read_sql_query("SELECT COUNT(*) AS n FROM campaigns WHERE team_id=?", conn, params=(my_team,)).iloc[0]["n"]
    assets_n = pd.read_sql_query("SELECT COUNT(*) AS n FROM assets WHERE team_id=?", conn, params=(my_team,)).iloc[0]["n"]
    wf_n = pd.read_sql_query("SELECT COUNT(*) AS n FROM workflows WHERE team_id=? AND enabled=1", conn, params=(my_team,)).iloc[0]["n"]
    conn.close()

    a,b,c,d = st.columns(4)
    a.metric("Active Users", int(users_n or 0))
    b.metric("Campaigns", int(camps_n or 0))
    c.metric("Assets", int(assets_n or 0))
    d.metric("Enabled Workflows", int(wf_n or 0))

    tabs = st.tabs(["👥 User & Access", "📣 Campaigns", "🧩 Assets", "🧠 Workflows", "🔐 Security"])

    # User & Access (seat limits)
    with tabs[0]:
        st.subheader("User & Access (RBAC)")
        seats = seats_allowed_for_team(my_team)
        used = active_user_count(my_team)
        st.info(f"Plan: **{org_plan}** • Seats: **{used}/{seats}**")

        conn = db_conn()
        udf = pd.read_sql_query("SELECT username,name,email,role,active,last_login_at FROM users WHERE team_id=? AND role!='root' ORDER BY created_at DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(udf, width="stretch")

        if can(my_role, "user_manage") or is_root:
            st.markdown("### ➕ Add user")
            with st.form("add_user"):
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

            st.markdown("### 📥 Bulk import (CSV)")
            st.caption("Headers: username,name,email,role,password • seat limits enforced")
            up = st.file_uploader("Upload CSV", type=["csv"])
            if up and st.button("Import", use_container_width=True):
                created, errs = bulk_import_users(my_team, up.getvalue())
                log_audit(my_team, me["username"], my_role, "user.bulk_import", "user", "", f"created={created} errs={len(errs)}")
                if created: st.success(f"Imported {created} user(s).")
                if errs:
                    st.error("Issues:")
                    for x in errs[:15]:
                        st.write(f"- {x}")
                st.rerun()
        else:
            st.info("Only Admin can manage users.")

    # Campaigns
    with tabs[1]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,channel,status,created_at FROM campaigns WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch")
        if can(my_role, "campaign_write") or is_root:
            with st.form("camp"):
                nm = st.text_input("Campaign name")
                ch = st.selectbox("Channel", ["email","social","ads"])
                stt = st.selectbox("Status", ["draft","scheduled","running","paused","completed"])
                notes = st.text_area("Notes")
                submit = st.form_submit_button("Create", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("INSERT INTO campaigns (team_id,name,channel,status,notes) VALUES (?,?,?,?,?)", (my_team,nm,ch,stt,notes))
                conn.commit(); conn.close()
                log_audit(my_team, me["username"], my_role, "campaign.create", "campaign", nm, f"channel={ch}")
                st.success("Campaign created."); st.rerun()

    # Assets
    with tabs[2]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,asset_type,created_at FROM assets WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch")
        if can(my_role, "asset_write") or is_root:
            with st.form("asset"):
                nm = st.text_input("Asset name")
                tp = st.selectbox("Type", ["image","template","copy"])
                ct = st.text_area("Content/Notes")
                submit = st.form_submit_button("Save", use_container_width=True)
            if submit:
                conn = db_conn()
                conn.execute("INSERT INTO assets (team_id,name,asset_type,content) VALUES (?,?,?,?)", (my_team,nm,tp,ct))
                conn.commit(); conn.close()
                log_audit(my_team, me["username"], my_role, "asset.create", "asset", nm, f"type={tp}")
                st.success("Saved."); st.rerun()

    # Workflows
    with tabs[3]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT id,name,enabled,trigger,created_at FROM workflows WHERE team_id=? ORDER BY id DESC", conn, params=(my_team,))
        conn.close()
        st.dataframe(df, width="stretch")

    # Security (org logs only)
    with tabs[4]:
        conn = db_conn()
        logs = pd.read_sql_query(
            "SELECT timestamp, actor, action_type, object_type, object_id, details FROM audit_logs WHERE team_id=? ORDER BY id DESC LIMIT 200",
            conn, params=(my_team,)
        )
        conn.close()
        st.dataframe(logs, width="stretch")

def render_root_admin():
    st.header("🛡️ Root Admin")
    st.caption("SaaS owner backend. Only root can see global orgs/users/logs.")

    tabs = st.tabs(["🏢 Orgs", "👥 Users", "📜 Logs", "💳 Billing"])

    with tabs[0]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT team_id, org_name, plan, seats_allowed, status, created_at FROM orgs ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, width="stretch")

    with tabs[1]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT username,name,email,role,active,team_id,created_at,last_login_at FROM users ORDER BY created_at DESC", conn)
        conn.close()
        st.dataframe(df, width="stretch")

    with tabs[2]:
        conn = db_conn()
        df = pd.read_sql_query("SELECT timestamp,team_id,actor,actor_role,action_type,object_type,object_id,details FROM audit_logs ORDER BY id DESC LIMIT 500", conn)
        conn.close()
        st.dataframe(df, width="stretch")

    with tabs[3]:
        st.info("Stripe webhook automation recommended to update org plan/seats after purchase.")

# ============================================================
# TABS
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
        render_agent_seat(title, key)

with TAB["👁️ Vision"]:
    render_vision()

with TAB["🎬 Veo Studio"]:
    render_veo()

with TAB["🤝 Team Intel"]:
    render_team_intel_minimal()

if "🛡️ Admin" in TAB:
    with TAB["🛡️ Admin"]:
        render_root_admin()
