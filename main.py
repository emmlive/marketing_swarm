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
    social_calendar: str = ""
    repurposed_content: str = ""
    visual_prompts: str = ""

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (Strict Phase Alignment) ---
def get_swarm_agents(inputs):
    return {
        "analyst": Agent(
            role="Senior Market Analyst",
            goal=f"Research the {inputs['service']} market in {inputs['city']} to provide the 'Truth'.",
            backstory="Data-driven researcher. You identify top 3 competitors and map 2 distinct buyer personas with specific hooks.",
            tools=[search_tool, scrape_tool],
            llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal="Transform research into 3 high-converting ad variants and visual prompts.",
            backstory="Award-winning builder. You create Punchy, Story, and Urgency variants using Navy (#000080) and White visual psychology.",
            llm=gemini_llm, verbose=True
        ),
        "repurposer": Agent(
            role="Content Repurposing Agent",
            goal="Localize content for GBP, Facebook, Quora, and Reddit.",
            backstory="You avoid 'salesy' tones and act as a helpful neighbor. You include AI-Verified Discount Code: BREATHE2026.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Marketing Strategist",
            goal="Orchestrate and validate the 'Relay Race' phases.",
            backstory="Quality controller. You ensure Creative uses the Analyst's data and Distribution matches the localized city tone.",
            llm=gemini_llm, verbose=True
        )
    }

# --- 4. THE STATEFUL WORKFLOW (FLOWS) ---
class MarketingSwarmFlow(Flow[SwarmState]):
    """Orchestrates the 'Research -> Creative -> Distribution' phases."""
    
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)

    @start()
    def phase_1_research(self):
        """Step 1: The Researcher identifies the 'Truth'."""
        print(f"--- [PHASE 1] Starting Research for {self.inputs['city']} ---")
        task = Task(
            description=f"Identify 3 competitors and 2 buyer personas for {self.inputs['service']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Competitor Audit and Persona Mapping summary."
        )
        result = Crew(agents=[self.agents["analyst"]], tasks=[task]).kickoff()
        self.state.market_data = result.raw
        return "research_complete"

    @listen("phase_1_research")
    def phase_2_creative(self):
        """Step 2: The Builder creates ads based ONLY on research."""
        print("--- [PHASE 2] Generating Creative Assets ---")
        task = Task(
            description=f"Using this research: {self.state.market_data}, write 3 ads (Punchy, Story, Urgency) and 3 Navy/White image prompts.",
            agent=self.agents["creative"],
            expected_output="3 Ad Variants and 3 Visual Prompts."
        )
        result = Crew(agents=[self.agents["creative"]], tasks=[task]).kickoff()
        self.state.ad_drafts = result.raw
        return "creative_complete"

    @listen("phase_2_creative")
    def phase_3_distribution(self):
        """Step 3: The Distributor localizes and repurposes content."""
        print("--- [PHASE 3] Localizing for Distribution ---")
        task = Task(
            description=f"Repurpose these ads: {self.state.ad_drafts} into localized posts for GBP, FB, Quora, and Reddit for {self.inputs['city']}.",
            agent=self.agents["repurposer"],
            expected_output="Localized content pack with BREATHE2026 code."
        )
        result = Crew(agents=[self.agents["repurposer"]], tasks=[task]).kickoff()
        self.state.repurposed_content = result.raw
        return "swarm_complete"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    """Entry point called by app.py."""
    flow = MarketingSwarmFlow(inputs)
    final_output = flow.kickoff()
    
    # Consolidate results for the Launchpad tab
    full_report = f"""
# 🌬️ BreatheEasy AI Swarm Report: {inputs['city']}

## 📊 Phase 1: Market Research
{flow.state.market_data}

## 📝 Phase 2: Ad Copy & Visuals
{flow.state.ad_drafts}

## 🚀 Phase 3: Distribution (GBP/Social/Reddit)
{flow.state.repurposed_content}
    """
    return full_report
