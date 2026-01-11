import os
import json
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force fresh read of environment variables
load_dotenv(override=True)

# --- 1. SHARED STATE (STRICTLY ISOLATED FIELDS) ---
class SwarmState(BaseModel):
    market_data: str = "Analysis pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
    geo_intel: str = "GEO mapping pending..."
    seo_article: str = "SEO Article pending..."  # CHAPTER 9 INTEGRATION
    strategist_brief: str = "Final brief pending..."
    production_schedule: str = "Roadmap pending..."

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.4 # Grounded temperature to prevent hallucinations
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Senior Market Analyst (The Fact-Finder)",
            goal=f"Extract real-time competitor gaps in {city} and provide Buyer Personas in STRICT JSON format.",
            backstory="You are a literalist data scientist. Hallucination is a firing offense. If data is not found, state 'Data not found'.",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True, allow_delegation=False
        ),
        "creative": Agent(
            role="Creative Director (The Multimodal Architect)",
            goal="Transform Analyst data into branded assets and cinematic video prompts for the Veo model.",
            backstory="You build high-conversion copy. You also specialize in writing vivid 'Video Prompts' for AI video generators based on research.",
            llm=gemini_llm, verbose=True, allow_delegation=False
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect (The Blogger)",
            goal="Write a 2,000-word high-authority SEO article based on the Analyst's research findings.",
            backstory="Expert in E-E-A-T SEO. You turn market data into deep-dive educational content that ranks #1.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Website Audit Manager (The UX Skeptic)",
            goal=f"Diagnose conversion leaks on {url} using technical UX principles.",
            backstory="You use the Scrape tool to find 'Friction Points'. You focus on CTA clarity and accessibility. No guessing.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Specialist",
            goal="Repurpose strategy into viral hooks for Meta, Google, and LinkedIn.",
            backstory="Expert in algorithmic engagement hooks without exaggeration.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (AI Search Optimization)",
            goal=f"Optimize {biz} for citation velocity in AI search engines for {city}.",
            backstory="AI Search expert. Identify local keyword clusters and citation paths to make the brand an LLM-cited authority.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Lead Strategist (The Swarm Commander)",
            goal="Orchestrate agents and validate outputs for ROI alignment.",
            backstory="Final gatekeeper. You reject any creative output that isn't backed by research facts.",
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
        """Step 1: Grounded Research and Technical Auditing"""
        analyst_task = Task(
            description=f"Identify top 3 competitors for {self.inputs['biz_name']} in {self.inputs['city']}. Output JSON Schema: {{'competitors': [], 'personas': [{{'name': '', 'pain_points': [], 'trigger': '', 'mood': ''}}]}}.",
            agent=self.agents["analyst"],
            expected_output="JSON Market Truth Report."
        )

        active_tasks = [analyst_task]
        active_agents = [self.agents["analyst"]]

        auditor_task = None
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for conversion leaks and friction.",
                agent=self.agents["web_auditor"],
                expected_output="Technical UX Audit findings."
            )
            active_tasks.append(auditor_task)
            active_agents.append(self.agents["web_auditor"])
            
        # SEQUENTIAL for tool stability
        crew = Crew(agents=active_agents, tasks=active_tasks, process=Process.sequential)
        crew.kickoff()
        
        self.state.market_data = analyst_task.output.raw if analyst_task.output else "Researcher data missing."
        if auditor_task:
            self.state.website_audit = auditor_task.output.raw if auditor_task.output else "Audit results missing."
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Creative, SEO & Specialist Production"""
        creative_task = Task(
            description=(
                "Using the Analyst's JSON, build 3 ad variants. "
                "ALSO, write a specific section labeled 'Video Prompt:' for the Veo model."
            ),
            agent=self.agents["creative"],
            expected_output="Branded Assets and a specific 'Video Prompt:' section."
        )
        
        production_tasks = [creative_task]
        production_agents = [self.agents["creative"]]

        # Chapter 9: SEO Blogger
        seo_task = None
        if self.toggles.get('seo'):
            seo_task = Task(
                description="Write a 2,000-word authority SEO article based on the Analyst's market research.",
                agent=self.agents["seo_blogger"],
                expected_output="Long-form SEO Article."
            )
            production_tasks.append(seo_article) # Added to task list
            production_agents.append(self.agents["seo_blogger"])

        # Other Specialists
        social_task = None
        if self.toggles.get('social'):
            social_task = Task(description="Viral hooks.", agent=self.agents["social_agent"], expected_output="Social Plan.")
            production_tasks.append(social_task); production_agents.append(self.agents["social_agent"])

        geo_task = None
        if self.toggles.get('geo'):
            geo_task = Task(description="GEO AI search plan.", agent=self.agents["geo_specialist"], expected_output="GEO Report.")
            production_tasks.append(geo_task); production_agents.append(self.agents["geo_specialist"])

        crew = Crew(agents=production_agents, tasks=production_tasks, process=Process.sequential)
        crew.kickoff()
        
        # Isolated State Assignment
        self.state.ad_drafts = creative_task.output.raw
        if seo_task: self.state.seo_article = seo_task.output.raw
        if social_task: self.state.social_plan = social_task.output.raw
        if geo_task: self.state.geo_intel = geo_task.output.raw
        
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 4: Strategic Finalization"""
        val_task = Task(
            description="Synthesize all outputs into a 30-day ROI brief.",
            agent=self.agents["strategist"],
            expected_output="Verified Master Brief and Roadmap."
        )

        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER (ISOLATED DICTIONARY) ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # Unified report for global exports
    formatted_string_report = f"""
# 🌬️ {inputs['biz_name']} Omni-Swarm Report

## 🔍 Phase 1: Discovery & Site Audit
{flow.state.market_data}

## 📝 Phase 2: Execution, Creative & Social
{flow.state.ad_drafts}

## 🗓️ Phase 3: Managerial Review & Roadmap
{flow.state.production_schedule}

---
*Generated by TechInAdvance AI | Strategist Verified*
"""

    return {
        "analyst": flow.state.market_data,
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article, # Chapter 9 Return
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report
    }
