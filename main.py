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

# --- 1. SHARED STATE (EXECUTIVE DATA SLOTS) ---
class SwarmState(BaseModel):
    market_data: str = "Analysis pending..."
    competitor_ads: str = "Ad tracking pending..."
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
    geo_intel: str = "GEO mapping pending..."
    seo_article: str = "SEO Content pending..." 
    strategist_brief: str = "Final brief pending..."
    production_schedule: str = "Roadmap pending..."

# --- 2. ENGINE INITIALIZATION ---
# Using the advanced Gemini 2.0 Flash for ultra-low latency and complex reasoning
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3 # Precision-focused
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (REFINED FOR DECISION INTELLIGENCE) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')

    return {
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps and price arbitrage opportunities for {biz} in {city}.",
            backstory="""You are an expert market scientist. You quantify 'Market Entry Gaps' and 
            'Competitor Fatigue' to find local vulnerabilities.""",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Executive Creative Director (Direct Response Expert)",
            goal="Engineer psychological ad hooks and high-end cinematic video concepts.",
            backstory="""You convert emotional triggers into A/B test variables and precise 
            cinematic scene descriptions for Veo video generation.""",
            llm=gemini_llm, verbose=True
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect (E-E-A-T Specialist)",
            goal="Compose high-authority technical articles that secure AI search engine trust.",
            backstory=f"You establish {biz} as the definitive local leader through technical authority content.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose technical conversion leaks and psychological friction on {url}.",
            backstory="""You identify where money is leaking from the funnel and provide 
            developer-ready action items.""",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Architect",
            goal="Repurpose strategy into a viral Omni-channel broadcast plan.",
            backstory="Expert in viral hooks and precise deployment schedules for maximum ROI.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Local AI Search Optimization)",
            goal=f"Optimize citation velocity and Map visibility for {biz} in {city}.",
            backstory="Expert in Local Ranking Factors and AI Search (SGE) dominance.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer (The Swarm Commander)",
            goal="Synthesize all agent intelligence into a 30-day CEO roadmap.",
            backstory="The ultimate decision maker. You validate every agent's work for ROI alignment.",
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
        """Step 1: Stakeholder Discovery & Ad Tracking"""
        analyst_task = Task(
            description=f"Identify the 'Market Entry Gap' in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Markdown Executive Market Report with 'Competitor Fatigue' table."
        )
        
        ad_track_task = Task(
            description=f"Analyze live ad hooks of rivals in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Detailed breakdown of psychological hooks used by local competitors."
        )

        active_tasks = [analyst_task, ad_track_task]
        
        auditor_task = None
        if self.toggles.get('audit') and self.inputs.get('url'):
            auditor_task = Task(
                description=f"Scan {self.inputs.get('url')} for conversion friction.",
                agent=self.agents["web_auditor"],
                expected_output="Executive Technical Audit with developer action items."
            )
            active_tasks.append(auditor_task)
            
        Crew(agents=list(self.agents.values()), tasks=active_tasks, process=Process.sequential).kickoff()
        
        self.state.market_data = str(analyst_task.output.raw)
        self.state.competitor_ads = str(ad_track_task.output.raw)
        if auditor_task:
            self.state.website_audit = str(auditor_task.output.raw)
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Content Engineering & Content Production"""
        creative_task = Task(
            description="Develop 3 'Pain-Point' ad frameworks and a cinematic 'Video Prompt:' for Veo.",
            agent=self.agents["creative"],
            expected_output="Executive Creative Brief with cinematic video directions."
        )
        
        production_tasks = [creative_task]
        
        if self.toggles.get('seo'):
            seo_task = Task(
                description="Compose a technical SEO article based on market research.",
                agent=self.agents["seo_blogger"],
                expected_output="High-authority technical article."
            )
            production_tasks.append(seo_task)

        if self.toggles.get('social'):
            social_task = Task(
                description="Create a 30-day viral distribution schedule.",
                agent=self.agents["social_agent"],
                expected_output="Viral Hooks and Distribution Schedule."
            )
            production_tasks.append(social_task)

        if self.toggles.get('geo'):
            geo_task = Task(
                description="Develop a local GEO dominance plan.",
                agent=self.agents["geo_specialist"],
                expected_output="Technical GEO Intelligence Report."
            )
            production_tasks.append(geo_task)

        Crew(agents=list(self.agents.values()), tasks=production_tasks, process=Process.sequential).kickoff()
        
        self.state.ad_drafts = str(creative_task.output.raw)
        # Match State to Toggled Tasks
        for task in production_tasks:
            if "SEO Content" in task.description: self.state.seo_article = str(task.output.raw)
            if "viral" in task.description: self.state.social_plan = str(task.output.raw)
            if "GEO" in task.description: self.state.geo_intel = str(task.output.raw)
            
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 3: CEO Level Synthesis & ROI Roadmap"""
        val_task = Task(
            description="Synthesize all data into a 30-day ROI Growth Roadmap.",
            agent=self.agents["strategist"],
            expected_output="Master Growth Brief: Milestones and ROI Projections."
        )
        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        return "swarm_finished"
# --- 5. EXECUTION WRAPPER (HUMAN-READABLE INTEGRATION) ---
def run_marketing_swarm(inputs):
    """
    Kicks off the Stateful CrewAI Flow and returns a structured 
    dictionary for the Streamlit UI, including the Master PDF/Word source.
    """
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    # --- GLOBAL EXECUTIVE REPORT BUILDER ---
    # This string is the source for 'Full Report' downloads and master views.
    # We include the new 'Vision Intelligence' for a complete audit trail.
    formatted_string_report = f"""
# 🚀 {inputs['biz_name']} | EXECUTIVE INTELLIGENCE SUMMARY

## 🔍 PHASE 1: MARKET DISCOVERY & AUDIT
### Strategic Market Analysis
{flow.state.market_data}

### Competitor Ad Intelligence
{flow.state.competitor_ads}

### 👁️ Visual Intelligence & Rival Asset Audit
{flow.state.vision_intel}

### Technical Website Audit
{flow.state.website_audit}

## 📝 PHASE 2: CONTENT ENGINEERING
### Branded Creative Concepts
{flow.state.ad_drafts}

### Authority SEO Article
{flow.state.seo_article}

### Local Map & GEO Dominance
{flow.state.geo_intel}

### Omni-Channel Social Roadmap
{flow.state.social_plan}

## 🗓️ PHASE 3: EXECUTION ROADMAP (30-DAY)
{flow.state.production_schedule}

---
*Decision Intelligence generated by TechInAdvance Swarm Engine*
"""

    return {
        "analyst": flow.state.market_data,
        "ads": flow.state.competitor_ads,
        "vision": flow.state.vision_intel, # Sync with Tab 9
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article,
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report # The master source for downloads
    }
