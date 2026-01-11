import os
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force fresh read
load_dotenv(override=True)

# --- 1. SHARED STATE ---
class SwarmState(BaseModel):
    # These fields ensure data is captured for every Command Seat
    market_data: str = "Analysis pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Distribution pending..."
    geo_intel: str = "GEO mapping pending..."
    production_schedule: str = "Roadmap pending..."
    strategist_brief: str = "Final brief pending..."

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
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
            role="Senior Conversion Psychologist (The Researcher)",
            goal=f"Extract competitor gaps in {city} and provide 2 structured JSON Buyer Personas.",
            backstory="You are a data-driven truth-seeker. You identify pain points using neuromarketing.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist (The Builder)",
            goal="Transform Analyst data into Navy/White branded assets and Nano Banana image prompts.",
            backstory="You build multimodal copy and visual prompts based on data, never generic clichés.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The Auditor)",
            goal=f"Diagnose conversion leaks on {url}.",
            backstory="UX specialist focused on friction reduction and conversion psychology.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Content Architect",
            goal="Repurpose strategy into short-form viral hooks for Meta, Google, and LinkedIn.",
            backstory="Expert in distribution velocity and social media copywriting.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Generative Engine Optimization)",
            goal=f"Optimize {biz} for AI Search (ChatGPT/Gemini) citation velocity in {city}.",
            backstory="Focused on local authority and AI-native search positioning.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Orchestrate agents and validate outputs for 100% ROI alignment.",
            backstory="The Commander. You ensure all phases are linked and high-fidelity.",
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
        active_tasks = []
        active_tasks.append(Task(
            description=f"Identify competitor gaps in {self.inputs['city']} and provide 2 JSON Buyer Personas.",
            agent=self.agents["analyst"],
            expected_output="JSON Market Truth Report."
        ))
        if self.toggles.get('audit'):
            active_tasks.append(Task(
                description=f"Audit {self.inputs['url']} for UX leaks.",
                agent=self.agents["web_auditor"],
                expected_output="Technical Audit findings."
            ))
        
        result = Crew(agents=[self.agents["analyst"], self.agents["web_auditor"]], tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        self.state.website_audit = str(result)
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        active_tasks = []
        active_tasks.append(Task(
            description="Build ad copy and Nano Banana image prompts using the Analyst's JSON personas.",
            agent=self.agents["creative"],
            expected_output="Branded Assets."
        ))
        if self.toggles.get('social'):
            active_tasks.append(Task(description="Social hooks.", agent=self.agents["social_agent"], expected_output="Social Plan."))
        if self.toggles.get('geo'):
            active_tasks.append(Task(description="Local AI search plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report."))

        result = Crew(agents=[self.agents["creative"], self.agents["social_agent"], self.agents["geo_specialist"]], tasks=active_tasks).kickoff()
        self.state.ad_drafts = str(result)
        self.state.social_plan = str(result)
        self.state.geo_intel = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        val_task = Task(description="Build 30-day roadmap and final brief.", agent=self.agents["strategist"], expected_output="Master Brief.")
        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER (UNIFIED RETURN) ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # PROACTIVE SOLUTION: Returning a dictionary that includes your exact string format
    # This allows app.py to display the summary OR individual agent seats.
    
    formatted_string_report = f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Execution, SEO IG & Budget Forecast
{flow.state.ad_drafts}

## 🗓️ Phase 3: Managerial Review & Roadmap
{flow.state.production_schedule}

---
*Generated by TechInAdvance AI | Strategist Verified*
"""

    return {
        "analyst": flow.state.market_data,
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report  # Your requested missing part
    }
