import os
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force fresh read
load_dotenv(override=True)

# --- 1. SHARED STATE ---
class SwarmState(BaseModel):
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

# --- 3. AGENT DEFINITIONS (Refined for Information Gain & Budget Forecasting) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    usp = inputs.get('usp', 'Innovation')
    ind = inputs.get('industry', 'General Industry')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Conversion Psychologist & Market Analyst",
            goal=f"Identify real-time competitor gaps in {city} for {biz} through Consumer Behavior logic.",
            backstory=f"Expert in Neuromarketing. You find 'Conversion Leaks' on {url} and Trust Deficits in {city}.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Lead Creative Strategist",
            goal=f"Transform USP ({usp}) into Navy/White branded ad assets that trigger emotional buying.",
            backstory="Psychological builder. You use Navy and White to convey elite trust and authority.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager",
            goal=f"Identify conversion leaks on {url}.",
            backstory="UX specialist. You diagnose why visitors don't convert using Fitts's Law.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "sem_specialist": Agent(
            role="SEM Budget Forecaster & PPC Specialist",
            goal=f"Create a high-intent Google Ads strategy and an automated budget forecast for {biz}.",
            backstory=(
                f"PPC expert. You calculate projected Cost Per Acquisition (CPA) and ROAS for {ind} in {city}. "
                f"You provide a three-tier budget forecast (conservative, aggressive, and scaling) based on local CPC trends."
            ),
            llm=gemini_llm, verbose=True
        ),
        "seo_creator": Agent(
            role="SEO Authority Strategist",
            goal=f"Generate 'Information Gain' content for {biz} that outranks generic AI fluff.",
            backstory=(
                f"Expert in Google's Information Gain patents. You produce {ind} content with "
                f"unique data, contrarian hooks, and personal experience that LLMs cannot replicate."
            ),
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Generative Engine Optimization)",
            goal=f"Ensure ChatGPT, Perplexity, and Gemini cite {biz} as the authority.",
            backstory="AI Search expert focused on 'Citation Velocity' and mapping the brand in LLM training paths.",
            llm=gemini_llm, verbose=True
        ),
        "time_director": Agent(
            role="Time Management Director",
            goal="Create a 30-day production schedule for the client.",
            backstory="Expert PM translating swarm output into a simple Gantt-style roadmap.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Manager)",
            goal="Audit the entire swarm output for maximum ROI and brand consistency.",
            backstory="Final gatekeeper. You ensure the output is high-fidelity and elite.",
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
        active_tasks = []
        active_tasks.append(Task(
            description=f"Analyze market psychology and competitor gaps for {self.inputs['biz_name']} in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Psychological Market Truth Report."
        ))

        if self.toggles.get('audit') and self.inputs.get('url'):
            active_tasks.append(Task(
                description=f"Audit {self.inputs['url']} for conversion leaks.",
                agent=self.agents["web_auditor"],
                expected_output="Technical UX Audit findings."
            ))

        result = Crew(agents=[self.agents["analyst"], self.agents.get("web_auditor")] if self.toggles.get('audit') else [self.agents["analyst"]], 
                      tasks=active_tasks).kickoff()
        self.state.market_data = str(result)
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        active_tasks = []
        active_agents = [self.agents["creative"]]
        
        # Mandatory Creative
        active_tasks.append(Task(
            description=f"Create Navy/White ad copies using {self.inputs['usp']} and the Psychologist's findings.",
            agent=self.agents["creative"],
            expected_output="3 Ad variants."
        ))

        # BUDGET FORECASTING INTEGRATION (SEM Agent)
        if self.toggles.get('sem'):
            active_agents.append(self.agents["sem_specialist"])
            active_tasks.append(Task(
                description=f"Develop a PPC strategy and a 3-tier budget forecast for {self.inputs['industry']} in {self.inputs['city']}.",
                agent=self.agents["sem_specialist"],
                expected_output="SEM Strategy + Automated Budget & ROI Forecast Table."
            ))

        # INFORMATION GAIN INTEGRATION (SEO Agent)
        if self.toggles.get('seo'):
            active_agents.append(self.agents["seo_creator"])
            active_tasks.append(Task(
                description="Generate an Information Gain article outline that challenges industry myths.",
                agent=self.agents["seo_creator"],
                expected_output="Information Gain SEO Content Strategy."
            ))

        if self.toggles.get('geo'):
            active_agents.append(self.agents["geo_specialist"])
            active_tasks.append(Task(description="LLM Citation velocity plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report."))

        result = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential).kickoff()
        self.state.ad_drafts = str(result)
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_logistics_and_audit(self):
        time_task = Task(description="Build a 30-day Gantt roadmap.", agent=self.agents["time_director"], expected_output="Production Schedule.")
        val_task = Task(description="Review all outputs for ROI.", agent=self.agents["strategist"], expected_output="Manager Approval.")

        result = Crew(agents=[self.agents["time_director"], self.agents["strategist"]], tasks=[time_task, val_task]).kickoff()
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    return f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Execution, SEO IG & Budget Forecast
{flow.state.ad_drafts}

## 🗓️ Phase 3: Managerial Review & Roadmap
{flow.state.production_schedule}

---
*Generated by TechInAdvance AI | Strategist Verified*
"""
