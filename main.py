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


# Keys used by app.py toggles:
# analyst, ads, creative, strategist, social, geo, audit, seo
TOGGLE_KEYS = {"analyst", "ads", "creative", "strategist", "social", "geo", "audit", "seo", "vision"}


# ============================================================
# 1) STATE
# ============================================================
class SwarmState(BaseModel):
    # Inputs
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Outputs (each maps to a tab key in app.py)
    market_data: str = "Agent not selected for this run."
    ads_output: str = "Agent not selected for this run."
    creative_pack: str = "Agent not selected for this run."
    strategist_brief: str = "Agent not selected for this run."
    website_audit: str = "Agent not selected for this run."
    social_plan: str = "Agent not selected for this run."
    geo_intel: str = "Agent not selected for this run."
    seo_article: str = "Agent not selected for this run."
    vision_intel: str = "Agent not selected for this run."

    # Master export string
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
    raise RuntimeError(
        "Missing GOOGLE_API_KEY. Add it to Streamlit secrets (recommended) or environment variables."
    )

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
    directives = inputs.get("directives") or inputs.get("custom_reqs") or "Standard growth optimization."

    analyst_tools = [scrape_tool]
    if search_tool:
        analyst_tools = [search_tool, scrape_tool]

    return {
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=(
                "You are a market scientist. You quantify market entry gaps, competitor fatigue, and pricing gaps. "
                f"Priority directives: {directives}"
            ),
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
            backstory="Expert in E-E-A-T and SGE. You write structured content that ranks and converts.",
            llm=gemini_llm,
            verbose=True
        ),
        "audit": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose technical conversion leaks on {url}.",
            backstory="You identify friction points, speed/mobile issues, and trust blockers preventing ROI.",
            tools=[scrape_tool],
            llm=gemini_llm,
            verbose=True
        ),
        "social": Agent(
            role="Social Distribution Architect",
            goal=f"Create a 30-day social plan for {biz} in {city}.",
            backstory="You are a viral hook engineer. You design daily content that drives inbound leads.",
            llm=gemini_llm,
            verbose=True
        ),
        "geo": Agent(
            role="GEO / Local Search Specialist",
            goal=f"Create a local GEO plan for {biz} in {city}.",
            backstory="Expert in local ranking factors, citations, and AI-driven map discovery.",
            llm=gemini_llm,
            verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal=f"Synthesize outputs into a CEO-ready 30-day execution plan for {biz}.",
            backstory="You turn research into a plan with quick wins, priorities, KPIs, and weekly actions.",
            llm=gemini_llm,
            verbose=True
        ),
        # Optional / future: vision
        "vision": Agent(
            role="Technical Visual Auditor & Forensic Analyst",
            goal=f"Analyze field photos to identify defects for {biz}.",
            backstory="You provide evidence-based findings and action recommendations.",
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

        self.active_swarm = self.inputs.get("active_swarm", []) or []
        # Normalize active_swarm to expected toggle keys (strings)
        self.active_swarm = [str(k).strip() for k in self.active_swarm if str(k).strip() in TOGGLE_KEYS]

        self.agents = get_swarm_agents(self.inputs)

    @start()
    def phase_1_discovery(self):
        """Phase 1: Research & Audit (sequential to reduce rate limiting)."""
        tasks = []

        if "analyst" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Identify market gaps for {self.state.biz_name} in {self.state.location}. "
                    "Return a structured analysis with: pricing gaps, positioning, top 3 offers, and quick wins."
                ),
                agent=self.agents["analyst"],
                expected_output="Structured market analysis."
            ))

        if "audit" in self.active_swarm:
            url = self.state.url or "the website"
            tasks.append(Task(
                description=(
                    f"Audit {url} for conversion friction. "
                    "DO NOT dump raw HTML. Provide: top issues, impact, and fixes. Keep it executive-friendly."
                ),
                agent=self.agents["audit"],
                expected_output="Executive technical audit."
            ))

        if "vision" in self.active_swarm:
            tasks.append(Task(
                description=f"Provide a forensic visual audit for {self.state.biz_name}.",
                agent=self.agents["vision"],
                expected_output="Forensic visual report."
            ))

        if tasks:
            crew = Crew(
                agents=[t.agent for t in tasks],
                tasks=tasks,
                process=Process.sequential
            )
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            for t in tasks:
                out = str(getattr(t.output, "raw", "") or "")
                desc = (t.description or "").lower()

                if "market gaps" in desc or "market" in desc:
                    self.state.market_data = out

                elif "audit" in desc or "conversion friction" in desc:
                    self.state.website_audit = out if len(out) <= 4500 else out[:4500] + "\n\n[Output truncated]"

                elif "forensic" in desc or "visual" in desc:
                    self.state.vision_intel = out

        return "trigger_production"

    @listen("trigger_production")
    def phase_2_execution(self):
        """Phase 2: Production tasks (sequential, retry on 429)."""
        tasks = []

        if "strategist" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day execution roadmap for {self.state.biz_name} in {self.state.location}. "
                    "Include: priorities, weekly plan, KPIs, and quick wins. Make it CEO-ready."
                ),
                agent=self.agents["strategist"],
                expected_output="Executive strategic brief + 30-day roadmap."
            ))

        if "ads" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Generate deployable ad copy for {self.state.biz_name} targeting {self.state.location}. "
                    "Deliver: Google Search headlines/descriptions + Meta hooks + primary text. Format as Markdown tables."
                ),
                agent=self.agents["ads"],
                expected_output="Markdown ad copy tables."
            ))

        if "creative" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create creative direction for {self.state.biz_name}. "
                    "Deliver: 5 creative concepts + ad angles + Midjourney/Canva prompt pack."
                ),
                agent=self.agents["creative"],
                expected_output="Creative direction + prompt pack."
            ))

        if "seo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Write an SEO authority article for {self.state.biz_name} in {self.state.location}. "
                    "Use headings, FAQs, local intent, and a strong CTA."
                ),
                agent=self.agents["seo"],
                expected_output="SEO authority article."
            ))

        if "social" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day social content calendar for {self.state.biz_name} in {self.state.location}. "
                    "Include daily post topics, hooks, and CTAs."
                ),
                agent=self.agents["social"],
                expected_output="30-day social calendar."
            ))

        if "geo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a local GEO plan for {self.state.biz_name} in {self.state.location}. "
                    "Include citations, GBP optimization, and near-me targeting steps."
                ),
                agent=self.agents["geo"],
                expected_output="Local GEO plan."
            ))

        if tasks:
            crew = Crew(
                agents=[t.agent for t in tasks],
                tasks=tasks,
                process=Process.sequential
            )
            kickoff_with_retry(crew, retries=2, base_sleep=15)

            for t in tasks:
                out = str(getattr(t.output, "raw", "") or "")
                desc = (t.description or "").lower()

                if "execution roadmap" in desc or "roadmap" in desc or "ceo-ready" in desc:
                    self.state.strategist_brief = out

                elif "deployable ad copy" in desc or "google search" in desc or "meta hooks" in desc:
                    self.state.ads_output = out

                elif "creative direction" in desc or "prompt pack" in desc or "creative concepts" in desc:
                    self.state.creative_pack = out

                elif "seo authority article" in desc or "seo" in desc:
                    self.state.seo_article = out

                elif "social content calendar" in desc or "social" in desc:
                    self.state.social_plan = out

                elif "local geo plan" in desc or "citations" in desc or "gbp" in desc:
                    self.state.geo_intel = out

        return "finalize_branding"

    @listen("finalize_branding")
    def add_stakeholder_branding(self):
        """Phase 3: Assemble the master full report for exports."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        package = self.inputs.get("package", "Basic")
        custom_logo_file = self.inputs.get("custom_logo")

        logo_html = ""
        if package != "Basic" and custom_logo_file is not None:
            try:
                bytes_data = custom_logo_file.getvalue()
                b64_logo = base64.b64encode(bytes_data).decode()
                logo_html = f'<div style="text-align:center;"><img src="data:image/png;base64,{b64_logo}" width="200"></div>'
            except Exception:
                logo_html = ""
        else:
            logo_html = "<div style='text-align:center;'>🛡️ <strong>SYSTEM GENERATED REPORT</strong></div>"

        header = f"""
{logo_html}
# {self.state.biz_name} Intelligence Report
**Date:** {now} | **Location:** {self.state.location} | **Plan:** {package}
---
""".strip()

        self.state.full_report = (
            f"{header}\n\n"
            f"## 🕵️ Market Analysis\n{self.state.market_data}\n\n"
            f"## 🌐 Website Audit\n{self.state.website_audit}\n\n"
            f"## 👔 Executive Strategy\n{self.state.strategist_brief}\n\n"
            f"## 📣 Ads Output\n{self.state.ads_output}\n\n"
            f"## 🎨 Creative Pack\n{self.state.creative_pack}\n\n"
            f"## ✍️ SEO Authority Article\n{self.state.seo_article}\n\n"
            f"## 📍 GEO Intelligence\n{self.state.geo_intel}\n\n"
            f"## 📱 Social Roadmap\n{self.state.social_plan}\n\n"
            f"## 👁️ Visual Forensics\n{self.state.vision_intel}\n"
        )

        return "branding_complete"


# ============================================================
# 5) WRAPPER CALLED BY app.py
# ============================================================
def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Returns keys that match app.py tabs:
    analyst, ads, creative, strategist, social, geo, audit, seo, full_report
    """
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()

    master_data = {
        "analyst": getattr(flow.state, "market_data", "No analyst output found."),
        "ads": getattr(flow.state, "ads_output", "No ads output found."),
        "creative": getattr(flow.state, "creative_pack", "No creative output found."),
        "strategist": getattr(flow.state, "strategist_brief", "No strategy output found."),
        "social": getattr(flow.state, "social_plan", "No social output found."),
        "geo": getattr(flow.state, "geo_intel", "No GEO output found."),
        "audit": getattr(flow.state, "website_audit", "No audit output found."),
        "seo": getattr(flow.state, "seo_article", "No SEO output found."),
        "vision": getattr(flow.state, "vision_intel", "No vision output found."),
        "full_report": getattr(flow.state, "full_report", "Full report generation failed."),
    }

    active_list = inputs.get("active_swarm", []) or []
    active_list = [str(k).strip() for k in active_list]

    return {k: v for k, v in master_data.items() if k in active_list or k == "full_report"}
