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

# --- 1. SHARED STATE ---
class SwarmState(BaseModel):
    # These fields ensure data is captured for every Command Seat in app.py
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

# --- 3. AGENT DEFINITIONS (Orchestrated for $1B SaaS standard) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Market Analyst (The Researcher)",
            goal=f"Extract competitor gaps in {city} and provide Buyer Personas in STRICT JSON format.",
            backstory="Data scientist focused on neuromarketing and competitor auditing. You output structured JSON.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Creative Director (The Builder)",
            goal="Transform Analyst data into high-conversion assets and Nano Banana image prompts.",
            backstory="Multimodal builder. You use Navy/White branding and psychological hooks to create visual and text assets.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The Auditor)",
            goal=f"Diagnose conversion leaks on {url}.",
            backstory="UX/UI specialist. You find the 'friction' points in the provided URL.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Specialist",
            goal="Repurpose strategy into hooks for Meta, Google, and LinkedIn.",
            backstory="Expert in social algorithm triggers and distribution velocity.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Generative Engine Optimization)",
            goal=f"Optimize {biz} for AI Search (ChatGPT/Gemini) citation velocity in {city}.",
            backstory="AI Search expert focused on making the brand the #1 cited authority in local searches.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Orchestrate agents and validate outputs for ROI alignment.",
            backstory="The Swarm Commander. You ensure the final output is elite and client-ready.",
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
        """Phase 1: Research and Technical Auditing"""
        active_tasks = []
        
        # MANDATORY JSON SCHEMA TASK
        active_tasks.append(Task(
            description=(
                f"Identify top 3 competitors for {self.inputs['biz_name']} in {self.inputs['city']}. "
                "Output findings in this JSON Schema: "
                "{'competitors': [], 'personas': [{'pain_points': [], 'buying_trigger': '', 'mood': ''}]}"
            ),
            agent=self.agents["analyst"],
            expected_output="Valid JSON string containing research and personas."
        ))

        if self.toggles.get('audit'):
            active_tasks.append(Task(
                description=f"Audit {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="UX Audit report."
            ))

        result = Crew(agents=[self.agents["analyst"], self.agents["web_auditor"]], tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        self.state.website_audit = str(result)
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Phase 2: Creative Production and Specialist Plans"""
        active_tasks = []
        active_agents = [self.agents["creative"]]
        
        # NANO BANANA INTEGRATION
        active_tasks.append(Task(
            description=(
                "Parse the Analyst's JSON. Create 3 Navy/White ad copy variants. "
                "Provide highly detailed image prompts for the 'Nano Banana' model based on the JSON 'mood'."
            ),
            agent=self.agents["creative"],
            expected_output="Multimodal creative assets and specific image prompts."
        ))

        if self.toggles.get('social'):
            active_agents.append(self.agents["social_agent"])
            active_tasks.append(Task(description="Meta/Google/LinkedIn hooks.", agent=self.agents["social_agent"], expected_output="Social Plan."))

        if self.toggles.get('geo'):
            active_agents.append(self.agents["geo_specialist"])
            active_tasks.append(Task(description="AI Search velocity plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = str(result)
        self.state.social_plan = str(result)
        self.state.geo_intel = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Phase 3: Final Brief and Roadmap"""
        val_task = Task(
            description="Audit all agent outputs. Synthesize into a final 30-day roadmap and Master Brief.",
            agent=self.agents["strategist"],
            expected_output="Elite Campaign Roadmap & Master Brief."
        )

        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER (UNIFIED RETURN FOR APP.PY) ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # Reconstruct the requested formatted string for the 'full_report' key
    formatted_string_report = f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Execution, SEO IG & Distribution
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
        "full_report": formatted_string_report
    }
