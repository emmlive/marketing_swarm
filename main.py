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
# Each field corresponds to a specific Command Seat in app.py to prevent data bleed
class SwarmState(BaseModel):
    market_data: str = "Analysis pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
    geo_intel: str = "GEO mapping pending..."
    production_schedule: str = "Roadmap pending..."
    strategist_brief: str = "Final brief pending..."

# --- 2. ENGINE INITIALIZATION ---
# Temperature 0.4 ensures grounding in tool-found facts to strictly minimize hallucinations
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4 
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (GROUNDED & SKEPTICAL) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Market Analyst (The Fact-Finder)",
            goal=f"Extract real-time competitor gaps in {city} and provide Buyer Personas in STRICT JSON format.",
            backstory="You are a literalist data scientist. Hallucination is a firing offense. If data is not found via tools, state 'Data not found' instead of guessing.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True, allow_delegation=False
        ),
        "creative": Agent(
            role="Creative Director (The Builder)",
            goal="Transform Analyst data into Navy/White branded assets and Nano Banana image prompts.",
            backstory="You are a multimodal architect. Claims must be anchored 100% to the Analyst's found facts. You do not invent competitor myths.",
            llm=gemini_llm, verbose=True, allow_delegation=False
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The UX Skeptic)",
            goal=f"Diagnose conversion leaks on {url} using technical UX principles.",
            backstory="You are a conversion psychologist. Use the Scrape tool to find 'Friction Points'. You do not guess UI issues.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Specialist",
            goal="Repurpose strategy into viral hooks for Meta, Google, and LinkedIn.",
            backstory="Expert in algorithmic engagement. Turn data-backed strategy into hooks without exaggerating claims.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (AI Search Optimization)",
            goal=f"Optimize {biz} for citation velocity in AI search engines for {city}.",
            backstory="AI Search expert. Identify local keyword clusters and citation paths to make the brand an LLM-cited authority.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Swarm Commander)",
            goal="Orchestrate agents and validate outputs for ROI alignment.",
            backstory="The final gatekeeper. You reject any creative output that isn't backed by research facts from the tools.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (STRICT ISOLATION LOGIC) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_discovery(self):
        """Step 1: Grounded Research and Technical Auditing"""
        analyst_task = Task(
            description=f"Identify top 3 competitors for {self.inputs['biz_name']} in {self.inputs['city']}. Output JSON Schema: {{'competitors': [], 'personas': [{{'name': '', 'pain_points': [], 'trigger': '', 'mood': ''}}]}}.",
            agent=self.agents["analyst"],
            expected_output="JSON Market Truth Report based EXCLUSIVELY on tool results."
        )

        tasks = [analyst_task]
        active_agents = [self.agents["analyst"]]

        auditor_task = None
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Technical UX Audit findings."
            )
            tasks.append(auditor_task)
            active_agents.append(self.agents["web_auditor"])
            
        # Sequential processing ensures tool stability and prevent tool overlap/desync
        crew = Crew(agents=active_agents, tasks=tasks, process=Process.sequential)
        crew.kickoff()
        
        # ISOLATED CAPTURE: Explicitly mapping raw output to separate state variables
        self.state.market_data = analyst_task.output.raw if analyst_task.output else "Researcher data missing."
        if auditor_task:
            self.state.website_audit = auditor_task.output.raw if auditor_task.output else "Audit results missing."
        else:
            self.state.website_audit = "Web Auditor not requested or URL missing."
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2 & 3: Fact-Anchored Creative & Specialist Mapping"""
        creative_task = Task(
            description="Using the Analyst's JSON, build 3 ad variants and 'Nano Banana' prompts. Ground claims in research.",
            agent=self.agents["creative"],
            expected_output="Grounded Branded Assets and Image Prompts."
        )
        tasks = [creative_task]; agents = [self.agents["creative"]]

        social_task = None
        if self.toggles.get('social'):
            social_task = Task(description="Platform-specific viral hooks.", agent=self.agents["social_agent"], expected_output="Social Distribution Plan.")
            tasks.append(social_task); agents.append(self.agents["social_agent"])

        geo_task = None
        if self.toggles.get('geo'):
            geo_task = Task(description="AI Search citation velocity plan.", agent=self.agents["geo_specialist"], expected_output="GEO Visibility Report.")
            tasks.append(geo_task); agents.append(self.agents["geo_specialist"])

        crew = Crew(agents=agents, tasks=tasks, process=Process.sequential)
        crew.kickoff()
        
        # Map outputs back to isolated SwarmState fields
        self.state.ad_drafts = creative_task.output.raw if creative_task.output else "Creative build failed."
        if social_task:
            self.state.social_plan = social_task.output.raw if social_task.output else "Social Specialist failed."
        if geo_task:
            self.state.geo_intel = geo_task.output.raw if geo_task.output else "GEO Specialist failed."
        
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 4: Strategic Brief & Final Synthesis Verification"""
        val_task = Task(
            description="Synthesize all grounded outputs into a 30-day brief. Reject hallucinated data.",
            agent=self.agents["strategist"],
            expected_output="Verified Master Campaign Brief and Roadmap."
        )

        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER (ISOLATED RETURN) ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # Generate the formatted summary for unified report views and exports
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
