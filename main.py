import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file
load_dotenv(override=True)

# --- 1. SHARED STATE (THE BLACKBOARD) ---
class SwarmState(BaseModel):
    """The shared state object following the 'Blackboard' architecture."""
    market_data: str = ""
    ad_drafts: str = ""
    repurposed_content: str = ""
    strategic_roadmap: str = ""
    analytics_plan: str = ""
    sem_strategy: str = ""
    geo_plan: str = ""
    production_schedule: str = "" # New field for Time Management

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (Legacy, New, & Time Management) ---
def get_swarm_agents(inputs):
    return {
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Research the {inputs['service']} market in {inputs['city']} to provide the 'Truth'.",
            backstory="Data-driven researcher. You identify top 3 competitors and map persona hooks.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal="Transform research into 3 high-converting ad variants and visual prompts.",
            backstory="Builder. You create Punchy, Story, and Urgency variants using Navy/White branding.",
            llm=gemini_llm, verbose=True
        ),
        "advice_director": Agent(
            role="Marketing Advice Director",
            goal="Provide a high-level strategic roadmap and ROI advice.",
            backstory="Veteran CMO focused on big-picture business growth.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a realistic production timeline and project schedule for all campaign assets.",
            backstory="Expert Project Manager. You calculate 'Level of Effort' (LOE) and ensure zero bottlenecks.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposing Agent",
            goal="Localize content for GBP, Facebook, Quora, and Reddit.",
            backstory="Neighborly tone. Includes AI-Verified Discount Code: BREATHE2026.",
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
            goal="Optimize brand presence for AI search engines like Perplexity and ChatGPT.",
            backstory="Future-SEO expert focused on Citation Authority in Generative AI.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Marketing Strategist",
            goal="Orchestrate and validate the 'Relay Race' phases.",
            backstory="Quality controller. You ensure the sequence follows the Day 1 notes.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (FLOWS) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    """Orchestrates Phase 1 (Research), Phase 2 (Creative/Strategy), Phase 3 (Time/Logistics)."""
    
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_research(self):
        """Phase 1: Research."""
        task = Task(
            description=f"Identify 3 competitors and persona hooks for {self.inputs['service']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Competitor Audit and Persona Mapping summary."
        )
        result = Crew(agents=[self.agents["analyst"]], tasks=[research_task]).kickoff()
        self.state.market_data = result.raw
        return "research_complete"

    @listen("phase_1_research")
    def phase_2_creative_and_strategy(self):
        """Phase 2: Building the assets and specific strategies."""
        active_agents = [self.agents["creative"]]
        active_tasks = [Task(description="Create 3 ad variants and visuals.", agent=self.agents["creative"], expected_output="Ad copy and prompts.")]
        
        # Modular logic for new agents based on toggles
        if self.toggles.get('advice'):
            active_agents.append(self.agents["advice_director"])
            active_tasks.append(Task(description="Provide strategic roadmap.", agent=self.agents["advice_director"], expected_output="CMO Roadmap."))
            
        if self.toggles.get('sem'):
            active_agents.append(self.agents["sem_specialist"])
            active_tasks.append(Task(description="Create PPC/SEM plan.", agent=self.agents["sem_specialist"], expected_output="SEM Strategy."))

        result = Crew(agents=active_agents, tasks=active_tasks).kickoff()
        # In a real run, you'd parse individual outputs to state. This is simplified for flow:
        self.state.ad_drafts = result.raw
        return "creative_complete"

    @listen("creative_complete")
    def phase_3_logistics_and_time(self):
        """Phase 3: The Time Management Director creates the final schedule."""
        print("--- [PHASE 3] Time Management & Production Scheduling ---")
        task = Task(
            description=f"Based on the creative work and strategies generated, create a detailed production timeline. "
                        f"When should ads go live? How long to set up SEM? Include a 7-day social schedule.",
            agent=self.agents["time_director"],
            expected_output="Production Schedule and Project Timeline (Gantt-style text)."
        )
        result = Crew(agents=[self.agents["time_director"]], tasks=[task]).kickoff()
        self.state.production_schedule = result.raw
        return "logistics_complete"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    full_report = f"""
# 🌬️ BreatheEasy AI Swarm Report: {inputs['city']}

## 📊 Phase 1: Market Research
{flow.state.market_data}

## 📝 Phase 2: Creative & Strategy
{flow.state.ad_drafts}

## 🗓️ Phase 3: Time Management & Production Schedule
{flow.state.production_schedule}
    """
    return full_report
