import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from pydantic import BaseModel
from dotenv import load_dotenv

import streamlit as st

from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# ============================================================
# ENV / SECRETS
# ============================================================
load_dotenv(override=True)

def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
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
    for attempt in range(retries + 1):
        try:
            return crew.kickoff()
        except Exception as e:
            if _is_429(e) and attempt < retries:
                wait = base_sleep * (attempt + 1)
                st.warning(f"⚠️ Rate limited (429). Retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise

# ✅ Extended toggles (existing + optional future agents)
TOGGLE_KEYS = {
    "analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo",
    "marketing_adviser", "ecommerce_marketer", "guest_posting", "market_researcher"
}

# ============================================================
# STATE
# ============================================================
class SwarmState(BaseModel):
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Existing outputs (map to app keys)
    market_data: str = "Agent not selected for this run."
    ads_output: str = "Agent not selected for this run."
    creative_pack: str = "Agent not selected for this run."
    strategist_brief: str = "Agent not selected for this run."
    website_audit: str = "Agent not selected for this run."
    social_plan: str = "Agent not selected for this run."
    geo_intel: str = "Agent not selected for this run."
    seo_article: str = "Agent not selected for this run."

    # New optional outputs (for future UI toggles; also usable via API)
    marketing_adviser: str = "Agent not selected for this run."
    ecommerce_marketer: str = "Agent not selected for this run."
    guest_posting: str = "Agent not selected for this run."
    market_research: str = "Agent not selected for this run."

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
    raise RuntimeError("Missing GOOGLE_API_KEY in secrets or env.")

gemini_llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,
    temperature=0.2,  # lower to reduce hallucination
)

scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(api_key=SERPER_API_KEY) if SERPER_API_KEY else None

SAFETY_INSTRUCTIONS = (
    "Important rules:\n"
    "- Do NOT invent facts, citations, or metrics.\n"
    "- If data is missing, say what you would need.\n"
    "- If you use web search results, summarize them and note uncertainty.\n"
    "- Prefer concise, executive-ready bullets.\n"
)

# ============================================================
# AGENTS
# ============================================================
def get_swarm_agents(inputs: Dict[str, Any]) -> Dict[str, Agent]:
    biz = inputs.get("biz_name", "The Business")
    city = inputs.get("city", "the local area")
    url = inputs.get("url") or inputs.get("website") or ""
    directives = inputs.get("directives") or "Standard growth optimization."

    analyst_tools = [scrape_tool]
    if search_tool:
        analyst_tools = [search_tool, scrape_tool]

    # Tools for research/outreach style agents
    outreach_tools = [scrape_tool]
    if search_tool:
        outreach_tools = [search_tool, scrape_tool]

    return {
        # --- Existing agents (kept) ---
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou quantify pricing gaps, positioning, and quick wins.\nDirectives: {directives}",
            tools=analyst_tools,
            llm=gemini_llm,
            verbose=True
        ),
        "audit": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose conversion leaks for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou audit websites for speed, trust, mobile UX, and conversion friction.\nIf URL is missing, ask for it.",
            tools=[scrape_tool],
            llm=gemini_llm,
            verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal=f"Synthesize into a CEO-ready 30-day execution plan for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou produce a weekly roadmap, KPIs, and priorities.",
            llm=gemini_llm,
            verbose=True
        ),
        "ads": Agent(
            role="Performance Ads Architect",
            goal=f"Generate deployable ad copy for {biz} targeting {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nGoogle Search + Meta copy in tables. Don’t fabricate claims.",
            llm=gemini_llm,
            verbose=True
        ),
        "creative": Agent(
            role="Creative Director (Assets & Prompts)",
            goal=f"Create creative direction + prompt packs for {biz}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nReturn 5 concepts, angles, and prompt packs + ad variants. Be specific.",
            llm=gemini_llm,
            verbose=True
        ),
        "seo": Agent(
            role="SEO Content Architect",
            goal=f"Write a local SEO authority article for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nE-E-A-T, local intent, FAQs, clear CTA. No fake stats.",
            llm=gemini_llm,
            verbose=True
        ),
        "social": Agent(
            role="Social Distribution Architect",
            goal=f"Create a 30-day social plan for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nDaily topics, hooks, captions, CTAs. Avoid unverifiable claims.",
            llm=gemini_llm,
            verbose=True
        ),
        "geo": Agent(
            role="GEO / Local Search Specialist",
            goal=f"Create a local GEO plan for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nCitations, GBP optimization, near-me targeting steps.",
            llm=gemini_llm,
            verbose=True
        ),

        # --- New optional agents (for future toggles; also usable via direct API calls) ---
        "marketing_adviser": Agent(
            role="Marketing Adviser (Executive)",
            goal=f"Recommend channel mix + messaging + measurement for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou give executive-level recommendations with practical next steps.",
            llm=gemini_llm,
            verbose=True
        ),
        "ecommerce_marketer": Agent(
            role="E-Commerce Marketer",
            goal=f"Increase conversion + AOV + retention for {biz} (local + online) targeting {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nFocus on offers, landing pages, email/SMS flows, and remarketing.",
            llm=gemini_llm,
            verbose=True
        ),
        "guest_posting": Agent(
            role="Guest Posting Strategist",
            goal=f"Design a guest posting + digital PR plan for {biz} to earn links and authority.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou propose target site criteria, pitch angles, topics, and outreach templates.",
            tools=outreach_tools,
            llm=gemini_llm,
            verbose=True
        ),
        "market_researcher": Agent(
            role="Market Researcher",
            goal=f"Deliver research-backed market intelligence for {biz} in {city}.",
            backstory=f"{SAFETY_INSTRUCTIONS}\nYou identify segments, competitors, demand signals, and keyword themes without fake numbers.",
            tools=analyst_tools,
            llm=gemini_llm,
            verbose=True
        ),
    }

# ============================================================
# OUTPUT EXTRACTION (PATCHED)
# ============================================================
def _task_text(task: Task) -> str:
    """
    Robustly extract text from CrewAI Task output across versions.
    """
    out = getattr(task, "output", None)
    if out is None:
        return ""
    if isinstance(out, str):
        return out

    # Common payload attributes across versions
    for attr in ("raw", "result", "text", "final", "content", "message"):
        try:
            v = getattr(out, attr, None)
            if v:
                return str(v)
        except Exception:
            pass

    # Sometimes output may be a dict-like
    try:
        if isinstance(out, dict):
            for k in ("raw", "result", "text", "final", "content"):
                if out.get(k):
                    return str(out.get(k))
            return json.dumps(out)
    except Exception:
        pass

    try:
        return str(out)
    except Exception:
        return ""

def _safe_set(state_field_get: str, txt: str, truncate: Optional[int] = None) -> str:
    txt = (txt or "").strip()
    if not txt:
        return ""
    if truncate and len(txt) > truncate:
        return txt[:truncate] + "\n\n[Truncated]"
    return txt

# ============================================================
# FLOW
# ============================================================
class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs: Dict[str, Any]):
        super().__init__()
        self.inputs = inputs or {}

        self.state.biz_name = self.inputs.get("biz_name", "Unknown Brand")
        self.state.location = self.inputs.get("city", "USA")
        self.state.directives = self.inputs.get("directives", "")
        self.state.url = self.inputs.get("url") or self.inputs.get("website") or ""

        active = self.inputs.get("active_swarm", []) or []
        self.active_swarm = [str(k).strip() for k in active if str(k).strip() in TOGGLE_KEYS]

        self.agents = get_swarm_agents(self.inputs)

    @start()
    def phase_1(self):
        tasks_order: List[Tuple[str, Task]] = []

        # ANALYST (expanded to include Market Researcher deliverables)
        if "analyst" in self.active_swarm:
            tasks_order.append((
                "analyst",
                Task(
                    description=(
                        f"Market analysis for {self.state.biz_name} in {self.state.location}.\n"
                        "Return EXECUTIVE bullets with clear headings:\n"
                        "A) Pricing gaps (what competitors charge; price bands if unknown)\n"
                        "B) Positioning (1-liner + differentiators)\n"
                        "C) Top 3 offers (name, price range, promise, who it's for)\n"
                        "D) Quick wins (next 7 days)\n\n"
                        "Also include a **Market Research Appendix**:\n"
                        "- Primary customer segments (3–5)\n"
                        "- Top competitors (5–10) + what they do well/poorly (no fake claims)\n"
                        "- Demand signals: 'near me' intent ideas + search themes\n"
                        "- What data you'd need to estimate market size (do not invent numbers)\n"
                    ),
                    agent=self.agents["analyst"],
                    expected_output="Executive market analysis + market research appendix."
                )
            ))

        # OPTIONAL: standalone Market Researcher (only if explicitly selected)
        if "market_researcher" in self.active_swarm:
            tasks_order.append((
                "market_researcher",
                Task(
                    description=(
                        f"Market Research Report for {self.state.biz_name} in {self.state.location}.\n"
                        "Return EXECUTIVE format:\n"
                        "1) Who buys + why (segments + pains)\n"
                        "2) Competitor map (top players; positioning themes)\n"
                        "3) Keyword clusters + intent buckets (no fake volume)\n"
                        "4) Offer opportunities (gaps to exploit)\n"
                        "5) Research checklist (what data we should collect next)\n"
                    ),
                    agent=self.agents["market_researcher"],
                    expected_output="Executive market research report."
                )
            ))

        # AUDIT
        if "audit" in self.active_swarm:
            if not self.state.url.strip():
                self.state.website_audit = "Missing website URL. Please provide a business website URL in the sidebar."
            else:
                tasks_order.append((
                    "audit",
                    Task(
                        description=(
                            f"Audit this website for conversion friction: {self.state.url}\n"
                            "Return EXECUTIVE output:\n"
                            "- Top issues (ranked)\n"
                            "- Impact (why it hurts conversions)\n"
                            "- Fixes (exact changes)\n"
                            "- Quick wins (48 hours)\n"
                            "Do NOT dump raw HTML."
                        ),
                        agent=self.agents["audit"],
                        expected_output="Executive conversion audit."
                    )
                ))

        if tasks_order:
            crew = Crew(
                agents=[t.agent for _, t in tasks_order],
                tasks=[t for _, t in tasks_order],
                process=Process.sequential
            )
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            executed_tasks = getattr(crew, "tasks", None) or [t for _, t in tasks_order]

            for (key, _), t_exec in zip(tasks_order, executed_tasks):
                txt = _task_text(t_exec)
                if key == "analyst":
                    v = _safe_set("market_data", txt)
                    if v:
                        self.state.market_data = v
                elif key == "audit":
                    v = _safe_set("website_audit", txt, truncate=4500)
                    if v:
                        self.state.website_audit = v
                elif key == "market_researcher":
                    v = _safe_set("market_research", txt)
                    if v:
                        self.state.market_research = v

        return "phase_2"

    @listen("phase_2")
    def phase_2(self):
        tasks_order: List[Tuple[str, Task]] = []

        # STRATEGIST (expanded to include Marketing Adviser content)
        if "strategist" in self.active_swarm:
            tasks_order.append((
                "strategist",
                Task(
                    description=(
                        f"Create a CEO-ready 30-day execution roadmap for {self.state.biz_name} in {self.state.location}.\n"
                        "EXECUTIVE format:\n"
                        "- North Star goal + 3 supporting KPIs\n"
                        "- Weekly plan (Week 1–4)\n"
                        "- Priorities (Top 7)\n"
                        "- Quick wins (next 72 hours)\n"
                        "- Risks + mitigations\n\n"
                        "Also include a **Marketing Adviser Addendum**:\n"
                        "- Channel mix recommendation (owned/paid/earned)\n"
                        "- Messaging pillars (3) + proof points (what evidence needed)\n"
                        "- Measurement plan (UTMs, funnel events, weekly review)\n"
                        "- Budget ranges (if unknown, provide tiers: low/med/high)\n"
                    ),
                    agent=self.agents["strategist"],
                    expected_output="CEO-ready roadmap + marketing adviser addendum."
                )
            ))

        # OPTIONAL: standalone Marketing Adviser (only if explicitly selected)
        if "marketing_adviser" in self.active_swarm:
            tasks_order.append((
                "marketing_adviser",
                Task(
                    description=(
                        f"Marketing Adviser Report for {self.state.biz_name} in {self.state.location}.\n"
                        "Return EXECUTIVE format:\n"
                        "1) Messaging pillars + sample taglines\n"
                        "2) Channel mix (what to run now vs later)\n"
                        "3) 30-day experiment plan (3 experiments)\n"
                        "4) Weekly scorecard template\n"
                    ),
                    agent=self.agents["marketing_adviser"],
                    expected_output="Executive marketing adviser report."
                )
            ))

        # ADS (expanded to include E-Commerce Marketer content)
        if "ads" in self.active_swarm:
            tasks_order.append((
                "ads",
                Task(
                    description=(
                        f"Generate deployable ad copy for {self.state.biz_name} targeting {self.state.location}.\n"
                        "Return Markdown tables:\n"
                        "- Google Search: 10 headlines + 6 descriptions\n"
                        "- Meta: 8 hooks + 6 primary texts + 5 CTAs\n"
                        "No fake claims.\n\n"
                        "Also include an **E-Commerce / Conversion Add-on** (even if local service):\n"
                        "- Offer structure (core offer + 2 upsells)\n"
                        "- Landing page sections (hero, proof, offer, FAQ, CTA)\n"
                        "- Remarketing audiences (5)\n"
                        "- Email/SMS flow outline (welcome, abandoned, winback)\n"
                    ),
                    agent=self.agents["ads"],
                    expected_output="Ad tables + conversion add-on."
                )
            ))

        # OPTIONAL: standalone E-Commerce Marketer (only if explicitly selected)
        if "ecommerce_marketer" in self.active_swarm:
            tasks_order.append((
                "ecommerce_marketer",
                Task(
                    description=(
                        f"E-Commerce Marketing Report for {self.state.biz_name} in {self.state.location}.\n"
                        "Return EXECUTIVE format:\n"
                        "1) Offer ladder (core + upsell + premium)\n"
                        "2) Landing page wireframe\n"
                        "3) Email/SMS flows (welcome, abandoned cart, post-purchase, winback)\n"
                        "4) Retargeting plan (audiences + creative angles)\n"
                        "5) KPI targets (ranges if unknown)\n"
                    ),
                    agent=self.agents["ecommerce_marketer"],
                    expected_output="Executive e-commerce marketing report."
                )
            ))

        # CREATIVE
        if "creative" in self.active_swarm:
            tasks_order.append((
                "creative",
                Task(
                    description=(
                        f"Creative direction for {self.state.biz_name}.\n"
                        "Deliver:\n"
                        "1) 5 creative concepts (name + angle + who it's for)\n"
                        "2) 3 ad variants per concept (headline + body + CTA)\n"
                        "3) Midjourney prompt pack (at least 10 prompts)\n"
                        "4) Canva layout directions (2 layouts)\n"
                        "Be specific. Avoid unverifiable claims."
                    ),
                    agent=self.agents["creative"],
                    expected_output="Creative pack."
                )
            ))

        # SEO (expanded to include Guest Posting)
        if "seo" in self.active_swarm:
            tasks_order.append((
                "seo",
                Task(
                    description=(
                        f"Write an SEO authority article for {self.state.biz_name} in {self.state.location}.\n"
                        "Include headings, FAQs, local intent, and a clear CTA.\n"
                        "Do not invent statistics.\n\n"
                        "Also include a **Guest Posting / Earned Links Plan**:\n"
                        "- Target site criteria (what qualifies)\n"
                        "- 10 guest post topic angles tied to {self.state.location}\n"
                        "- Outreach sequence (email 1/2/3)\n"
                        "- Anchor text + link placement rules (safe)\n"
                    ),
                    agent=self.agents["seo"],
                    expected_output="SEO article + guest posting plan."
                )
            ))

        # OPTIONAL: standalone Guest Posting (only if explicitly selected)
        if "guest_posting" in self.active_swarm:
            tasks_order.append((
                "guest_posting",
                Task(
                    description=(
                        f"Guest Posting Report for {self.state.biz_name} in {self.state.location}.\n"
                        "Return EXECUTIVE format:\n"
                        "1) Target site categories + search operators\n"
                        "2) Pitch angles (10)\n"
                        "3) Topic titles (20)\n"
                        "4) Outreach templates + follow-ups\n"
                        "5) Link safety rules\n"
                    ),
                    agent=self.agents["guest_posting"],
                    expected_output="Executive guest posting report."
                )
            ))

        # SOCIAL
        if "social" in self.active_swarm:
            tasks_order.append((
                "social",
                Task(
                    description=(
                        f"Create a 30-day social content calendar for {self.state.biz_name} in {self.state.location}.\n"
                        "Include daily topic, hook, caption, CTA.\n"
                        "Keep claims verifiable; use placeholders for proof points if unknown."
                    ),
                    agent=self.agents["social"],
                    expected_output="30-day social calendar."
                )
            ))

        # GEO
        if "geo" in self.active_swarm:
            tasks_order.append((
                "geo",
                Task(
                    description=(
                        f"Create a local GEO plan for {self.state.biz_name} in {self.state.location}.\n"
                        "EXECUTIVE output:\n"
                        "- GBP optimization checklist\n"
                        "- Citation plan (types, not fake lists)\n"
                        "- Near-me targeting steps\n"
                        "- Review acquisition system\n"
                        "- 7-day quick wins\n"
                        "If citations are uncertain, explain how to verify."
                    ),
                    agent=self.agents["geo"],
                    expected_output="Local GEO plan."
                )
            ))

        if tasks_order:
            crew = Crew(
                agents=[t.agent for _, t in tasks_order],
                tasks=[t for _, t in tasks_order],
                process=Process.sequential
            )
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            executed_tasks = getattr(crew, "tasks", None) or [t for _, t in tasks_order]

            for (key, _), t_exec in zip(tasks_order, executed_tasks):
                txt = _task_text(t_exec)

                if key == "strategist":
                    v = _safe_set("strategist_brief", txt)
                    if v:
                        self.state.strategist_brief = v
                elif key == "ads":
                    v = _safe_set("ads_output", txt)
                    if v:
                        self.state.ads_output = v
                elif key == "creative":
                    v = _safe_set("creative_pack", txt)
                    if v:
                        self.state.creative_pack = v
                elif key == "seo":
                    v = _safe_set("seo_article", txt)
                    if v:
                        self.state.seo_article = v
                elif key == "social":
                    v = _safe_set("social_plan", txt)
                    if v:
                        self.state.social_plan = v
                elif key == "geo":
                    v = _safe_set("geo_intel", txt)
                    if v:
                        self.state.geo_intel = v
                elif key == "marketing_adviser":
                    v = _safe_set("marketing_adviser", txt)
                    if v:
                        self.state.marketing_adviser = v
                elif key == "ecommerce_marketer":
                    v = _safe_set("ecommerce_marketer", txt)
                    if v:
                        self.state.ecommerce_marketer = v
                elif key == "guest_posting":
                    v = _safe_set("guest_posting", txt)
                    if v:
                        self.state.guest_posting = v

        return "finalize"

    @listen("finalize")
    def finalize(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        package = self.inputs.get("package", "Lite")

        self.state.full_report = (
            f"# {self.state.biz_name} Intelligence Report\n"
            f"**Date:** {now} | **Location:** {self.state.location} | **Plan:** {package}\n"
            f"---\n\n"
            f"## 🕵️ Market Analysis\n{self.state.market_data}\n\n"
            f"## 🔎 Market Research\n{self.state.market_research}\n\n"
            f"## 🌐 Website Audit\n{self.state.website_audit}\n\n"
            f"## 👔 Executive Strategy\n{self.state.strategist_brief}\n\n"
            f"## 🧭 Marketing Adviser\n{self.state.marketing_adviser}\n\n"
            f"## 📺 Ads Output\n{self.state.ads_output}\n\n"
            f"## 🛒 E-Commerce Marketer\n{self.state.ecommerce_marketer}\n\n"
            f"## 🎨 Creative Pack\n{self.state.creative_pack}\n\n"
            f"## ✍️ SEO Authority Article\n{self.state.seo_article}\n\n"
            f"## 🧩 Guest Posting\n{self.state.guest_posting}\n\n"
            f"## 📍 GEO Intelligence\n{self.state.geo_intel}\n\n"
            f"## 📱 Social Roadmap\n{self.state.social_plan}\n"
        )
        return "done"

# ============================================================
# PUBLIC WRAPPER
# ============================================================
def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Returns keys that match app.py toggles exactly, plus optional future keys:
    analyst, ads, creative, strategist, social, geo, audit, seo, full_report,
    marketing_adviser, ecommerce_marketer, guest_posting, market_researcher (market_research)
    """
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()

    master = {
        "analyst": flow.state.market_data,
        "audit": flow.state.website_audit,
        "strategist": flow.state.strategist_brief,
        "ads": flow.state.ads_output,
        "creative": flow.state.creative_pack,
        "seo": flow.state.seo_article,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,

        # optional future keys
        "marketing_adviser": flow.state.marketing_adviser,
        "ecommerce_marketer": flow.state.ecommerce_marketer,
        "guest_posting": flow.state.guest_posting,
        "market_researcher": flow.state.market_research,  # returned under market_researcher for convenience

        "full_report": flow.state.full_report,
    }

    active_list = inputs.get("active_swarm", []) or []
    active_list = [str(k).strip() for k in active_list]

    # Always return full_report; return only requested keys too
    return {k: v for k, v in master.items() if (k in active_list) or (k == "full_report")}
