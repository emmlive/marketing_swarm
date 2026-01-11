import os
import json
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force fresh read of environment variables
load_dotenv(override=True)

# --- 1. SHARED STATE (STRICTLY ISOLATED FIELDS) ---
class SwarmState(BaseModel):
    market_data: str = "Analysis pending..."
    competitor_ads: str = "Ad tracking pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
    geo_intel: str = "GEO mapping pending..."
    seo_article: str = "SEO Content pending..." 
    strategist_brief: str = "Final brief pending..."
    production_schedule: str = "Roadmap pending..."

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4 
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Market Analyst (The Fact-Finder)",
            goal=f"Extract competitor gaps in {city} and identify live advertising copy of rivals.",
            backstory="Literalist data scientist. You find exactly what competitors are saying in live ads.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Creative Director (The Multimodal Architect)",
            goal="Transform Analyst data into branded assets and cinematic video prompts for Veo.",
            backstory="Multimodal architect. You build assets anchored 100% in tool-found facts.",
            llm=gemini_llm, verbose=True
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect (The Blogger)",
            goal="Write a 2,000-word high-authority SEO article based on findings.",
            backstory="Expert in E-E-A-T technical SEO blogging.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The UX Skeptic)",
            goal=f"Diagnose conversion leaks on {url}.",
            backstory="UX psychologist using the Scrape tool to find actual Friction Points.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Specialist",
            goal="Repurpose strategy into viral hooks for Meta, Google, and LinkedIn.",
            backstory="Algorithmic engagement hooks expert.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (AI Search Optimization)",
            goal=f"Optimize {biz} for citation velocity in AI Search Engines.",
            backstory="AI Citation and Maps visibility expert.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Swarm Commander)",
            goal="Orchestrate agents and validate outputs for ROI alignment.",
            backstory="Final commander. You ensure a 30-day roadmap is grounded in truth.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW ---
# 
class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_discovery(self):
        """Step 1: Grounded Research & Ad Tracking"""
        analyst_task = Task(
            description=f"Identify top 3 competitors for {self.inputs['biz_name']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="JSON Market Report."
        )
        
        ad_track_task = Task(
            description=f"Find live Google/Meta ad copy for competitors in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Competitor Ad Report."
        )

        active_tasks = [analyst_task, ad_track_task]
        
        auditor_task = None
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for UX friction.",
                agent=self.agents["web_auditor"],
                expected_output="Technical Audit findings."
            )
            active_tasks.append(auditor_task)
            
        Crew(agents=list(self.agents.values()), tasks=active_tasks, process=Process.sequential).kickoff()
        
        self.state.market_data = analyst_task.output.raw
        self.state.competitor_ads = ad_track_task.output.raw
        if auditor_task:
            self.state.website_audit = auditor_task.output.raw
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Creative, SEO & Content Production (Hardened Assignment)"""
        creative_task = Task(
            description="Build 3 ad variants and a specific 'Video Prompt:' for Veo.",
            agent=self.agents["creative"],
            expected_output="Branded Assets + Prompt."
        )
        
        production_tasks = [creative_task]
        
        seo_task = None
        if self.toggles.get('seo'):
            seo_task = Task(
                description="Write a 2,000-word authority SEO article based on research.",
                agent=self.agents["seo_blogger"],
                expected_output="2,000-word SEO Article."
            )
            production_tasks.append(seo_task)

        social_task = None
        if self.toggles.get('social'):
            social_task = Task(description="Viral hooks.", agent=self.agents["social_agent"], expected_output="Social Plan.")
            production_tasks.append(social_task)

        geo_task = None
        if self.toggles.get('geo'):
            geo_task = Task(description="GEO AI search plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report.")
            production_tasks.append(geo_task)

        Crew(agents=list(self.agents.values()), tasks=production_tasks, process=Process.sequential).kickoff()
        
        # ASSIGNMENT BY OBJECT REFERENCE (Index-Proof)
        self.state.ad_drafts = creative_task.output.raw
        if seo_task: self.state.seo_article = seo_task.output.raw
        if social_task: self.state.social_plan = social_task.output.raw
        if geo_task: self.state.geo_intel = geo_task.output.raw
        
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        val_task = Task(
            description="Synthesize into a final 30-day ROI brief.",
            agent=self.agents["strategist"],
            expected_output="Master Brief and Roadmap."
        )
        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    formatted_string_report = f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery, Ad Tracking & Site Audit
### Market Intelligence
{flow.state.market_data}

### Live Competitor Ad Tracking
{flow.state.competitor_ads}

### Technical Website Audit
{flow.state.website_audit}

## 📝 Phase 2: Execution, Creative, SEO & Social
### Branded Creative Assets
{flow.state.ad_drafts}

### Long-Form SEO Content
{flow.state.seo_article}

### Local GEO AI Optimization
{flow.state.geo_intel}

### Social Media Distribution
{flow.state.social_plan}

## 🗓️ Phase 3: Managerial Review & Roadmap
{flow.state.production_schedule}

---
*Generated by TechInAdvance AI | Strategist Verified*
"""

    return {
        "analyst": flow.state.market_data,
        "ads": flow.state.competitor_ads,
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article,
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report
    }
