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
    vision_intel: str = "Visual audit pending..." 
    ad_drafts: str = "Creative build pending..."
    website_audit: str = "Audit pending..."
    social_plan: str = "Social strategy pending..."
    geo_intel: str = "GEO mapping pending..."
    seo_article: str = "SEO Content pending..." 
    strategist_brief: str = "Final brief pending..."
    production_schedule: str = "Roadmap pending..."

# --- 2. ENGINE INITIALIZATION ---
gemini_llm = LLM(
    model="google/gemini-2.0-flash", 
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3 
)

search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# --- 3. AGENT DEFINITIONS (OPTIMIZED FOR STRATEGIC DEPTH & FORENSICS) ---
def get_swarm_agents(inputs):
    biz = inputs.get('biz_name', 'The Business')
    city = inputs.get('city', 'the local area')
    url = inputs.get('url', 'the provided website')
    reqs = inputs.get('custom_reqs', 'Standard growth optimization.')

    return {
        "analyst": Agent(
            role="Chief Market Strategist (McKinsey Level)",
            goal=f"Identify high-value market entry gaps and price arbitrage opportunities for {biz} in {city}.",
            backstory=f"""You are an expert market scientist. You quantify 'Market Entry Gaps' and 
            'Competitor Fatigue' to find local vulnerabilities. Priority directives: {reqs}""",
            tools=[search_tool, scrape_tool], llm=gemini_llm, verbose=True
        ),
        "vision_agent": Agent(
            role="Technical Visual Auditor & Forensic Analyst",
            goal=f"Analyze field photos (Roofing, HVAC, Construction) to identify damage or defects for {biz}.",
            backstory="""You act as a technical forensics expert. You inspect photos (e.g. air ducts, roofing, 
            damage) and provide an objective 'Evidence of Need' report to help close sales.""",
            llm=gemini_llm, verbose=True
        ),
        "creative": Agent(
            role="Multichannel Direct-Response Ad Architect",
            goal="Engineer deployable ad copy for Google Search, Facebook, and Instagram + Veo concepts.",
            backstory="""Expert copywriter who understands platform constraints (character limits). 
            You move users from 'Interest' to 'Action' with ready-to-paste ad sets.""",
            llm=gemini_llm, verbose=True
        ),
        "seo_blogger": Agent(
            role="SEO Content Architect (E-E-A-T Specialist)",
            goal="Compose high-authority technical articles for SGE dominance.",
            backstory=f"Establishes {biz} as the definitive local leader with technical authority content.",
            llm=gemini_llm, verbose=True
        ),
        "web_auditor": Agent(
            role="Conversion UX Auditor",
            goal=f"Diagnose technical conversion leaks on {url}.",
            backstory="Identifies digital funnel leaks and provides developer-ready action items.",
            tools=[scrape_tool], llm=gemini_llm, verbose=True
        ),
        "social_agent": Agent(
            role="Social Distribution Architect",
            goal="Repurpose strategy into a viral Omni-channel broadcast plan.",
            backstory="Expert in viral distribution mechanics and deployment schedules.",
            llm=gemini_llm, verbose=True
        ),
        "geo_specialist": Agent(
            role="GEO Specialist (Local AI Search Optimization)",
            goal=f"Optimize citation velocity and Map visibility in {city}.",
            backstory="Expert in Local Ranking Factors and AI-driven local discovery.",
            llm=gemini_llm, verbose=True
        ),
        "strategist": Agent(
            role="Chief Growth Officer (The Swarm Commander)",
            goal="Synthesize all agent intelligence into a 30-day ROI growth roadmap.",
            backstory=f"Ultimate decision maker. Validates work against CEO vision and: {reqs}.",
            llm=gemini_llm, verbose=True
        )
    }

class MarketingSwarmFlow(Flow[SwarmState]):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = inputs
        self.agents = get_swarm_agents(inputs)
        self.toggles = inputs.get('toggles', {})

    @start()
    def phase_1_discovery(self):
        """Step 1: Stakeholder Discovery, Ad Tracking & Visual Forensics"""
        analyst_task = Task(
            description=f"Identify 'Market Entry Gaps' and analyze competitor ad hooks in {self.inputs['city']}.",
            agent=self.agents["analyst"],
            expected_output="Markdown Report with Competitor Fatigue analysis and Psychological Ad Hook deconstruction."
        )
        
        vision_task = Task(
            description=f"Analyze provided field photos (Roofing/HVAC/etc) for technical defects or rival brand weaknesses.",
            agent=self.agents["vision_agent"],
            expected_output="Detailed Forensic Report identifying damage, severity scores, and design gaps."
        )

        active_tasks = [analyst_task, vision_task]
        
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
        self.state.vision_intel = str(vision_task.output.raw) 
        
        if auditor_task:
            self.state.website_audit = str(auditor_task.output.raw)
            
        return "discovery_complete"

    @listen("discovery_complete")
    def phase_2_execution(self):
        """Step 2: Content Engineering & Ready-to-Push Ad Production"""
        
        
        creative_task = Task(
            description="""Engineer a Multichannel Ad Suite for the business:
            1. GOOGLE SEARCH: 3 Headlines (30 char), 2 Descriptions (90 char).
            2. META (FB/IG): 1 Emotional Headline, 1 Long-form Primary Text.
            3. VEO: 1 High-fidelity Cinematic Video Scene Description.""",
            agent=self.agents["creative"],
            expected_output="""Markdown table formatted as:
            | Platform | Component | Copy/Prompt |
            | :--- | :--- | :--- |"""
        )
        
        production_tasks = [creative_task]
        
        if self.toggles.get('seo'):
            production_tasks.append(Task(
                description="Compose a technical SEO authority article.",
                agent=self.agents["seo_blogger"],
                expected_output="Technical article content."
            ))

        if self.toggles.get('social'):
            production_tasks.append(Task(
                description="Create a 30-day viral distribution schedule.",
                agent=self.agents["social_agent"],
                expected_output="Viral Hooks and Schedule."
            ))

        if self.toggles.get('geo'):
            production_tasks.append(Task(
                description="Develop a local GEO dominance plan.",
                agent=self.agents["geo_specialist"],
                expected_output="Technical GEO Intelligence Report."
            ))

        Crew(agents=list(self.agents.values()), tasks=production_tasks, process=Process.sequential).kickoff()
        
        self.state.ad_drafts = str(creative_task.output.raw)
        
        for task in production_tasks:
            out = str(task.output.raw)
            if "SEO" in task.description: self.state.seo_article = out
            if "viral" in task.description: self.state.social_plan = out
            if "GEO" in task.description: self.state.geo_intel = out
            
        return "execution_complete"

    @listen("execution_complete")
    def phase_3_validation(self):
        """Step 3: CEO Level Synthesis & Phased ROI Roadmap"""
        val_task = Task(
            description="Synthesize all data into a 30-day ROI Growth Roadmap.",
            agent=self.agents["strategist"],
            expected_output="Master Growth Brief: Milestones and ROI Projections."
        )
        result = Crew(agents=[self.agents["strategist"]], tasks=[val_task]).kickoff()
        
        self.state.strategist_brief = str(result)
        self.state.production_schedule = str(result)
        
        return "swarm_finished"

# --- 5. EXECUTION WRAPPER ---
def run_marketing_swarm(inputs):
    flow = MarketingSwarmFlow(inputs)
    flow.kickoff()
    
    formatted_string_report = f"""
# 🚀 {inputs['biz_name']} | EXECUTIVE INTELLIGENCE SUMMARY

## 🔍 PHASE 1: MARKET DISCOVERY & AUDIT
### Strategic Market Analysis
{flow.state.market_data}

### 👁️ Visual Forensics & Field Audit
{flow.state.vision_intel}

### Technical Website Audit
{flow.state.website_audit}

## 📝 PHASE 2: CONTENT & MULTI-PLATFORM ADS
### Deployable Ad Suite (Google, FB, IG)
{flow.state.ad_drafts}

### Authority SEO Content
{flow.state.seo_article}

### Local GEO Dominance
{flow.state.geo_intel}

### Social Roadmap
{flow.state.social_plan}

## 🗓️ PHASE 3: 30-DAY ROI ROADMAP
{flow.state.production_schedule}
"""

    return {
        "analyst": flow.state.market_data,
        "ads": flow.state.competitor_ads,
        "vision": flow.state.vision_intel, 
        "creative": flow.state.ad_drafts,
        "strategist": flow.state.strategist_brief,
        "social": flow.state.social_plan,
        "geo": flow.state.geo_intel,
        "seo": flow.state.seo_article,
        "auditor": flow.state.website_audit,
        "full_report": formatted_string_report 
    }
