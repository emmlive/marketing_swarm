import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from pydantic import BaseModel
from dotenv import load_dotenv

import streamlit as st

from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# ============================================================
# ENV / SECRETS
# ============================================================
load_dotenv(override=True)

def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Streamlit secrets first, then environment variables."""
    try:
        if hasattr(st, "secrets") and name in st.secrets and st.secrets[name]:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.getenv(name, default)

def _is_429(err: Exception) -> bool:
    msg = str(err)
    return ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg)

def kickoff_with_retry(crew: Crew, retries: int = 2, base_sleep: int = 15):
    """Retry Crew kickoff on common Gemini/GCP 429 rate-limit errors."""
    for attempt in range(retries + 1):
        try:
            return crew.kickoff()
        except Exception as e:
            if _is_429(e) and attempt < retries:
                wait = base_sleep * (attempt + 1)
                try:
                    st.warning(f"⚠️ Rate limited (429). Retrying in {wait}s...")
                except Exception:
                    pass
                time.sleep(wait)
                continue
            raise

# ============================================================
# TOGGLES (must match app.py keys)
# ============================================================
TOGGLE_KEYS = {
    "analyst",
    "ads",
    "creative",
    "strategist",
    "social",
    "geo",
    "audit",
    "seo",
    "marketing_adviser",
    "ecommerce_marketer",
    "guest_posting",
    "market_researcher",
    "gbp_growth",  # ✅ NEW
}

# ============================================================
# STATE
# ============================================================
class SwarmState(BaseModel):
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Outputs (map to app keys)
    analyst: str = "Agent not selected for this run."
    ads: str = "Agent not selected for this run."
    creative: str = "Agent not selected for this run."
    strategist: str = "Agent not selected for this run."
    audit: str = "Agent not selected for this run."
    seo: str = "Agent not selected for this run."
    social: str = "Agent not selected for this run."
    geo: str = "Agent not selected for this run."

    marketing_adviser: str = "Agent not selected for this run."
    ecommerce_marketer: str = "Agent not selected for this run."
    guest_posting: str = "Agent not selected for this run."
    market_researcher: str = "Agent not selected for this run."

    gbp_growth: str = "Agent not selected for this run."  # ✅ NEW

    full_report: str = "Full report not generated."

# ============================================================
# LLM + TOOLS
# ============================================================
GOOGLE_API_KEY = (
    _get_secret("GOOGLE_API_KEY")
    or _get_secret("GEMINI_API_KEY")
    or _get_secret("GENAI_API_KEY")
)
SERPER_API_KEY = _get_secret("SERPER_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY in Streamlit secrets or environment variables.")

gemini_llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,
    temperature=0.2,  # lower = less hallucination
)

scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(api_key=SERPER_API_KEY) if SERPER_API_KEY else None

SAFETY_INSTRUCTIONS = (
    "Important rules:\n"
    "- Do NOT invent facts, citations, customer counts, revenue, market share, or performance metrics.\n"
    "- If data is missing, say what you would need and give a conservative, assumption-based plan.\n"
    "- If you use web search results, summarize them and note uncertainty.\n"
    "- Prefer concise, executive-ready bullets. Avoid long essays.\n"
)

# ============================================================
# AGENTS
# ============================================================
def get_swarm_agents(inputs: Dict[str, Any]) -> Dict[str, Agent]:
    biz = inputs.get("biz_name", "The Business")
    city = inputs.get("city", "the local area")
    url = (inputs.get("url") or inputs.get("website") or "").strip()
    directives = inputs.get("directives") or "Standard growth optimization."

    research_tools = [scrape_tool]
    if search_tool:
        research_tools = [search_tool, scrape_tool]

    return {
        "market_researcher": Agent(
            role="Market Researcher",
            goal=f"Produce an executive market research snapshot for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nDirectives: {directives}\nUse search/scrape when available. If SERPER key is missing, state limitations.",
            tools=research_tools,
            llm=gemini_llm,
            verbose=True,
        ),
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou quantify pricing gaps, positioning, and quick wins.\nDirectives: {directives}",
            tools=research_tools,
            llm=gemini_llm,
            verbose=True,
        ),
        "marketing_adviser": Agent(
            role="Marketing Adviser",
            goal=f"Create a pragmatic marketing plan for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou recommend channels, messaging, and a weekly execution cadence.\nDirectives: {directives}",
            llm=gemini_llm,
            verbose=True,
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal=f"Synthesize into a CEO-ready 30-day execution plan for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou produce a weekly roadmap, KPIs, priorities, and owner/operator tasks.",
            llm=gemini_llm,
            verbose=True,
        ),
        "ecommerce_marketer": Agent(
            role="E-Commerce Marketer",
            goal=f"Design an e-commerce growth system for {biz} (or a store-ready funnel if not e-commerce).",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou deliver funnel steps, email/SMS flows, offers, retention.\nIf not e-commerce, adapt to lead-gen.",
            llm=gemini_llm,
            verbose=True,
        ),
        "ads": Agent(
            role="Performance Ads Architect",
            goal=f"Generate deployable ad copy for {biz} targeting {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nGoogle Search + Meta copy in tables. Don’t fabricate claims.",
            llm=gemini_llm,
            verbose=True,
        ),
        "creative": Agent(
            role="Creative Director (Assets & Prompts)",
            goal=f"Create creative direction + prompt packs for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nReturn concepts, angles, prompts + ad variants. Be specific.",
            llm=gemini_llm,
            verbose=True,
        ),
        "seo": Agent(
            role="Search Engine Marketing (SEO)",
            goal=f"Write a local SEO authority article for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nE-E-A-T, local intent, FAQs, CTA. No fake stats.",
            llm=gemini_llm,
            verbose=True,
        ),
        "guest_posting": Agent(
            role="Guest Posting Specialist",
            goal=f"Build a guest posting plan to earn relevant backlinks and referral traffic for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou produce targets, outreach templates, topic angles, and safe anchors.\nIf sites not validated, mark as examples.",
            tools=research_tools,
            llm=gemini_llm,
            verbose=True,
        ),
        "social": Agent(
            role="Social Distribution Architect",
            goal=f"Create a 30-day social plan for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nDaily topics, hooks, captions, CTAs. Avoid unverifiable claims.",
            llm=gemini_llm,
            verbose=True,
        ),
        "geo": Agent(
            role="GEO / Local Search Specialist",
            goal=f"Create a local GEO plan for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nCitations, GBP optimization, near-me targeting steps.",
            llm=gemini_llm,
            verbose=True,
        ),
        "gbp_growth": Agent(
            role="Google Business Profile (GBP) Growth Agent",
            goal=f"Grow Google Business Profile visibility for {biz} in {city}.",
            backstory=(
                f"{SAFETY_INSTRUCTIONS}\n"
                "You deliver:\n"
                "- Weekly GBP posts\n"
                "- Review reply templates (positive & negative)\n"
                "- Keyword/service suggestions\n"
                "- Ranking drop triage checklist (no fake rank data)\n"
                f"Directives: {directives}\n"
                f"URL: {url or '[missing]'}"
            ),
            llm=gemini_llm,
            verbose=True,
        ),
        "audit": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose conversion leaks for {biz} based on the provided website.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nAudit speed, trust, mobile UX, conversion friction.\nIf URL missing, ask for it clearly.\nURL: {url or '[missing]'}",
            tools=[scrape_tool],
            llm=gemini_llm,
            verbose=True,
        ),
    }

# ============================================================
# ROBUST OUTPUT EXTRACTION
# ============================================================
def _extract_output(task: Task, kickoff_result: Any) -> str:
    # 1) crew kickoff result (often string)
    try:
        if kickoff_result is not None:
            txt = str(kickoff_result).strip()
            if txt:
                return txt
    except Exception:
        pass

    # 2) task.output raw-like fields
    out = getattr(task, "output", None)
    if out is None:
        return ""

    for attr in ("raw", "result", "text", "final", "content", "message"):
        try:
            v = getattr(out, attr, None)
            if v:
                return str(v).strip()
        except Exception:
            pass

    # 3) dict-like
    try:
        if isinstance(out, dict):
            for k in ("raw", "result", "text", "final", "content"):
                if out.get(k):
                    return str(out.get(k)).strip()
            return json.dumps(out)
    except Exception:
        pass

    # 4) last resort
    try:
        return str(out).strip()
    except Exception:
        return ""

def _run_one(agent_key: str, agent: Agent, state: SwarmState) -> str:
    """Run exactly one task and return its output as text."""
    biz = state.biz_name
    city = state.location
    url = state.url.strip()

    # Task prompts per agent (executive-ready)
    if agent_key == "market_researcher":
        desc = (
            f"Market research snapshot for {biz} in {city}.\n"
            "Return:\n"
            "1) ICP segments (3)\n"
            "2) Buyer triggers & pains\n"
            "3) Competitor landscape (types + positioning themes)\n"
            "4) Offer/pricing patterns (no invented numbers)\n"
            "5) Demand themes + keyword buckets (no fake volume)\n"
            "6) 5 opportunity angles + why\n"
        )
        expected = "Executive market research snapshot."
    elif agent_key == "analyst":
        desc = (
            f"Market analysis for {biz} in {city}.\n"
            "Return bullets:\n"
            "1) Pricing gaps\n2) Positioning\n3) Top 3 offers\n4) Quick wins\n"
        )
        expected = "Structured market analysis."
    elif agent_key == "marketing_adviser":
        desc = (
            f"Marketing adviser plan for {biz} in {city}.\n"
            "Return:\n"
            "- Best 3 channels + why\n"
            "- Messaging (3 value props + proof ideas)\n"
            "- Weekly execution plan (4 weeks)\n"
            "- Budget tiers (low/med/high) with what to do (no fabricated costs)\n"
            "- KPI checklist\n"
        )
        expected = "Pragmatic marketing plan."
    elif agent_key == "strategist":
        desc = (
            f"Create a CEO-ready 30-day execution roadmap for {biz} in {city}.\n"
            "Include:\n- Weekly plan\n- KPIs\n- Quick wins\n- Priorities\n- Owner/operator checklist\n"
        )
        expected = "CEO-ready roadmap."
    elif agent_key == "ecommerce_marketer":
        desc = (
            f"E-commerce growth plan for {biz} in {city}.\n"
            "If the business is NOT e-commerce, adapt the plan to lead-gen.\n"
            "Return:\n"
            "1) Offer structure (bundles/upsells)\n"
            "2) Conversion levers (product/landing/checkout)\n"
            "3) Email/SMS flows (welcome, abandon, post-purchase, winback)\n"
            "4) Retention tactics\n"
            "5) 7-day sprint checklist\n"
        )
        expected = "E-commerce growth system."
    elif agent_key == "ads":
        desc = (
            f"Generate deployable ad copy for {biz} targeting {city}.\n"
            "Return Markdown tables:\n"
            "- Google Search: 10 headlines + 6 descriptions\n"
            "- Meta: 8 hooks + 6 primary texts + 5 CTAs\n"
            "No fake claims."
        )
        expected = "Ad copy tables."
    elif agent_key == "creative":
        desc = (
            f"Creative direction for {biz}.\n"
            "Deliver:\n"
            "1) 5 creative concepts (name + angle + who it's for)\n"
            "2) 3 ad variants per concept (headline + body + CTA)\n"
            "3) Prompt pack (at least 12 prompts) for Midjourney/Runway/Canva\n"
            "4) Canva layout directions (2 layouts)\n"
            "Be specific. Avoid unverifiable claims."
        )
        expected = "Creative pack."
    elif agent_key == "seo":
        desc = (
            f"Write a local SEO authority article for {biz} in {city}.\n"
            "Include headings, FAQs, local intent, and a clear CTA.\n"
            "Do not invent statistics."
        )
        expected = "SEO authority article."
    elif agent_key == "guest_posting":
        desc = (
            f"Guest posting plan for {biz} in {city}.\n"
            "Return:\n"
            "1) Target site categories + how to find them\n"
            "2) 10 pitch angles\n"
            "3) 12 article topic titles\n"
            "4) Outreach email template + 2 follow-ups\n"
            "5) Anchor-text plan (safe mix) + tracking checklist\n"
        )
        expected = "Guest posting plan."
    elif agent_key == "social":
        desc = (
            f"Create a 30-day social content calendar for {biz} in {city}.\n"
            "Include daily topic, hook, caption, CTA.\n"
            "Prefer short, scannable rows (Day 1..30)."
        )
        expected = "30-day social calendar."
    elif agent_key == "geo":
        desc = (
            f"Create a local GEO plan for {biz} in {city}.\n"
            "Return:\n- GBP optimization checklist\n- Citation checklist\n- Review strategy\n- Near-me targeting steps\n- Local content ideas\n"
            "If uncertain, explain how to verify."
        )
        expected = "Local GEO plan."
    elif agent_key == "gbp_growth":
        desc = (
            f"Create a GBP Growth Pack for {biz} in {city}.\n\n"
            "Return EXECUTIVE format with these sections:\n"
            "1) Weekly GBP Posts (7 drafts): title + 80-150 word copy + CTA + photo idea\n"
            "2) Review Replies:\n"
            "   - 5 positive reply templates\n"
            "   - 5 negative reply templates (de-escalation + resolution)\n"
            "3) GBP Keywords & Services:\n"
            "   - 15 keyword phrases (service + city + intent)\n"
            "   - Primary/secondary category suggestions (state uncertainty if unknown)\n"
            "4) Ranking Drop Triage:\n"
            "   - Checklist (what to check)\n"
            "   - Likely causes\n"
            "   - Immediate actions (48 hours) + follow-up (14 days)\n\n"
            "Rules: Do NOT invent rankings/metrics. If you need data, list it under 'Data Needed'."
        )
        expected = "Executive GBP Growth Pack."
    elif agent_key == "audit":
        if not url:
            return "Missing website URL. Please provide a business website URL in the sidebar."
        desc = (
            f"Audit this website for conversion friction: {url}\n"
            "Return executive output:\n"
            "- Top issues (prioritized)\n- Impact\n- Fixes\n"
            "Do NOT dump raw HTML."
        )
        expected = "Executive conversion audit."
    else:
        desc = f"Generate an executive report for {biz} in {city}."
        expected = "Executive report."

    task = Task(description=desc, agent=agent, expected_output=expected)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)

    kickoff_result = kickoff_with_retry(crew, retries=2, base_sleep=15)
    txt = _extract_output(task, kickoff_result)
    return txt if txt else "No output returned (empty response)."

def _build_full_report(state: SwarmState, package: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = (
        f"# {state.biz_name} Intelligence Report\n"
        f"**Date:** {now} | **Location:** {state.location} | **Plan:** {package}\n"
        f"---\n\n"
    )

    sections = [
        ("🔎 Market Research", state.market_researcher),
        ("🕵️ Market Analysis", state.analyst),
        ("🧭 Marketing Adviser", state.marketing_adviser),
        ("👔 Executive Strategy", state.strategist),
        ("🛒 E-Commerce Marketer", state.ecommerce_marketer),
        ("📺 Ads Output", state.ads),
        ("🎨 Creative Pack", state.creative),
        ("✍️ SEO (SEM)", state.seo),
        ("🧩 Guest Posting", state.guest_posting),
        ("📍 GEO Intelligence", state.geo),
        ("📍 GBP Growth Pack", state.gbp_growth),
        ("📱 Social Roadmap", state.social),
        ("🌐 Website Audit", state.audit),
    ]

    body = ""
    for title, content in sections:
        body += f"## {title}\n{content}\n\n"

    return header + body.strip()

# ============================================================
# PUBLIC WRAPPER (used by app.py)
# ============================================================
def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Returns keys that match app.py toggles exactly:
    analyst, ads, creative, strategist, social, geo, audit, seo,
    marketing_adviser, ecommerce_marketer, guest_posting, market_researcher,
    gbp_growth,
    plus full_report.
    """
    inputs = inputs or {}
    active_list = inputs.get("active_swarm", []) or []
    active = [str(k).strip() for k in active_list if str(k).strip()]
    active = [k for k in active if k in TOGGLE_KEYS]

    state = SwarmState(
        biz_name=inputs.get("biz_name", "Unknown Brand"),
        location=inputs.get("city", "USA"),
        directives=inputs.get("directives", ""),
        url=(inputs.get("url") or inputs.get("website") or ""),
    )

    package = inputs.get("package", "Lite")
    agents = get_swarm_agents(inputs)

    # deterministic order
    RUN_ORDER: List[str] = [
        "market_researcher",
        "analyst",
        "marketing_adviser",
        "strategist",
        "ecommerce_marketer",
        "ads",
        "creative",
        "seo",
        "guest_posting",
        "geo",
        "gbp_growth",
        "social",
        "audit",
    ]

    for key in RUN_ORDER:
        if key not in active:
            continue
        txt = _run_one(key, agents[key], state)
        try:
            setattr(state, key, txt)
        except Exception:
            pass

    state.full_report = _build_full_report(state, package)

    master: Dict[str, str] = {
        "analyst": state.analyst,
        "audit": state.audit,
        "strategist": state.strategist,
        "ads": state.ads,
        "creative": state.creative,
        "seo": state.seo,
        "social": state.social,
        "geo": state.geo,
        "marketing_adviser": state.marketing_adviser,
        "ecommerce_marketer": state.ecommerce_marketer,
        "guest_posting": state.guest_posting,
        "market_researcher": state.market_researcher,
        "gbp_growth": state.gbp_growth,
        "full_report": state.full_report,
    }

    # Always return full_report; return selected agents too
    return {k: v for k, v in master.items() if (k in active) or (k == "full_report")}
