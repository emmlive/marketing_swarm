import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start, router
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file
load_dotenv(override=True)

# --- 1. SHARED STATE (THE BLACKBOARD) ---
class SwarmState(BaseModel):
    """The shared state object that agents read from and write to."""
    campaign_goal: str = ""
    market_data: dict = {}
    ad_drafts: str = ""
    visual_concepts: str = ""
    social_calendar: str = ""
    repurposed_content: str = ""
    human_revision_notes: str = ""
    is_approved: bool = False

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. THE AGENTS (Integrated Legacy & New) ---
def get_agents(inputs):
    return {
        "strategist": Agent(
            role="Lead Marketing Strategist",
            goal=f"Transform {inputs['service']} goals into an execution plan.",
            backstory="High-reasoning orchestrator and quality controller.",
            llm=gemini_llm, verbose=True
        ),
        "analyst": Agent(
            role=f"Senior {inputs['industry']} Market Analyst",
            goal=f"Identify competitor gaps and persona mapping in {inputs['city']}.",
            backstory="Expert in identifying local pain points and purchase 'hooks'.",
            tools=[search_tool, scrape_tool],
            llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Creative Director",
            goal="Build ad copy and visual prompts based on Analyst truth.",
            backstory="Specialist in punchy, story-based, and urgency-driven copy.",
            llm=gemini_llm, verbose=True
        ),
        "vision": Agent(
            role="Vision Inspector Agent",
            goal="Perform professional visual diagnostics using smartphone imagery for ANY industry.",
            backstory="Analyzes density, contaminants, and hazards to provide objective scoring.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposing Agent",
            goal="Turn 1 blog/report into localized GBP, FB, Quora, and Reddit posts.",
            backstory="Expert at localizing content by city while avoiding 'salesy' tones.",
            llm=gemini_llm, verbose=True
        ),
        "social_mgr": Agent(
            role="Social Media Manager",
            goal="Create a 7-day social media schedule.",
            backstory="Expert at pacing content to mix offers with helpful tips.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (FLOWS) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    """Orchestrates the 'Relay Race' between agents."""
    
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_agents(inputs)

    @start()
    def initialize_campaign(self):
        """Phase 1: Research"""
        print(f"--- Starting Swarm for {self.inputs['service']} in {self.inputs['city']} ---")
        
        research_task = Task(
            description=f"Identify 3 competitors and 2 buyer personas for {self.inputs['service']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="JSON with keys: competitors, pain_points, target_demographics."
        )
        
        result = Crew(agents=[self.agents["analyst"]], tasks=[research_task]).kickoff()
        self.state.market_data = result.raw
        return "Market Research Complete"

    @listen("initialize_campaign")
    def generate_creative(self):
        """Phase 2: Creative Assets"""
        creative_task = Task(
            description=f"Using research: {self.state.market_data}, write 3 ad versions and image prompts.",
            agent=self.agents["creative"],
            expected_output="Multimodal assets (Ads + Nano Banana prompts)."
        )
        
        result = Crew(agents=[self.agents["creative"]], tasks=[creative_task]).kickoff()
        self.state.ad_drafts = result.raw
        return "Creative Assets Generated"

    @listen("generate_creative")
    def repurpose_and_schedule(self):
        """Phase 3: Distribution & Repurposing"""
        repurpose_task = Task(
            description=f"Localize this content for {self.inputs['city']} for GBP, Quora, and Reddit.",
            agent=self.agents["repurposer"],
            expected_output="Platform-specific localized content posts."
        )
        
        result = Crew(agents=[self.agents["repurposer"]], tasks=[repurpose_task]).kickoff()
        self.state.repurposed_content = result.raw
        return "Distribution Ready"

# --- 5. EXECUTION WRAPPER ---
def run_swarm(city, industry, service):
    inputs = {"city": city, "industry": industry, "service": service}
    flow = MarketingSwarmFlow(inputs)
    final_state = flow.kickoff()
    
    print("✅ Agents and Tasks completed in Stateful Workflow.")
    return final_state
