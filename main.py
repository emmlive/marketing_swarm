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
    # New Input Fields (Required for your __init__ to work)
    biz_name: str = ""
    location: str = ""
    directives: str = ""

    # Existing Agent Output Fields
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

# --- 2. ENGINE INITIALIZATION (Streamlit Cloud & Secrets Optimized) ---
import streamlit as st

# 1. Initialize LLM using the secret key directly
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=st.secrets["GOOGLE_API_KEY"], # Pulls from secrets.toml
    temperature=0.3 
)

# 2. Initialize Tools using the secret keys directly
search_tool = SerperDevTool(api_key=st.secrets["SERPER_API_KEY"]) # Pulls from secrets.toml
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
        
        # Hydrate State
        self.state.biz_name = inputs.get('biz_name', 'Unknown Brand')
        self.state.location = inputs.get('city', 'USA')
        self.state.directives = inputs.get('directives', '')
        
        self.agents = get_swarm_agents(inputs)
        self.active_swarm = inputs.get('active_swarm', [])

    @start()
    def phase_1_discovery(self):
        """Phase 1: Market Research & Audit"""
        active_tasks = []
        
        if "analyst" in self.active_swarm:
            analyst_task = Task(
                description=f"Analyze market gaps for {self.state.biz_name} in {self.state.location}.",
                agent=self.agents["analyst"],
                expected_output="Markdown Report."
            )
            active_tasks.append(analyst_task)

        if "vision" in self.active_swarm:
            vision_task = Task(
                description=f"Forensic visual audit for {self.state.biz_name}.",
                agent=self.agents["vision_agent"],
                expected_output="Visual Report."
            )
            active_tasks.append(vision_task)
            
        if "audit" in self.active_swarm:
            active_tasks.append(Task(
                description=f"Scan {self.inputs.get('url', 'web')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Technical Audit."
            ))

        if active_tasks:
            crew = Crew(
                agents=[t.agent for t in active_tasks],
                tasks=active_tasks,
                process=Process.sequential
            )
            crew.kickoff()
            
            # Save results to state
            for task in active_tasks:
                out = str(task.output.raw)
                if "market" in task.description.lower(): self.state.market_data = out
                if "visual" in task.description.lower(): self.state.vision_intel = out
                if "scan" in task.description.lower(): self.state.website_audit = out
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Phase 2: Content Generation"""
        production_tasks = []
        
        if "creative" in self.active_swarm:
            production_tasks.append(Task(
                description=f"Ad suite for {self.state.biz_name}.", 
                agent=self.agents["creative"], 
                expected_output="Ad copy."
            ))

        if "seo" in self.active_swarm:
            production_tasks.append(Task(
                description="SEO Article.", 
                agent=self.agents["seo_blogger"], 
                expected_output="Blog post."
            ))

        if production_tasks:
            crew = Crew(
                agents=[t.agent for t in production_tasks],
                tasks=production_tasks,
                process=Process.sequential
            )
            crew.kickoff()
            
            for task in production_tasks:
                out = str(task.output.raw)
                if "Ad suite" in task.description: self.state.ad_drafts = out
                if "SEO" in task.description: self.state.seo_article = out
            
        return "execution_complete"

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

# 4. SYSTEMIC MAPPING (Revised for Flow State Sync)
    # This dictionary maps internal flow state variables to the UI keys in app.py
    master_data = {
        "analyst": getattr(flow.state, 'market_data', "No analyst data found."),
        "ads": getattr(flow.state, 'competitor_ads', "No ad data found."),
        "vision": getattr(flow.state, 'vision_intel', "No visual intel found."), 
        "creative": getattr(flow.state, 'ad_drafts', "No creative drafts found."),
        "strategist": getattr(flow.state, 'strategist_brief', "Final brief pending."),
        "social": getattr(flow.state, 'social_plan', "Social roadmap not generated."),
        "geo": getattr(flow.state, 'geo_intel', "GEO data not selected."),
        "seo": getattr(flow.state, 'seo_article', "SEO Content not selected."),
        "audit": getattr(flow.state, 'website_audit', "Website audit pending."),
        "full_report": formatted_string_report 
    }

    # 5. FILTERED RETURN
    # We pull the 'active_swarm' list from the inputs we sent from app.py
    active_list = inputs.get('active_swarm', [])
    
    # We only return what the user asked for + the full summary
    return {k: v for k, v in master_data.items() if k in active_list or k == "full_report"}
