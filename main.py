import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

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

TOGGLE_KEYS = {"analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo"}

# ============================================================
# STATE
# ============================================================
class SwarmState(BaseModel):
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Outputs (map to app keys)
    market_data: str = "Agent not selected for this run."
    ads_output: str = "Agent not selected for this run."
    creative_pack: str = "Agent not selected for this run."
    strategist_brief: str = "Agent not selected for this run."
    website_audit: str = "Agent not selected for this run."
    social_plan: str = "Agent not selected for this run."
    geo_intel: str = "Agent not selected for this run."
    seo_article: str = "Agent not selected for this run."

    full_report: str = "Full report not generated."

# ============================================================
# LLM + TOOLS
# ============================================================
GOOGLE_API_KEY = _get_secret("GOOGLE_API_KEY") or _get_secret("GEMINI_API_KEY") or _get_secret("GENAI_API_KEY")
SERPER_API_KEY = _get_secret("SERPER_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY in secrets or env.")

gemini_llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,
    temperature=0.2,  # slightly lower to reduce hallucination
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

    return {
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
    }

def _task_text(task: Task) -> str:
    out = getattr(task, "output", None)
    if out is None:
        return ""
    raw = getattr(out, "raw", None)
    if raw:
        return str(raw)
    try:
        return str(out)
    except Exception:
        return ""

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
        tasks: Dict[str, Task] = {}

        if "analyst" in self.active_swarm:
            tasks["analyst"] = Task(
                description=(
                    f"Market analysis for {self.state.biz_name} in {self.state.location}.\n"
                    "Return bullets:\n"
                    "1) Pricing gaps\n2) Positioning\n3) Top 3 offers\n4) Quick wins\n"
                ),
                agent=self.agents["analyst"],
                expected_output="Structured market analysis."
            )

        if "audit" in self.active_swarm:
            if not self.state.url.strip():
                # Don't waste LLM calls; ask for URL explicitly
                self.state.website_audit = "Missing website URL. Please provide a business website URL in the sidebar."
            else:
                tasks["audit"] = Task(
                    description=(
                        f"Audit this website for conversion friction: {self.state.url}\n"
                        "Return executive output:\n"
                        "- Top issues\n- Impact\n- Fixes\n"
                        "Do NOT dump raw HTML."
                    ),
                    agent=self.agents["audit"],
                    expected_output="Executive audit."
                )

        if tasks:
            crew = Crew(agents=[t.agent for t in tasks.values()], tasks=list(tasks.values()), process=Process.sequential)
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            if "analyst" in tasks:
                txt = _task_text(tasks["analyst"]).strip()
                if txt:
                    self.state.market_data = txt

            if "audit" in tasks:
                txt = _task_text(tasks["audit"]).strip()
                if txt:
                    self.state.website_audit = txt[:4500] + ("\n\n[Truncated]" if len(txt) > 4500 else "")

        return "phase_2"

    @listen("phase_2")
    def phase_2(self):
        tasks: Dict[str, Task] = {}

        if "strategist" in self.active_swarm:
            tasks["strategist"] = Task(
                description=(
                    f"Create a CEO-ready 30-day execution roadmap for {self.state.biz_name} in {self.state.location}.\n"
                    "Include:\n- Weekly plan\n- KPIs\n- Quick wins\n- Priorities\n"
                ),
                agent=self.agents["strategist"],
                expected_output="CEO-ready roadmap."
            )

        if "ads" in self.active_swarm:
            tasks["ads"] = Task(
                description=(
                    f"Generate deployable ad copy for {self.state.biz_name} targeting {self.state.location}.\n"
                    "Return Markdown tables:\n"
                    "- Google Search: 10 headlines + 6 descriptions\n"
                    "- Meta: 8 hooks + 6 primary texts + 5 CTAs\n"
                    "No fake claims."
                ),
                agent=self.agents["ads"],
                expected_output="Ad tables."
            )

        if "creative" in self.active_swarm:
            tasks["creative"] = Task(
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

        if "seo" in self.active_swarm:
            tasks["seo"] = Task(
                description=(
                    f"Write an SEO authority article for {self.state.biz_name} in {self.state.location}.\n"
                    "Include headings, FAQs, local intent, and a clear CTA.\n"
                    "Do not invent statistics."
                ),
                agent=self.agents["seo"],
                expected_output="SEO article."
            )

        if "social" in self.active_swarm:
            tasks["social"] = Task(
                description=(
                    f"Create a 30-day social content calendar for {self.state.biz_name} in {self.state.location}.\n"
                    "Include daily topic, hook, caption, CTA."
                ),
                agent=self.agents["social"],
                expected_output="30-day social calendar."
            )

        if "geo" in self.active_swarm:
            tasks["geo"] = Task(
                description=(
                    f"Create a local GEO plan for {self.state.biz_name} in {self.state.location}.\n"
                    "Include citations, GBP optimization, near-me targeting steps."
                ),
                agent=self.agents["geo"],
                expected_output="Local GEO plan."
            )

        if tasks:
            crew = Crew(agents=[t.agent for t in tasks.values()], tasks=list(tasks.values()), process=Process.sequential)
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            if "strategist" in tasks:
                txt = _task_text(tasks["strategist"]).strip()
                if txt:
                    self.state.strategist_brief = txt

            if "ads" in tasks:
                txt = _task_text(tasks["ads"]).strip()
                if txt:
                    self.state.ads_output = txt

            if "creative" in tasks:
                txt = _task_text(tasks["creative"]).strip()
                if txt:
                    self.state.creative_pack = txt

            if "seo" in tasks:
                txt = _task_text(tasks["seo"]).strip()
                if txt:
                    self.state.seo_article = txt

            if "social" in tasks:
                txt = _task_text(tasks["social"]).strip()
                if txt:
                    self.state.social_plan = txt

            if "geo" in tasks:
                txt = _task_text(tasks["geo"]).strip()
                if txt:
                    self.state.geo_intel = txt

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
            f"## 🌐 Website Audit\n{self.state.website_audit}\n\n"
            f"## 👔 Executive Strategy\n{self.state.strategist_brief}\n\n"
            f"## 📺 Ads Output\n{self.state.ads_output}\n\n"
            f"## 🎨 Creative Pack\n{self.state.creative_pack}\n\n"
            f"## ✍️ SEO Authority Article\n{self.state.seo_article}\n\n"
            f"## 📍 GEO Intelligence\n{self.state.geo_intel}\n\n"
            f"## 📱 Social Roadmap\n{self.state.social_plan}\n"
        )
        return "done"


def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
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
        "full_report": flow.state.full_report,
    }

    active_list = inputs.get("active_swarm", []) or []
    active_list = [str(k).strip() for k in active_list]

    return {k: v for k, v in master.items() if (k in active_list) or (k == "full_report")}
