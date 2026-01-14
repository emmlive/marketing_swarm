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
    market_data: str = "Analysis pending..."
    competitor_ads: str = "Ad tracking pending..."
    vision_intel: str = "Visual audit pending..."  # FIXED: Ensures UI can always access this attribute
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
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3 
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
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps and price arbitrage opportunities for {biz} in {city}.",
            backstory="Expert market scientist specializing in competitor fatigue and local vulnerabilities.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "vision_agent": Agent(
            role="Visual Identity Auditor",
            goal=f"Analyze the visual psychological impact of competitor assets and {biz}'s current presence.",
            backstory="Expert in design psychology and conversion-focused visual hierarchy.",
            llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Executive Creative Director",
            goal="Engineer psychological ad hooks and high-end cinematic video concepts.",
            backstory="Converts emotional triggers into precise cinematic scene descriptions for Veo video generation.",
            llm=gemini_llm, verbose=True
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect",
            goal="Compose high-authority technical articles that secure AI search engine trust.",
            backstory=f"Establishes {biz} as the definitive local leader through E-E-A-T technical authority content.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose technical conversion leaks on {url}.",
            backstory="Identifies funnel leaks and provides developer-ready action items.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Architect",
            goal="Repurpose strategy into a viral Omni-channel broadcast plan.",
            backstory="Expert in viral hooks and deployment schedules.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist",
            goal=f"Optimize citation velocity and Map visibility for {biz} in {city}.",
            backstory="Expert in Local Ranking Factors and AI Search (SGE) dominance.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer",
            goal="Synthesize all agent intelligence into a 30-day CEO roadmap.",
            backstory="The ultimate decision maker validating every agent's work for ROI alignment.",
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
        """Step 1: Stakeholder Discovery, Ad Tracking & Visual Audit"""
        analyst_task = Task(
            description=f"Identify the 'Market Entry Gap' and analyze live ad hooks in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Markdown Report with Competitor Fatigue analysis and Psychological Ad Hook deconstruction."
        )
        
        vision_task = Task(
            description=f"Perform a visual audit of competitors in the {self.inputs['industry']} space for {self.inputs['city']}.",
            agent=self.agents["vision_agent"],
            expected_output="Detailed breakdown of rival visual psychology and design gaps."
        )

        active_tasks = [analyst_task, vision_task]
        
        auditor_task = None
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Executive Technical Audit with developer action items."
            )
            active_tasks.append(auditor_task)
            
        Crew(agents=list(self.agents.values()), tasks=active_tasks, process=Process.sequential).kickoff()
        
        self.state.market_data = str(analyst_task.output.raw)
        self.state.competitor_ads = "Analyzed within Market Data"
        self.state.vision_intel = str(vision_task.output.raw) 
        
        if auditor_task:
            self.state.website_audit = str(auditor_task.output.raw)
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Content Engineering & Production"""
        creative_task = Task(
            description="Develop 3 'Pain-Point' ad frameworks and a cinematic 'Video Prompt:' for Veo.",
            agent=self.agents["creative"],
            expected_output="Executive Creative Brief with cinematic video directions."
        )
        
        production_tasks = [creative_task]
        
        if self.toggles.get('seo'):
            production_tasks.append(Task(
                description="Compose a technical SEO authority article.",
                agent=self.agents["seo_blogger"],
                expected_output="Technical article content."
            ))

        if self.toggles.get('social'):
            production_tasks.append(Task(
                description="Create a 30-day viral distribution schedule.",
                agent=self.agents["social_agent"],
                expected_output="Viral Hooks and Schedule."
            ))

        if self.toggles.get('geo'):
            production_tasks.append(Task(
                description="Develop a local GEO dominance plan.",
                agent=self.agents["geo_specialist"],
                expected_output="Technical GEO Intelligence Report."
            ))

        Crew(agents=list(self.agents.values()), tasks=production_tasks, process=Process.sequential).kickoff()
        
        self.state.ad_drafts = str(creative_task.output.raw)
        
        for task in production_tasks:
            out = str(task.output.raw)
            if "SEO" in task.description: self.state.seo_article = out
            if "viral" in task.description: self.state.social_plan = out
            if "GEO" in task.description: self.state.geo_intel = out
            
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 3: CEO Level Synthesis & ROI Roadmap"""
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
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    formatted_string_report = f"""
# 🚀 {inputs['biz_name']} | EXECUTIVE INTELLIGENCE SUMMARY

## 🔍 PHASE 1: MARKET DISCOVERY & AUDIT
### Strategic Market Analysis
{flow.state.market_data}

### 👁️ Visual Intelligence & Rival Asset Audit
{flow.state.vision_intel}

### Technical Website Audit
{flow.state.website_audit}

## 📝 PHASE 2: CONTENT ENGINEERING
### Branded Creative Concepts
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

    return {
        "analyst": flow.state.market_data,
        "ads": flow.state.competitor_ads,
        "vision": flow.state.vision_intel, 
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article,
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report 
    }
