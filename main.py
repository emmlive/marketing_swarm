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
        """Phase 1: Research & Executive Audit"""
        active_tasks = []
        
        if "analyst" in self.active_swarm:
            active_tasks.append(Task(
                description=f"Identify market gaps for {self.state.biz_name} in {self.state.location}.",
                agent=self.agents["analyst"],
                expected_output="A structured Market Analysis."
            ))

        if "vision" in self.active_swarm:
            active_tasks.append(Task(
                description=f"Forensic visual audit for {self.state.biz_name}.",
                agent=self.agents["vision_agent"],
                expected_output="Forensic visual report."
            ))
            
        if "audit" in self.active_swarm:
            active_tasks.append(Task(
                description=f"Scan {self.inputs.get('url', 'the web')} for conversion friction. DO NOT dump raw HTML. Provide 3-5 executive bullet points.",
                agent=self.agents["web_auditor"],
                expected_output="Executive Technical Audit."
            ))

        if active_tasks:
            discovery_crew = Crew(
                agents=[t.agent for t in active_tasks],
                tasks=active_tasks,
                process=Process.sequential
            )
            discovery_crew.kickoff()
            
            for task in active_tasks:
                out = str(task.output.raw)
                desc = task.description.lower()
                # AUDITOR CLEANUP: Prevents the 'Copy-Paste' look
                if "scan" in desc:
                    self.state.website_audit = out if len(out) < 2000 else out[:2000] + "\n\n[Full technical data archived...]"
                elif "market" in desc: self.state.market_data = out
                elif "forensic" in desc: self.state.vision_intel = out
            
        return "trigger_production" # Explicit signal for Phase 2

    @listen("trigger_production")
    def phase_2_execution(self):
        """Phase 2: Strategy & High-Value Production"""
        production_tasks = []
        
        if "strategist" in self.active_swarm:
            production_tasks.append(Task(
                description=f"Master Strategy for {self.state.biz_name}.",
                agent=self.agents["strategist"],
                expected_output="Executive Strategic Brief."
            ))

        if "creative" in self.active_swarm:
            production_tasks.append(Task(
                description="Multichannel Ad Suite Engineering.",
                agent=self.agents["creative"],
                expected_output="Markdown Ad Copy Table."
            ))

        if "seo" in self.active_swarm:
            production_tasks.append(Task(
                description="Authority SEO-Optimized Article.",
                agent=self.agents["seo_blogger"],
                expected_output="Full Technical Article."
            ))

        if "social" in self.active_swarm:
            production_tasks.append(Task(description="30-Day Viral Calendar.", agent=self.agents["social_agent"], expected_output="Social Schedule."))

        if "geo" in self.active_swarm:
            production_tasks.append(Task(description="Local GEO Intelligence.", agent=self.agents["geo_specialist"], expected_output="Local SEO Strategy."))

        if production_tasks:
            prod_crew = Crew(
                agents=[t.agent for t in production_tasks],
                tasks=production_tasks,
                process=Process.sequential
            )
            prod_crew.kickoff()
            
            for task in production_tasks:
                out = str(task.output.raw)
                desc = task.description.lower()
                if "strategy" in desc: self.state.strategist_brief = out
                elif "multichannel" in desc: self.state.ad_drafts = out
                elif "seo" in desc: self.state.seo_article = out
                elif "viral" in desc: self.state.social_plan = out
                elif "geo" in desc: self.state.geo_intel = out
            
        return "finalize_branding"

    @listen("finalize_branding")
    def add_stakeholder_branding(self):
        """Phase 3: Injecting Professional Branding, Timestamps, and Tiered Logos"""
        from datetime import datetime
        import base64
        
        # 1. Capture Current Timestamp
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 2. LOGO INJECTION LOGIC
        package = self.inputs.get('package', 'Basic')
        custom_logo_file = self.inputs.get('custom_logo') 
        logo_html = ""
        
        # Only allow custom logos for Pro, Enterprise, or Admin
        if package != "Basic" and custom_logo_file is not None:
            try:
                # Read the file object from Streamlit and encode to base64
                bytes_data = custom_logo_file.getvalue()
                b64_logo = base64.b64encode(bytes_data).decode()
                # We use HTML img tag for precise PDF layout control
                logo_html = f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_logo}" width="200"></div>'
            except Exception as e:
                logo_html = ""
        else:
            # Branding for Basic plan
            logo_html = "<div style='text-align: center;'>🛡️ <strong>SYSTEM GENERATED REPORT</strong></div>"

        # 3. CONSTRUCT STAKEHOLDER HEADER
        header = f"""
{logo_html}
# {self.state.biz_name} Intelligence Report
**Date:** {now} | **Location:** {self.state.location} | **Plan:** {package}
---
        """
        
        # 4. ASSEMBLE MASTER REPORT FOR PDF
        # We combine all results into one master string
        self.state.full_report = f"{header}\n\n" \
            f"## 🕵️ Market Analysis\n{self.state.market_data}\n\n" \
            f"## 👔 Executive Strategy\n{self.state.strategist_brief}\n\n" \
            f"## 🎨 Multichannel Creative\n{self.state.ad_drafts}\n\n" \
            f"## ✍️ SEO Authority Article\n{self.state.seo_article}\n\n" \
            f"## 🌐 Website Audit\n{self.state.website_audit}\n\n" \
            f"## 📍 GEO Intelligence\n{self.state.geo_intel}\n\n" \
            f"## 📱 Social Roadmap\n{self.state.social_plan}"

        return "branding_complete"
        
        # 1. STRATEGIST (The Lead Architect)
        if "strategist" in self.active_swarm:
            production_tasks.append(Task(
                description=f"Develop a Master Marketing Strategy for {self.state.biz_name}.",
                agent=self.agents["strategist"],
                expected_output="A high-level executive strategic brief."
            ))

        # 2. CREATIVE (Ad Copy)
        if "creative" in self.active_swarm:
            production_tasks.append(Task(
                description="Engineer a Multichannel Ad Suite (Google, Meta, Veo).",
                agent=self.agents["creative"],
                expected_output="Markdown table with platform-specific ad copy."
            ))

        # 3. SEO (The Blogger)
        if "seo" in self.active_swarm:
            production_tasks.append(Task(
                description="Compose a technical SEO-optimized authority article.", 
                agent=self.agents["seo_blogger"], 
                expected_output="A 1000-word technical SEO article."
            ))

        # 4. SOCIAL (Viral Specialist)
        if "social" in self.active_swarm:
            production_tasks.append(Task(
                description="Create a 30-day viral social media content calendar.", 
                agent=self.agents["social_agent"], 
                expected_output="Calendar with hooks and captions."
            ))

        # 5. GEO (Local Search)
        if "geo" in self.active_swarm:
            production_tasks.append(Task(
                description="Develop a local GEO-fencing and GMB optimization plan.", 
                agent=self.agents["geo_specialist"], 
                expected_output="Local SEO and GEO intelligence report."
            ))

       # --- EXECUTION & ROBUST MAPPING ---
        if production_tasks:
            crew = Crew(
                agents=[t.agent for t in production_tasks],
                tasks=production_tasks,
                process=Process.sequential
            )
            crew.kickoff()
            
            for task in production_tasks:
                # Ensure we are capturing the raw string output correctly
                out = str(task.output.raw)
                desc = task.description.lower()
                
                # Broad Keyword Matching: If ANY of these words exist, save to the state
                if any(word in desc for word in ["strategy", "master", "brief"]): 
                    self.state.strategist_brief = out
                elif any(word in desc for word in ["ad suite", "multichannel", "creative", "copy"]): 
                    self.state.ad_drafts = out
                elif any(word in desc for word in ["seo", "article", "blog", "content"]): 
                    self.state.seo_article = out
                elif any(word in desc for word in ["viral", "social", "calendar", "post"]): 
                    self.state.social_plan = out
                elif any(word in desc for word in ["geo", "local", "gmb", "map"]): 
                    self.state.geo_intel = out
            
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

# 4. SYSTEMIC MAPPING (Final Alignment for Go-Live)
    # This dictionary bridges your Backend State to your Frontend Tabs
    master_data = {
        "analyst": getattr(flow.state, 'market_data', "No analyst data found."),
        "vision": getattr(flow.state, 'vision_intel', "No visual intel found."), 
        "creative": getattr(flow.state, 'ad_drafts', "No creative drafts found."),
        "strategist": getattr(flow.state, 'strategist_brief', "Final brief pending."),
        "social": getattr(flow.state, 'social_plan', "Social roadmap not generated."),
        "geo": getattr(flow.state, 'geo_intel', "GEO data not selected."),
        "seo": getattr(flow.state, 'seo_article', "SEO Content not selected."),
        "audit": getattr(flow.state, 'website_audit', "Website audit pending."),
        "full_report": getattr(flow.state, 'full_report', "Full report generation failed.")
    }

    # 5. FILTERED RETURN
    # We retrieve the list of buttons the user actually clicked
    active_list = inputs.get('active_swarm', [])
    
    # We return the data for active agents + the full summary for the PDF
    return {k: v for k, v in master_data.items() if k in active_list or k == "full_report"}
