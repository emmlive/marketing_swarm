import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file to prevent credential caching issues
load_dotenv(override=True)

# --- 1. SHARED STATE (THE BLACKBOARD ARCHITECTURE) ---
class SwarmState(BaseModel):
    """The shared state object following the 'Blackboard' architecture."""
    market_data: str = ""
    ad_drafts: str = ""
    strategic_roadmap: str = ""
    sem_strategy: str = ""
    seo_content: str = ""
    geo_plan: str = ""
    analytics_plan: str = ""
    repurposed_content: str = ""
    production_schedule: str = "" 
    final_validation: str = ""
    website_audit: str = ""
    vision_findings: str = ""

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (13 Specialized Roles) ---
def get_swarm_agents(inputs):
    # Context-aware variables for agents
    biz = inputs.get('biz_name', 'The Business')
    usp = inputs.get('usp', 'High-quality service')
    ind = inputs.get('industry', 'General Industry')

    return {
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Identify real-time competitor gaps in {inputs['city']} for {biz}.",
            backstory=f"Data scientist who finds exactly where local {ind} competitors are failing.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal=f"Transform {biz}'s USP ({usp}) into Navy/White branded ad assets.",
            backstory="Psychological builder. You use the Navy (#000080) and White palette to convey elite trust.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager",
            goal=f"Identify conversion 'leaks' on {inputs.get('url')}.",
            backstory="UX specialist. You find why visitors are not turning into leads for this specific brand.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "advice_director": Agent(
            role="Marketing Advice Director",
            goal=f"Provide a CMO-level ROI strategy for {biz} in {inputs['city']}.",
            backstory=f"Veteran strategist. You ensure {biz} doesn't waste money on generic marketing.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a bespoke project management roadmap for the client.",
            backstory="Expert PM. You translate complex marketing tasks into a simple 30-day to-do list.",
            llm=gemini_llm, verbose=True
        ),
        "sem_specialist": Agent(
            role="SEM Specialist",
            goal="Build high-intent Google Ads keyword strategies.",
            backstory="PPC expert. You focus on 'Bottom of Funnel' keywords that drive immediate revenue.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist",
            goal="Optimize brand citations for Generative AI Search Engines.",
            backstory="AI Search expert. You ensure Perplexity, Gemini, and ChatGPT cite this brand.",
            llm=gemini_llm, verbose=True
        ),
        "analytics_specialist": Agent(
            role="Web Analytics Specialist",
            goal="Define a precise conversion tracking plan (GTM/GA4).",
            backstory="Attribution expert. You ensure every ad dollar is tracked to a specific conversion.",
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Blog Creator",
            goal="Generate E-E-A-T compliant local authority content.",
            backstory="Content strategist who balances local ranking factors with reader conversion.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposer",
            goal="Localize 1 asset into platform-specific social hooks for GBP/Reddit/Quora.",
            backstory="Neighborly communicator. You make the brand look like a local community pillar.",
            llm=gemini_llm, verbose=True
        ),
        "vision_inspector": Agent(
            role=f"Autonomous {ind} Vision Inspector",
            goal=f"Analyze industry-specific visual evidence and safety protocols.",
            backstory=f"Risk management expert for {ind}. You identify hazards or safety receipts visually.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Audit the entire swarm output to ensure maximum user value.",
            backstory="The final gatekeeper. You reject any output that feels generic or off-brand.",
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
        """Phase 1: Discovery & Technical Audit."""
        active_tasks = []
        active_agents = [self.agents["analyst"]]
        active_tasks.append(Task(
            description=f"Analyze the market for {self.inputs['biz_name']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Competitor Map and Market Truth Report."
        ))

        if self.toggles.get('audit') and self.inputs.get('url'):
            active_agents.append(self.agents["web_auditor"])
            active_tasks.append(Task(
                description=f"Audit {self.inputs['url']} for conversion leaks.",
                agent=self.agents["web_auditor"],
                expected_output="Technical Site Audit findings."
            ))

        result = Crew(agents=active_agents, tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Phase 2: Independent Specialist Production."""
        active_tasks = []
        active_agents = [self.agents["creative"]]
        
        # Mandatory Creative
        active_tasks.append(Task(
            description=f"Create Navy/White ad copy based on USP: {self.inputs['usp']}.",
            agent=self.agents["creative"],
            expected_output="3 Ad variants and visual prompts."
        ))

        # Dynamic Modular Specialists
        if self.toggles.get('advice'):
            active_agents.append(self.agents["advice_director"])
            active_tasks.append(Task(description="ROI Strategy Advice.", agent=self.agents["advice_director"], expected_output="CMO Strategic Plan."))
            
        if self.toggles.get('sem'):
            active_agents.append(self.agents["sem_specialist"])
            active_tasks.append(Task(description="Keyword Bidding Plan.", agent=self.agents["sem_specialist"], expected_output="SEM Strategy."))

        if self.toggles.get('geo'):
            active_agents.append(self.agents["geo_specialist"])
            active_tasks.append(Task(description="AI Search Citations Map.", agent=self.agents["geo_specialist"], expected_output="GEO Report."))

        if self.toggles.get('seo'):
            active_agents.append(self.agents["seo_creator"])
            active_tasks.append(Task(description="Local Authority Content.", agent=self.agents["seo_creator"], expected_output="Optimized SEO Blog."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics_and_audit(self):
        """Phase 3: Logistics and Final Manager Audit."""
        # Task 1: Schedule
        time_task = Task(
            description="Build a 30-day project roadmap for the user.",
            agent=self.agents["time_director"],
            expected_output="Gantt-style Production Schedule."
        )
        # Task 2: Final Gatekeeping
        val_task = Task(
            description="Review all outputs for ROI and brand alignment.",
            agent=self.agents["strategist"],
            expected_output="Final Manager Approval and Summary."
        )

        result = Crew(agents=[self.agents["time_director"], self.agents["strategist"]], tasks=[time_task, val_task]).kickoff()
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    return f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Market Intelligence & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Creative Strategy & Specialist Production
{flow.state.ad_drafts}

## 🗓️ Phase 3: Managerial Review & User Schedule
{flow.state.production_schedule}

---
*Generated by BreatheEasy AI | Strategist Verified*
    """
