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
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Research the {inputs['service']} market in {inputs['city']} to provide the 'Truth'.",
            backstory="Data-driven researcher. You identify top 3 competitors and persona hooks.",
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
            backstory="Veteran CMO who looks at the big picture and ensures project ROI.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a realistic production timeline and project schedule.",
            backstory="Expert Project Manager. You calculate 'Level of Effort' (LOE).",
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
            backstory="Future-SEO expert focused on Citation Authority in Generative Search.",
            llm=gemini_llm, verbose=True
        ),
        "analytics_specialist": Agent(
            role="Web Analytics Specialist",
            goal="Define the tracking plan (GTM/GA4) for the campaign.",
            backstory="Data scientist focused on conversion tracking and attribution.",
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Blog Creator",
            goal="Generate long-form, keyword-optimized articles for local ranking.",
            backstory="Content strategist who balances readability with SEO.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposing Agent",
            goal="Localize content for GBP, Facebook, Quora, and Reddit.",
            backstory="Neighborly tone. Includes AI-Verified Discount Code: BREATHE2026.",
            llm=gemini_llm, verbose=True
        ),
        "vision_inspector": Agent(
            role=f"Autonomous {inputs['industry']} Vision Inspector",
            goal=f"Decide diagnostic protocol for {inputs['industry']} and analyze evidence.",
            backstory="You determine what hazards or upsells exist in this industry context.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Marketing Strategist (Manager)",
            goal="Orchestrate and validate the 'Relay Race' phases.",
            backstory="Quality controller. You ensure the sequence follows the Day 1 notes.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (PHASED ORCHESTRATION) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_research(self):
        """Phase 1: Market Truth."""
        task = Task(
            description=f"Identify 3 competitors and persona hooks for {self.inputs['service']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Detailed Competitor Audit and Persona Mapping."
        )
        result = Crew(agents=[self.agents["analyst"]], tasks=[task]).kickoff()
        self.state.market_data = result.raw
        return "research_complete"

    @listen("research_complete")
    def phase_2_execution(self):
        """Phase 2: Modular execution based on user toggles."""
        active_tasks = []
        active_agents = []

        # Core Creative (Mandatory)
        active_agents.append(self.agents["creative"])
        active_tasks.append(Task(description="Write 3 ads (Punchy, Story, Urgency) and image prompts.", agent=self.agents["creative"], expected_output="Ad copy and visual prompts."))

        # Modular Specialist Switches
        if self.toggles.get('advice'):
            active_agents.append(self.agents["advice_director"])
            active_tasks.append(Task(description="Provide strategic roadmap.", agent=self.agents["advice_director"], expected_output="ROI Roadmap."))
            
        if self.toggles.get('sem'):
            active_agents.append(self.agents["sem_specialist"])
            active_tasks.append(Task(description="Create PPC Plan.", agent=self.agents["sem_specialist"], expected_output="SEM Strategy."))
            
        if self.toggles.get('seo'):
            active_agents.append(self.agents["seo_creator"])
            active_tasks.append(Task(description="Generate SEO Blog.", agent=self.agents["seo_creator"], expected_output="Optimized blog post."))

        if self.toggles.get('geo'):
            active_agents.append(self.agents["geo_specialist"])
            active_tasks.append(Task(description="Create Generative Engine Optimization plan.", agent=self.agents["geo_specialist"], expected_output="GEO Plan."))

        if self.toggles.get('analytics'):
            active_agents.append(self.agents["analytics_specialist"])
            active_tasks.append(Task(description="Develop GTM/GA4 tracking plan.", agent=self.agents["analytics_specialist"], expected_output="Tracking Plan."))

        if self.toggles.get('repurpose'):
            active_agents.append(self.agents["repurposer"])
            active_tasks.append(Task(description="Repurpose for social channels.", agent=self.agents["repurposer"], expected_output="Social media content pack."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = result.raw
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics_and_validation(self):
        """Phase 3: Time Management & Final Quality Audit."""
        # 1. Timeline Generation
        time_task = Task(
            description="Create a 30-day production timeline for all generated assets.",
            agent=self.agents["time_director"],
            expected_output="Gantt-style Production Schedule."
        )
        # 2. Final Strategist Audit (The "Manager")
        validation_task = Task(
            description="Review the research, creative, and schedule to ensure they are high-converting and error-free.",
            agent=self.agents["strategist"],
            expected_output="Final Manager Validation and Summary."
        )
        
        result = Crew(agents=[self.agents["time_director"], self.agents["strategist"]], tasks=[time_task, validation_task]).kickoff()
        self.state.production_schedule = result.raw
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    full_report = f"""
# 🌬️ BreatheEasy AI Swarm Report: {inputs['city']}

## 📊 Phase 1: Market Truth (Research)
{flow.state.market_data}

## 📝 Phase 2: Creative Assets & Specialist Strategy
{flow.state.ad_drafts}

## 🗓️ Phase 3: Time Management & Launch Schedule
{flow.state.production_schedule}

---
*Omni-Master v15.0 | Manager Verified*
    """
    return full_report
