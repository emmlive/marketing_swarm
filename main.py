import os
import base64
from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import BaseModel
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

import streamlit as st

# Force fresh read of environment variables (local dev)
load_dotenv(override=True)


# ============================================================
# 0) SECRETS / ENV HELPERS
# ============================================================
def _get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get from Streamlit secrets first, then env."""
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
    """
    Retries crew.kickoff() on Gemini 429 rate limit errors.
    """
    for attempt in range(retries + 1):
        try:
            return crew.kickoff()
        except Exception as e:
            if _is_429(e) and attempt < retries:
                wait = base_sleep * (attempt + 1)
                # Don't crash; just wait and retry
                st.warning(f"⚠️ Rate limited (429). Retrying in {wait}s (attempt {attempt+1}/{retries})...")
                import time
                time.sleep(wait)
                continue
            raise


# ============================================================
# 1) SHARED STATE
# ============================================================
class SwarmState(BaseModel):
    # Inputs
    biz_name: str = ""
    location: str = ""
    directives: str = ""
    url: str = ""

    # Outputs
    market_data: str = "Agent not selected for this run."
    competitor_ads: str = "Agent not selected for this run."
    vision_intel: str = "Agent not selected for this run."
    website_audit: str = "Agent not selected for this run."
    social_plan: str = "Agent not selected for this run."
    geo_intel: str = "Agent not selected for this run."
    seo_article: str = "Agent not selected for this run."
    strategist_brief: str = "Agent not selected for this run."

    # Master export
    full_report: str = "Full report not generated."


# ============================================================
# 2) ENGINE INITIALIZATION
# ============================================================
GOOGLE_API_KEY = _get_secret("GOOGLE_API_KEY") or _get_secret("GEMINI_API_KEY") or _get_secret("GENAI_API_KEY")
SERPER_API_KEY = _get_secret("SERPER_API_KEY")

if not GOOGLE_API_KEY:
    raise RuntimeError(
        "Missing GOOGLE_API_KEY (Gemini). Add it to Streamlit Cloud Secrets or environment variables."
    )

# LLM (Gemini via CrewAI)
gemini_llm = LLM(
    model="google/gemini-2.0-flash",
    api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

# Tools
scrape_tool = ScrapeWebsiteTool()
search_tool = SerperDevTool(api_key=SERPER_API_KEY) if SERPER_API_KEY else None


# ============================================================
# 3) AGENTS
# ============================================================
def get_swarm_agents(inputs: Dict[str, Any]) -> Dict[str, Agent]:
    biz = inputs.get("biz_name", "The Business")
    city = inputs.get("city", "the local area")
    url = inputs.get("url") or inputs.get("website") or "the provided website"
    reqs = inputs.get("directives") or inputs.get("custom_reqs") or "Standard growth optimization."

    analyst_tools = [scrape_tool]
    if search_tool:
        analyst_tools = [search_tool, scrape_tool]

    return {
        # Keys match app.py toggles: analyst, ads, creative, strategist, social, geo, audit, seo
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=f"You are a market scientist. You quantify market entry gaps and competitor fatigue. Priority: {reqs}",
            tools=analyst_tools,
            llm=gemini_llm,
            verbose=True
        ),
        "ads": Agent(
            role="Performance Ads Architect",
            goal=f"Generate deployable ad copy for {biz} targeting {city}.",
            backstory="You are a direct-response ad specialist for Google Search and Meta. You write scroll-stopping hooks and conversion-focused copy.",
            llm=gemini_llm,
            verbose=True
        ),
        "creative": Agent(
            role="Creative Director (Assets & Prompts)",
            goal=f"Create high-converting creative direction and prompt packs for {biz}.",
            backstory="You produce visual ad concepts and prompt packs that convert (Midjourney/Canva-ready).",
            llm=gemini_llm,
            verbose=True
        ),
        "seo": Agent(
            role="SEO Content Architect",
            goal=f"Write an SEO authority article for {biz} in {city}.",
            backstory="Expert in E-E-A-T and Search Generative Experience optimization. You write helpful, structured content that ranks and converts.",
            llm=gemini_llm,
            verbose=True
        ),
        "audit": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose technical conversion leaks on {url}.",
            backstory="You identify digital friction points, speed/mobile issues, and trust blockers that prevent ROI.",
            tools=[scrape_tool],
            llm=gemini_llm,
            verbose=True
        ),
        "social": Agent(
            role="Social Distribution Architect",
            goal=f"Create a 30-day social plan for {biz} in {city}.",
            backstory="Expert in social algorithms, hooks, and repurposing strategy into daily posts that drive inbound leads.",
            llm=gemini_llm,
            verbose=True
        ),
        "geo": Agent(
            role="GEO / Local Search Specialist",
            goal=f"Optimize local visibility and citations for {biz} in {city}.",
            backstory="Expert in local ranking factors and AI-driven map discovery. You produce actionable local SEO steps.",
            llm=gemini_llm,
            verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal=f"Synthesize intelligence into a 30-day execution plan for {biz}.",
            backstory="You are the integrator. You turn research into a CEO-ready plan with quick wins and priorities.",
            llm=gemini_llm,
            verbose=True
        ),
        # Optional vision agent (only used if you later add a toggle)
        "vision": Agent(
            role="Technical Visual Auditor & Forensic Analyst",
            goal=f"Analyze field photos to identify damage/defects for {biz}.",
            backstory="You are a technical forensics expert. You provide evidence-based findings and recommended actions.",
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
        self.state.url = self.inputs.get("url", "")

        self.agents = get_swarm_agents(self.inputs)
        self.active_swarm = self.inputs.get("active_swarm", []) or []

    @start()
    def phase_1_discovery(self):
        """Phase 1: Research & Executive Audit (sequential, retry on 429)."""
        tasks = []

        if "analyst" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Identify market gaps for {self.state.biz_name} in {self.state.location}. "
                    f"Return a structured analysis with: pricing gaps, positioning, 3 offers, and quick-win tactics."
                ),
                agent=self.agents["analyst"],
                expected_output="A structured Market Analysis."
            ))

        if "audit" in self.active_swarm:
            url = self.inputs.get("url") or self.inputs.get("website") or "the website"
            tasks.append(Task(
                description=(
                    f"Audit {url} for conversion friction. "
                    "DO NOT dump raw HTML. Provide: top issues, impact, and fixes. Keep it executive-friendly."
                ),
                agent=self.agents["audit"],
                expected_output="Executive Technical Audit."
            ))

        # Optional: if you ever toggle vision later
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
                elif "audit" in desc or "conversion" in desc:
                    # Clip extreme length to keep UI clean
                    self.state.website_audit = out if len(out) <= 3500 else out[:3500] + "\n\n[Output truncated for UI]"
                elif "forensic" in desc or "visual" in desc:
                    self.state.vision_intel = out

        return "trigger_production"

    @listen("trigger_production")
    def phase_2_execution(self):
        """Phase 2: Production (sequential, retry on 429)."""
        tasks = []

        if "strategist" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day execution roadmap for {self.state.biz_name} in {self.state.location}. "
                    "Include: priorities, weekly plan, KPIs, and quick wins."
                ),
                agent=self.agents["strategist"],
                expected_output="Executive Strategic Brief."
            ))

        # 'ads' is the app toggle; produce ad suite here
        if "ads" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Generate a multichannel ad suite for {self.state.biz_name} in {self.state.location}: "
                    "Google Search headlines/descriptions + Meta primary text + hooks. Format as a Markdown table."
                ),
                agent=self.agents["ads"],
                expected_output="Markdown Ad Copy Table."
            ))

        # 'creative' toggle (asset direction + prompts)
        if "creative" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create creative direction for {self.state.biz_name}: "
                    "5 concepts + color/typography notes + Midjourney/Canva-ready prompt pack."
                ),
                agent=self.agents["creative"],
                expected_output="Creative direction and prompt pack."
            ))

        if "seo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Write an SEO authority article for {self.state.biz_name} in {self.state.location}. "
                    "Use headings, FAQs, and strong local intent. Be helpful and conversion-aware."
                ),
                agent=self.agents["seo"],
                expected_output="Full Technical Article."
            ))

        if "social" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a 30-day social calendar for {self.state.biz_name} in {self.state.location}. "
                    "Include daily post ideas, hooks, and CTA."
                ),
                agent=self.agents["social"],
                expected_output="Social schedule."
            ))

        if "geo" in self.active_swarm:
            tasks.append(Task(
                description=(
                    f"Create a local GEO plan for {self.state.biz_name} in {self.state.location}. "
                    "Include citation plan, GBP optimizations, and near-me targeting steps."
                ),
                agent=self.agents["geo"],
                expected_output="Local SEO strategy."
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

                if "30-day execution roadmap" in desc or "execution roadmap" in desc or "roadmap" in desc:
                    self.state.strategist_brief = out
                elif "multichannel ad suite" in desc or "ad suite" in desc or "google search" in desc:
                    self.state.competitor_ads = out
                elif "creative direction" in desc or "prompt pack" in desc:
                    # Store creative direction into competitor_ads if you prefer; here we keep it separate by using market_data? no
                    # We'll store it in competitor_ads ONLY if ads not selected; otherwise keep it appended.
                    if self.state.competitor_ads and self.state.competitor_ads != "Agent not selected for this run.":
                        self.state.competitor_ads += "\n\n---\n\n## 🎨 Creative Direction & Prompt Pack\n" + out
                    else:
                        self.state.competitor_ads = "## 🎨 Creative Direction & Prompt Pack\n" + out
                elif "seo authority article" in desc or "seo" in desc:
                    self.state.seo_article = out
                elif "social calendar" in desc or "30-day social" in desc:
                    self.state.social_plan = out
                elif "local geo plan" in desc or "geo plan" in desc or "citation" in desc:
                    self.state.geo_intel = out

        return "finalize_branding"

    @listen("finalize_branding")
    def add_stakeholder_branding(self):
        """Phase 3: Assemble full report string."""
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
            f"## 📣 Ads & Creative\n{self.state.competitor_ads}\n\n"
            f"## ✍️ SEO Authority Article\n{self.state.seo_article}\n\n"
            f"## 📍 GEO Intelligence\n{self.state.geo_intel}\n\n"
            f"## 📱 Social Roadmap\n{self.state.social_plan}\n\n"
            f"## 👁️ Visual Forensics\n{self.state.vision_intel}\n"
        )

        return "branding_complete"


# ============================================================
# 5) EXECUTION WRAPPER (CALLED BY app.py)
# ============================================================
def run_marketing_swarm(inputs: Dict[str, Any]) -> Dict[str, str]:
    """
    Executes the Flow and returns a dict keyed exactly to app.py tab keys:
    analyst, ads, creative, strategist, social, geo, audit, seo, full_report
    """
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()

    # Bridge backend state -> frontend tabs
    master_data = {
        "analyst": getattr(flow.state, "market_data", "No analyst data found."),
        # app key is 'ads' (we store combined ads+creative direction in competitor_ads)
        "ads": getattr(flow.state, "competitor_ads", "No ad output found."),
        # keep creative also available; if you want separate, change mapping strategy
        "creative": getattr(flow.state, "competitor_ads", "No creative output found."),
        "strategist": getattr(flow.state, "strategist_brief", "Final brief pending."),
        "social": getattr(flow.state, "social_plan", "Social roadmap not generated."),
        "geo": getattr(flow.state, "geo_intel", "GEO data not selected."),
        "seo": getattr(flow.state, "seo_article", "SEO content not generated."),
        "audit": getattr(flow.state, "website_audit", "Website audit not generated."),
        "full_report": getattr(flow.state, "full_report", "Full report generation failed.")
    }

    active_list = inputs.get("active_swarm", []) or []

    # Return only requested keys + full_report
    return {k: v for k, v in master_data.items() if k in active_list or k == "full_report"}
