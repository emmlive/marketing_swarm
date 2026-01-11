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

# --- 1. SHARED STATE (ISOLATED FIELDS) ---
class SwarmState(BaseModel):
    # Isolated fields to prevent data overlap in Command Seats
    market_data: str = "Analysis pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
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
            role="Senior Market Analyst (The Researcher)",
            goal=f"Extract competitor gaps in {city} and provide Buyer Personas in STRICT JSON format.",
            backstory="Data scientist focused on neuromarketing. You provide the foundation of truth.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Creative Director (The Builder)",
            goal="Transform Analyst data into high-conversion assets and Nano Banana image prompts.",
            backstory="Multimodal builder. You use the Researcher's JSON to ensure copy is data-backed.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The Auditor)",
            goal=f"Diagnose conversion leaks on {url}.",
            backstory="UX specialist. You find the 'friction' points in the URL provided.",
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
            backstory="AI Search expert focused on making the brand the #1 cited authority in local AI results.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Orchestrate agents and validate outputs for ROI alignment.",
            backstory="The Swarm Commander. You ensure the final Master Brief is elite.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (ISOLATED EXECUTION) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_discovery(self):
        """Phase 1: Research and Technical Auditing"""
        # ANALYST TASK
        analyst_task = Task(
            description=(
                f"Identify top 3 competitors for {self.inputs['biz_name']} in {self.inputs['city']}. "
                "Output findings in this JSON Schema: "
                "{'competitors': [], 'personas': [{'pain_points': [], 'buying_trigger': '', 'mood': ''}]}"
            ),
            agent=self.agents["analyst"],
            expected_output="JSON Market Truth Report."
        )

        # AUDITOR TASK (Conditional)
        if self.toggles.get('audit'):
            auditor_task = Task(
                description=f"Audit {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Technical UX Audit findings."
            )
            
            # Run parallel discovery
            crew = Crew(agents=[self.agents["analyst"], self.agents["web_auditor"]], 
                        tasks=[analyst_task, auditor_task])
            result = crew.kickoff()
            
            # Isolated state assignment
            self.state.market_data = str(analyst_task.output.raw)
            self.state.website_audit = str(auditor_task.output.raw)
        else:
            result = Crew(agents=[self.agents["analyst"]], tasks=[analyst_task]).kickoff()
            self.state.market_data = str(result)
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Phase 2: Creative Production and Specialist Plans"""
        # CREATIVE TASK
        creative_task = Task(
            description="Create 3 Navy/White ad variants and 'Nano Banana' prompts using the Researcher's JSON.",
            agent=self.agents["creative"],
            expected_output="Branded Creative Assets."
        )
        tasks = [creative_task]
        agents = [self.agents["creative"]]

        # SOCIAL TASK
        if self.toggles.get('social'):
            social_task = Task(description="Social hooks and distribution.", agent=self.agents["social_agent"], expected_output="Social Plan.")
            tasks.append(social_task)
            agents.append(self.agents["social_agent"])

        # GEO TASK
        if self.toggles.get('geo'):
            geo_task = Task(description="AI Search velocity plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report.")
            tasks.append(geo_task)
            agents.append(self.agents["geo_specialist"])

        crew = Crew(agents=agents, tasks=tasks, process=Process.sequential)
        crew.kickoff()
        
        # Isolated state assignment to prevent mirror overlap
        self.state.ad_drafts = str(creative_task.output.raw)
        if self.toggles.get('social'): self.state.social_plan = str(social_task.output.raw)
        if self.toggles.get('geo'): self.state.geo_intel = str(geo_task.output.raw)
        
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Phase 3: Final Brief and Roadmap"""
        val_task = Task(
            description="Audit all agent outputs. Synthesize into a final 30-day roadmap and Master Brief.",
            agent=self.agents["strategist"],
            expected_output="Master Campaign Brief."
        )

        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER (ISOLATED DICTIONARY) ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    formatted_string_report = f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Execution, Creative & Social
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
