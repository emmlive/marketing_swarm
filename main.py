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
    website_audit: str = ""
    vision_score: int = 0
    vision_findings: str = ""

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
    return {
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Research the {inputs['service']} market in {inputs['city']}.",
            backstory="Data-driven researcher focused on competitor gaps.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal="Transform research into Navy/White branded ad variants.",
            backstory="Master of visual psychology and conversion hooks.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager",
            goal="Analyze the provided URL for conversion and SEO leaks.",
            backstory="Specialist in UX and site performance audits.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "vision_inspector": Agent(
            role=f"Autonomous {inputs['industry']} Vision Inspector",
            goal=f"Analyze visual evidence and assign a safety score (1-10).",
            backstory=f"Expert in {inputs['industry']} diagnostics. You look for 'Receipts' of hazards.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a 30-day Gantt-style production timeline.",
            backstory="Expert Project Manager calculating Level of Effort.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Marketing Strategist (Manager)",
            goal="Validate all outputs and ensure project ROI.",
            backstory="Quality controller ensuring alignment with Day 1 project notes.",
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
    def phase_1_research_and_audit(self):
        """Phase 1: Market Truth & Web Audit."""
        active_tasks = []
        active_agents = [self.agents["analyst"]]
        
        active_tasks.append(Task(description=f"Market Audit for {self.inputs['service']}.", agent=self.agents["analyst"], expected_output="Market Report"))
        
        if self.toggles.get('website_audit') and self.inputs.get('website_url'):
            active_agents.append(self.agents["web_auditor"])
            active_tasks.append(Task(description=f"Audit {self.inputs['website_url']}.", agent=self.agents["web_auditor"], expected_output="Site Audit Report"))

        result = Crew(agents=active_agents, tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        return "research_complete"

    @listen("research_complete")
    def phase_2_execution(self):
        """Phase 2: Creative & Distribution Swarm."""
        active_tasks = []
        active_agents = [self.agents["creative"]]
        
        active_tasks.append(Task(description="Write 3 Navy/White ad variants.", agent=self.agents["creative"], expected_output="Ad variants."))
        
        # Modular logic (Simplified for brevity - include SEM, SEO, GEO, etc here as per v15)
        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics_and_validation(self):
        """Phase 3: Final Timeline & Manager Review."""
        time_task = Task(description="Create 30-day timeline.", agent=self.agents["time_director"], expected_output="Gantt Schedule.")
        val_task = Task(description="Validate all work.", agent=self.agents["strategist"], expected_output="Final Validation.")
        
        result = Crew(agents=[self.agents["time_director"], self.agents["strategist"]], tasks=[time_task, val_task]).kickoff()
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    return flow.state
