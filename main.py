import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file to prevent auth caching issues
load_dotenv(override=True)

# --- 1. SHARED STATE (THE BLACKBOARD ARCHITECTURE) ---
class SwarmState(BaseModel):
    """The shared state object that agents read from and write to."""
    market_data: str = ""
    ad_drafts: str = ""
    repurposed_content: str = ""
    strategic_roadmap: str = ""
    analytics_plan: str = ""
    sem_strategy: str = ""
    geo_plan: str = ""
    seo_content: str = ""
    vision_report: str = ""
    production_schedule: str = "" # Updated by Time Management Director

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (All 12 Specialist Roles) ---
def get_swarm_agents(inputs):
    return {
        # Core Foundation Agents
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Research the {inputs['service']} market in {inputs['city']} to provide the 'Truth'.",
            backstory="Data-driven researcher. You identify top 3 competitors and map 2 distinct buyer personas with specific hooks.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal="Transform research into 3 high-converting ad variants and visual prompts.",
            backstory="Award-winning builder. You create Punchy, Story, and Urgency variants using Navy (#000080) and White visual psychology.",
            llm=gemini_llm, verbose=True
        ),
        # New Modular Specialists
        "advice_director": Agent(
            role="Marketing Advice Director",
            goal="Provide a high-level strategic roadmap and ROI advice.",
            backstory="Veteran CMO who looks at the big picture and ensures project ROI.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a realistic production timeline and project schedule for all campaign assets.",
            backstory="Expert Project Manager. You calculate 'Level of Effort' (LOE) and ensure zero bottlenecks.",
            llm=gemini_llm, verbose=True
        ),
        "sem_specialist": Agent(
            role="SEM Specialist",
            goal="Build Google Ads search campaigns and keyword bidding strategies.",
            backstory="PPC expert focused on Quality Score and Local Service Ads.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist",
            goal="Optimize brand presence for AI search engines like Perplexity, ChatGPT, and Gemini.",
            backstory="Future-SEO expert focused on Citation Authority in Generative Search.",
            llm=gemini_llm, verbose=True
        ),
        "analytics_specialist": Agent(
            role="Web Analytics Specialist",
            goal="Define the tracking plan (GTM/GA4) for the campaign.",
            backstory="Data scientist focused on conversion tracking and attribution models.",
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Blog Creator",
            goal="Generate long-form, keyword-optimized articles for local ranking.",
            backstory="Content strategist who balances readability with search engine crawler requirements.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposing Agent",
            goal="Localize content for GBP, Facebook, Quora, and Reddit.",
            backstory="Neighborly tone. Includes AI-Verified Discount Code: BREATHE2026.",
            llm=gemini_llm, verbose=True
        ),
        # Autonomous Vision Agent
        "vision_inspector": Agent(
            role=f"Autonomous {inputs['industry']} Vision Inspector",
            goal=f"Decide diagnostic protocol for {inputs['industry']} and analyze visual evidence.",
            backstory=f"You do not follow a fixed script. You determine what hazards or upsells exist in {inputs['industry']} context.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Marketing Strategist",
            goal="Orchestrate and validate the 'Relay Race' phases.",
            backstory="Quality controller. You ensure the sequence follows the user's Day 1 project notes.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (PHASED ORCHESTRATION) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    """Orchestrates Research -> Creative/Strategy -> Logistics phases."""
    
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_research(self):
        """Phase 1: The Analyst finds the 'Truth'."""
        print(f"--- [PHASE 1] Researching {self.inputs['industry']} in {self.inputs['city']} ---")
        task = Task(
            description=f"Identify 3 competitors and persona hooks for {self.inputs['service']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Detailed Competitor Audit and Persona Mapping."
        )
        result = Crew(agents=[self.agents["analyst"]], tasks=[task]).kickoff()
        self.state.market_data = result.raw
        return "research_complete"

    @listen("phase_1_research")
    def phase_2_execution(self):
        """Phase 2: Modular execution based on user toggles."""
        print("--- [PHASE 2] Executing Modular Specialist Tasks ---")
        active_tasks = []
        active_agents = []

        # Foundation Creative
        active_agents.append(self.agents["creative"])
        active_tasks.append(Task(description="Write 3 ads and visual prompts.", agent=self.agents["creative"], expected_output="Ad variants and image prompts."))

        # Modular Switches (Advice, SEM, GEO, SEO, Analytics)
        if self.toggles.get('advice'):
            active_agents.append(self.agents["advice_director"])
            active_tasks.append(Task(description="Provide ROI Roadmap.", agent=self.agents["advice_director"], expected_output="Strategic advice."))
            
        if self.toggles.get('sem'):
            active_agents.append(self.agents["sem_specialist"])
            active_tasks.append(Task(description="Create PPC Plan.", agent=self.agents["sem_specialist"], expected_output="SEM Strategy."))
            
        if self.toggles.get('seo'):
            active_agents.append(self.agents["seo_creator"])
            active_tasks.append(Task(description="Generate SEO Blog.", agent=self.agents["seo_creator"], expected_output="1,000-word optimized blog."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = result.raw
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics(self):
        """Phase 3: Time Management and Production Scheduling."""
        print("--- [PHASE 3] Time Management & Final Timeline ---")
        task = Task(
            description=f"Analyze all generated content and provide a realistic 30-day production timeline and 7-day social schedule.",
            agent=self.agents["time_director"],
            expected_output="Gantt-style Production Schedule."
        )
        result = Crew(agents=[self.agents["time_director"]], tasks=[task]).kickoff()
        self.state.production_schedule = result.raw
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    """Entry point for app.py to trigger the Omni-Swarm."""
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # Consolidating all Phase data for the Streamlit UI
    full_report = f"""
# 🌬️ BreatheEasy AI Swarm Report: {inputs['city']}

## 📊 Phase 1: Market Truth (Research)
{flow.state.market_data}

## 📝 Phase 2: Creative Assets & Strategy
{flow.state.ad_drafts}

## 🗓️ Phase 3: Time Management & Launch Schedule
{flow.state.production_schedule}

---
*Campaign generated by BreatheEasy Omni-Master v14.0*
    """
    return full_report
