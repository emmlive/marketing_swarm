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
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Conversion Psychologist & Market Analyst",
            goal=f"Identify real-time competitor gaps in {city} for {biz} through the lens of Consumer Behavior.",
            backstory=(
                f"You are an expert in Neuromarketing and Cialdini's Principles of Persuasion. "
                f"Your job is to find 'Conversion Leaks' on {url} and identify Trust Deficits "
                f"among competitors. You identify where the psychological 'friction' is preventing sales."
            ),
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal=f"Transform {biz}'s USP ({usp}) into Navy/White branded ad assets that trigger emotional buying.",
            backstory="Psychological builder. You use Navy (#000080) and White to convey elite trust and authority.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager",
            goal=f"Identify conversion 'leaks' on {url}.",
            backstory="UX specialist focused on 'Cognitive Load' and Fitts's Law. You diagnose why visitors don't convert.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "advice_director": Agent(
            role="Marketing Advice Director",
            goal=f"Provide a CMO-level ROI strategy for {biz} in {city}.",
            backstory="Veteran strategist. You ensure the brand avoids generic marketing and focuses on high-margin growth.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a bespoke project management roadmap for the client.",
            backstory="Expert PM. You translate complex swarm outputs into a simple 30-day production schedule.",
            llm=gemini_llm, verbose=True
        ),
        "sem_specialist": Agent(
            role="SEM Specialist",
            goal="Build high-intent Google Ads keyword strategies.",
            backstory="PPC expert. You focus on 'Bottom of Funnel' triggers that drive immediate phone calls and leads.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Generative Engine Optimization)",
            goal=f"Force ChatGPT, Perplexity, and Gemini to cite {biz} as the #1 local authority.",
            backstory=(
                "AI Search expert. You focus on 'Citation Velocity' and 'Entity Linking.' "
                "You ensure LLMs view the brand as a community pillar by mapping unique data points."
            ),
            llm=gemini_llm, verbose=True
        ),
        "analytics_specialist": Agent(
            role="Web Analytics Specialist",
            goal="Define a precise conversion tracking plan (GTM/GA4).",
            backstory="Data scientist focused on attribution and multi-touch conversion paths.",
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Blog Creator",
            goal="Generate E-E-A-T compliant local authority content.",
            backstory="Content strategist balancing local search intent with reader value.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposer",
            goal="Localize 1 asset into platform-specific social hooks (GBP/Reddit/Quora).",
            backstory="Neighborly communicator. You ensure the brand sounds like a trusted local expert.",
            llm=gemini_llm, verbose=True
        ),
        "vision_inspector": Agent(
            role=f"Autonomous {ind} Vision Inspector",
            goal=f"Analyze industry-specific visual evidence and safety protocols.",
            backstory=f"Risk management expert for {ind}. You identify hazards or 'Receipts of Safety' visually.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Audit the entire swarm output to ensure maximum user value and ROI.",
            backstory="Final gatekeeper. You ensure all output is non-generic, high-fidelity, and on-brand.",
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
            description=f"Analyze the market psychology and competitor gaps for {self.inputs['biz_name']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Conversion Psychology Map and Market Truth Report."
        ))

        if self.toggles.get('audit') and self.inputs.get('url'):
            active_agents.append(self.agents["web_auditor"])
            active_tasks.append(Task(
                description=f"Audit {self.inputs['url']} for conversion leaks and cognitive load issues.",
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
            description=f"Create Navy/White ad variants using {self.inputs['usp']} and findings from the Psychologist.",
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
            active_tasks.append(Task(description="AI Search Citations Map (Perplexity/ChatGPT triggers).", agent=self.agents["geo_specialist"], expected_output="GEO Report."))

        if self.toggles.get('seo'):
            active_agents.append(self.agents["seo_creator"])
            active_tasks.append(Task(description="Local Authority Content.", agent=self.agents["seo_creator"], expected_output="Optimized SEO Blog."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics_and_audit(self):
        """Phase 3: Logistics and Final Manager Audit."""
        

[Image of a project management Gantt chart]

        # Task 1: Schedule
        time_task = Task(
            description="Build a 30-day project roadmap for the user to execute these assets.",
            agent=self.agents["time_director"],
            expected_output="Gantt-style Production Schedule."
        )
        # Task 2: Final Gatekeeping
        val_task = Task(
            description="Review all outputs for ROI, conversion psychology alignment, and brand consistency.",
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
*Generated by TechInAdvance AI | Strategist Verified*
    """
