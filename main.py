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

# --- 3. AGENT DEFINITIONS (Refined for Psychology & SaaS ROI) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    usp = inputs.get('usp', 'High-quality service')
    ind = inputs.get('industry', 'General Industry')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Conversion Psychologist & Market Analyst",
            goal=f"Analyze competitors in {inputs['city']} and {url} through the lens of Consumer Behavior.",
            backstory=(
                f"You are an expert in Neuromarketing and Cialdini's 6 Principles of Persuasion. "
                f"Your job is to identify real-time competitor gaps in {inputs['city']} while diagnosing "
                f"Conversion Leaks for {biz}. You look for Trust Deficits, Cognitive Friction, and "
                f"Value Proposition gaps. You provide the 'Psychological Truth' of the market."
            ),
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal=f"Transform the Analyst's psychological findings and {biz}'s USP ({usp}) into Navy/White branded ad assets.",
            backstory="Psychological builder. You use the Navy (#000080) and White palette to convey elite trust and trigger emotional buying responses.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager",
            goal=f"Identify conversion leaks and UX friction on {url}.",
            backstory="UX specialist. You apply Fitts's Law and Hick's Law to find exactly why visitors are not turning into leads for this specific brand.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "advice_director": Agent(
            role="Marketing Advice Director",
            goal=f"Provide a high-level strategic ROI roadmap for {biz} in {inputs['city']}.",
            backstory="Veteran CMO who ensures the Swarm's tactical output aligns with long-term business growth and ROI.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a bespoke project management roadmap for the client.",
            backstory="Expert PM. You translate complex marketing tasks into a simple 30-day Gantt-style production schedule.",
            llm=gemini_llm, verbose=True
        ),
        "sem_specialist": Agent(
            role="SEM Specialist",
            goal="Build high-intent Google Ads keyword strategies.",
            backstory="PPC expert focused on Quality Score and 'Bottom of Funnel' intent.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist",
            goal="Optimize brand citations for Generative AI Search Engines.",
            backstory="AI Search expert focused on citation authority in Perplexity and Gemini.",
            llm=gemini_llm, verbose=True
        ),
        "analytics_specialist": Agent(
            role="Web Analytics Specialist",
            goal="Define the tracking plan (GTM/GA4) for the campaign.",
            backstory="Data scientist focused on conversion tracking and precise attribution.",
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Blog Creator",
            goal="Generate keyword-optimized authority articles for local ranking.",
            backstory="Content strategist who balances E-E-A-T requirements with high readability.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposer",
            goal="Localize core assets into social hooks for GBP, Facebook, Quora, and Reddit.",
            backstory="Neighborly communicator. You ensure the brand feels like a local pillar in the community.",
            llm=gemini_llm, verbose=True
        ),
        "vision_inspector": Agent(
            role=f"Autonomous {ind} Vision Inspector",
            goal=f"Analyze industry-specific evidence and safety protocols for {ind}.",
            backstory=f"Risk management expert. You look for 'receipts' of safety and quality that build elite trust.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Audit the entire swarm output to ensure maximum user value and ROI.",
            backstory="Quality controller. You ensure all agent outputs are non-generic and align with the Navy/White brand guidelines.",
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
        
        # Mandatory Conversion Psychology Research
        active_tasks.append(Task(
            description=f"Analyze the market psychology for {self.inputs['biz_name']} in {self.inputs['city']}. Find 3 competitors and diagnose their persuasion gaps.",
            agent=self.agents["analyst"],
            expected_output="Conversion Psychology Map and Competitor Audit."
        ))

        # Optional Deep Website Audit
        if self.toggles.get('audit') and self.inputs.get('url'):
            active_agents.append(self.agents["web_auditor"])
            active_tasks.append(Task(
                description=f"Audit {self.inputs['url']} for cognitive friction and UX conversion leaks.",
                agent=self.agents["web_auditor"],
                expected_output="Technical UX and Conversion Audit Findings."
            ))

        result = Crew(agents=active_agents, tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Phase 2: Independent Specialist Production."""
        active_tasks = []
        active_agents = [self.agents["creative"]]
        
        # Mandatory Creative (Injecting Psychology into Copy)
        active_tasks.append(Task(
            description=f"Create 3 ad variants using {self.inputs['usp']} and the Analyst's psychology findings. Focus on Elite Trust (Navy/White).",
            agent=self.agents["creative"],
            expected_output="3 Ad variants (Punchy, Story, Urgency) and visual prompts."
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
            description="Build a 30-day Gantt-style roadmap for the implementation of these assets.",
            agent=self.agents["time_director"],
            expected_output="30-Day Production Schedule."
        )
        # Task 2: Final Gatekeeping
        val_task = Task(
            description="Review all outputs. Ensure they are error-free, persuasive, and follow the Navy/White elite brand standard.",
            agent=self.agents["strategist"],
            expected_output="Final Manager Approval Summary."
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
