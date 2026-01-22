import os
import base64
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
# 0) ENV / SECRETS
# ============================================================
load_dotenv(override=True)

def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Streamlit secrets first, then environment."""
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
    """Retry crew.kickoff() on Gemini 429 rate limit errors."""
    for attempt in range(retries + 1):
        try:
            return crew.kickoff()
        except Exception as e:
            if _is_429(e) and attempt < retries:
                wait = base_sleep * (attempt + 1)
                st.warning(f"⚠️ Rate limited (429). Retrying in {wait}s (attempt {attempt+1}/{retries})...")
                time.sleep(wait)
                continue
            raise

TOGGLE_KEYS = {"analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo"}  # keep aligned with app.py

# ============================================================
# 1) STATE
# ============================================================
class SwarmState(BaseModel):
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Outputs map exactly to app.py keys
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
# 2) LLM + TOOLS
# ============================================================
GOOGLE_API_KEY = (
    _get_secret("GOOGLE_API_KEY")
    or _get_secret("GEMINI_API_KEY")
    or _get_secret("GENAI_API_KEY")
)

SERPER_API_KEY = _get_secret("SERPER_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY. Add it to Streamlit secrets or environment variables.")

gemini_llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(api_key=SERPER_API_KEY) if SERPER_API_KEY else None

# ============================================================
# 3) AGENTS
# ============================================================
def get_swarm_agents(inputs: Dict[str, Any]) -> Dict[str, Agent]:
    biz = inputs.get("biz_name", "The Business")
    city = inputs.get("city", "the local area")
    url = inputs.get("url") or inputs.get("website") or "the provided website"
    directives = inputs.get("directives") or "Standard growth optimization."

    analyst_tools = [scrape_tool]
    if search_tool:
        analyst_tools = [search_tool, scrape_tool]

    return {
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=f"You quantify market entry gaps, competitor fatigue, and pricing gaps. Directives: {directives}",
            tools=analyst_tools,
            llm=gemini_llm,
            verbose=True
        ),
        "ads": Agent(
            role="Performance Ads Architect",
            goal=f"Generate deployable ad copy for {biz} targeting {city}.",
            backstory="You write conversion-focused hooks and compliant ad copy for Google Search and Meta.",
            llm=gemini_llm,
            verbose=True
        ),
        "creative": Agent(
            role="Creative Director (Assets & Prompts)",
            goal=f"Create creative direction + prompt packs for {biz}.",
            backstory="You deliver high-converting creative concepts and prompt packs (Midjourney/Canva-ready).",
            llm=gemini_llm,
            verbose=True
        ),
        "seo": Agent(
            role="SEO Content Architect",
            goal=f"Write a local SEO authority article for {biz} in {city}.",
            backstory="Expert in E-E-A-T and SGE. Structured content that ranks and converts.",
            llm=gemini_llm,
            verbose=True
        ),
        "audit": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose conversion leaks on {url}.",
            backstory="You identify friction points, speed/mobile issues, and trust blockers preventing ROI.",
            tools=[scrape_tool],
            llm=gemini_llm,
            verbose=True
        ),
        "social": Agent(
            role="Social Distribution Architect",
            goal=f"Create a 30-day social plan for {biz} in {city}.",
            backstory="You design daily content that drives inbound leads with hooks and CTAs.",
            llm=gemini_llm,
            verbose=True
        ),
        "geo": Agent(
            role="GEO / Local Search Specialist",
            goal=f"Create a local GEO plan for {biz} in {city}.",
            backstory="Local ranking factors, citations, GBP optimization, near-me targeting.",
            llm=gemini_llm,
            verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal=f"Synthesize intelligence into a CEO-ready 30-day execution plan for {biz}.",
            backstory="You create priorities, weekly plan, KPIs, and quick wins.",
            llm=gemini_llm,
            verbose=True
        ),
    }

# ============================================================
# 4) FLOW
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
    def phase_1_discovery(self):
        tasks = []

        if "analyst" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Identify market gaps for {self.state.biz_name} in {self.state.location}. "
                    "Return structured bullets: pricing gaps, positioning, 3 offers, quick wins."
                ),
                agent=self.agents["analyst"],
                expected_output="Structured market analysis."
            ))

        if "audit" in self.active_swarm:
            url = self.state.url or "the website"
            tasks.append(Task(
                description=(
                    f"Audit {url} for conversion friction. DO NOT dump raw HTML. "
                    "Provide top issues + impact + fixes."
                ),
                agent=self.agents["audit"],
                expected_output="Executive technical audit."
            ))

        if tasks:
            crew = Crew(agents=[t.agent for t in tasks], tasks=tasks, process=Process.sequential)
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            for t in tasks:
                out = str(getattr(t.output, "raw", "") or "")
                desc = (t.description or "").lower()
                if "market gaps" in desc or "market" in desc:
                    self.state.market_data = out
                elif "audit" in desc or "conversion friction" in desc:
                    self.state.website_audit = out if len(out) <= 4500 else out[:4500] + "\n\n[Output truncated]"

        return "trigger_production"

    @listen("trigger_production")
    def phase_2_execution(self):
        tasks = []

        if "strategist" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day execution roadmap for {self.state.biz_name} in {self.state.location}. "
                    "Include priorities, weekly plan, KPIs, and quick wins."
                ),
                agent=self.agents["strategist"],
                expected_output="CEO-ready strategy brief."
            ))

        if "ads" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Generate deployable ad copy for {self.state.biz_name} targeting {self.state.location}. "
                    "Return Markdown tables: Google Search headlines/descriptions + Meta hooks + primary text."
                ),
                agent=self.agents["ads"],
                expected_output="Markdown ad copy tables."
            ))

        if "creative" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create creative direction for {self.state.biz_name}. "
                    "Deliver 5 concepts + angles + a Midjourney/Canva prompt pack + 3 ad variants per concept."
                ),
                agent=self.agents["creative"],
                expected_output="Creative direction + prompt pack."
            ))

        if "seo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Write an SEO authority article for {self.state.biz_name} in {self.state.location}. "
                    "Include headings, FAQs, local intent, CTA."
                ),
                agent=self.agents["seo"],
                expected_output="SEO authority article."
            ))

        if "social" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day social calendar for {self.state.biz_name} in {self.state.location}. "
                    "Include daily post topics, hooks, captions, and CTAs."
                ),
                agent=self.agents["social"],
                expected_output="30-day social calendar."
            ))

        if "geo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a local GEO plan for {self.state.biz_name} in {self.state.location}. "
                    "Include citations, GBP optimization, near-me targeting steps."
                ),
                agent=self.agents["geo"],
                expected_output="Local GEO plan."
            ))

        if tasks:
            crew = Crew(agents=[t.agent for t in tasks], tasks=tasks, process=Process.sequential)
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            for t in tasks:
                out = str(getattr(t.output, "raw", "") or "")
                desc = (t.description or "").lower()

                if "execution roadmap" in desc or "roadmap" in desc:
                    self.state.strategist_brief = out
                elif "deployable ad copy" in desc or "google search" in desc or "meta hooks" in desc:
                    self.state.ads_output = out
                elif "creative direction" in desc or "prompt pack" in desc or "ad variants" in desc:
                    self.state.creative_pack = out
                elif "seo authority article" in desc or "seo" in desc:
                    self.state.seo_article = out
                elif "social calendar" in desc or "social" in desc:
                    self.state.social_plan = out
                elif "local geo plan" in desc or "citations" in desc or "gbp" in desc:
                    self.state.geo_intel = out

        return "finalize_report"

    @listen("finalize_report")
    def finalize_report(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        package = self.inputs.get("package", "Lite")

        header = (
            f"# {self.state.biz_name} Intelligence Report\n"
            f"**Date:** {now} | **Location:** {self.state.location} | **Plan:** {package}\n"
            f"---\n"
        )

        self.state.full_report = (
            f"{header}\n"
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


# ============================================================
# 5) PUBLIC WRAPPER (used by app.py)
# ============================================================
def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Returns keys that match app.py toggles exactly:
    analyst, ads, creative, strategist, social, geo, audit, seo, full_report
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
        "full_report": flow.state.full_report,
    }

    active_list = inputs.get("active_swarm", []) or []
    active_list = [str(k).strip() for k in active_list]

    # always return full_report; return selected agents too
    return {k: v for k, v in master.items() if (k in active_list) or (k == "full_report")}
