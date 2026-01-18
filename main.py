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

# --- 1. SHARED STATE (EXECUTIVE DATA SLOTS) ---
class SwarmState(BaseModel):
    market_data: str = "Agent not selected for this run."
    competitor_ads: str = "Ad tracking pending..."
    vision_intel: str = "Agent not selected for this run." 
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit not selected for this run."
    social_plan: str = "Social strategy not selected."
    geo_intel: str = "GEO mapping not selected."
    seo_article: str = "SEO Content not selected." 
    strategist_brief: str = "Final brief pending..."
    production_schedule: str = "Roadmap pending..."

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3 
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (VALIDATED WITH BACKSTORIES) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')
    reqs = inputs.get('custom_reqs', 'Standard growth optimization.')

    return {
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps for {biz} in {city}.",
            backstory=f"You are a market scientist. You quantify 'Market Entry Gaps' and 'Competitor Fatigue'. Priority: {reqs}",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "vision_agent": Agent(
            role="Technical Visual Auditor & Forensic Analyst",
            goal=f"Analyze field photos to identify damage or defects for {biz}.",
            backstory="You are a technical forensics expert. You inspect photos and provide evidence-based reports.",
            llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Multichannel Direct-Response Ad Architect",
            goal="Engineer deployable ad copy for Google Search, Facebook, and Instagram.",
            backstory="You are an expert copywriter specializing in character-limited ad formats and high-conversion hooks.",
            llm=gemini_llm, verbose=True
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect", 
            goal="Compose high-authority technical articles.", 
            backstory="Expert in E-E-A-T and Google Search Generative Experience optimization.", 
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Conversion UX Auditor", 
            goal=f"Diagnose technical conversion leaks on {url}.", 
            backstory="You identify digital friction points that prevent ROI.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Architect", 
            goal="Repurpose strategy into a viral broadcast plan.", 
            backstory="Expert in social media algorithms and viral hook engineering.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist", 
            goal=f"Optimize citation velocity in {city}.", 
            backstory="Expert in Local Ranking Factors and AI-driven map discovery.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer", 
            goal="Synthesize all agent intelligence into a roadmap.", 
            backstory="The ultimate decision maker. You ensure all output aligns with the CEO's growth goals.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW ---
class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_discovery(self):
        """Step 1: Filtered Discovery & Visual Forensics"""
        active_tasks = []
        
        if self.toggles.get('analyst'):
            analyst_task = Task(
                description=f"Identify 'Market Entry Gaps' and analyze competitor ad hooks in {self.inputs['city']}.",
                agent=self.agents["analyst"],
                expected_output="Markdown Report with Competitor Fatigue analysis."
            )
            active_tasks.append(analyst_task)

        if self.toggles.get('vision'):
            vision_task = Task(
                description=f"Analyze provided field photos for technical defects or rival brand weaknesses.",
                agent=self.agents["vision_agent"],
                expected_output="Detailed Forensic Report identifying damage and design gaps."
            )
            active_tasks.append(vision_task)
            
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Executive Technical Audit."
            )
            active_tasks.append(auditor_task)

        if active_tasks:
            active_agents = [task.agent for task in active_tasks]
            Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
            
            for task in active_tasks:
                out = str(task.output.raw)
                if "Market" in task.description: self.state.market_data = out
                if "Forensic" in task.description or "field photos" in task.description: self.state.vision_intel = out
                if "conversion" in task.description: self.state.website_audit = out
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Filtered Production & Ad Engineering"""
        production_tasks = []
        
        if self.toggles.get('builder'): 
            creative_task = Task(
                description="""Engineer a Multichannel Ad Suite: 
                1. Google (3 Headlines, 2 Desc), 2. Meta (Headline/Text), 3. Veo Prompt.""",
                agent=self.agents["creative"],
                expected_output="Markdown table with platform-specific copy."
            )
            production_tasks.append(creative_task)

        if self.toggles.get('seo'):
            production_tasks.append(Task(description="Compose a technical SEO article.", agent=self.agents["seo_blogger"], expected_output="Technical article."))
        if self.toggles.get('social'):
            production_tasks.append(Task(description="Create a 30-day viral schedule.", agent=self.agents["social_agent"], expected_output="Viral Hooks."))
        if self.toggles.get('geo'):
            production_tasks.append(Task(description="Develop local GEO plan.", agent=self.agents["geo_specialist"], expected_output="GEO Intelligence."))

        if production_tasks:
            active_agents = [task.agent for task in production_tasks]
            Crew(agents=active_agents, tasks=production_tasks, process=Process.sequential).kickoff()
            
            for task in production_tasks:
                out = str(task.output.raw)
                if "Multichannel" in task.description: self.state.ad_drafts = out
                if "SEO" in task.description: self.state.seo_article = out
                if "viral" in task.description: self.state.social_plan = out
                if "GEO" in task.description: self.state.geo_intel = out
            
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 3: ROI Roadmap Synthesis"""
        if self.toggles.get('manager'):
            val_task = Task(
                description="Synthesize all data into a 30-day ROI Growth Roadmap.",
                agent=self.agents["strategist"],
                expected_output="Master Growth Brief: Milestones and ROI Projections."
            )
            result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
            self.state.strategist_brief = str(result)
            self.state.production_schedule = str(result)
        
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    # 1. Initialize and execute the Swarm Flow
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # 2. Capture the active list from the UI (Folder 05 sync)
    active_list = inputs.get('active_swarm', [])

    # 3. YOUR FORMATTED STRING (Keep this for the master export)
    # We use .get() here as well to prevent crashes if an agent is skipped
    formatted_string_report = f"""
# 🚀 {inputs.get('biz_name', 'Enterprise')} | EXECUTIVE INTELLIGENCE SUMMARY

## 🔍 PHASE 1: MARKET DISCOVERY & AUDIT
### Strategic Market Analysis
{flow.state.market_data}

### 👁️ Visual Forensics & Field Audit
{flow.state.vision_intel}

### Technical Website Audit
{flow.state.website_audit}

## 📝 PHASE 2: CONTENT & MULTI-PLATFORM ADS
### Deployable Ad Suite (Google, FB, IG)
{flow.state.ad_drafts}

### Authority SEO Content
{flow.state.seo_article}

### Local GEO Dominance
{flow.state.geo_intel}

### Social Roadmap
{flow.state.social_plan}

## 🗓️ PHASE 3: 30-DAY ROI ROADMAP
{flow.state.production_schedule}
"""

    # 4. SYSTEMIC MAPPING (Matches Folder 06 keys in app.py)
    master_data = {
        "analyst": flow.state.market_data,
        "ads": flow.state.competitor_ads,
        "vision": flow.state.vision_intel, 
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article,
        "audit": flow.state.website_audit,
        "full_report": formatted_string_report 
    }

    # 5. FILTER: Return only toggled agents + the full summary
    return {k: v for k, v in master_data.items() if k in active_list or k == "full_report"}
