import os

# 1. SILENCE TELEMETRY - Must stay at the top
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Crew, Process
import agents 
from tasks import MarketingTasks 

# Instantiate the Task Factory globally for the module
tasks = MarketingTasks()

def create_marketing_crew(city, industry, service, premium, blog):
    """
    Assembles the Crew to generate a Full Strategy, 7-Day Calendar, 
    and Competitor Battlecard.
    """
    
    # Task 1: Research & Battlecard (Analysis of local competitors)
    t1 = tasks.research_task(agents.market_analyst, city, industry, service, premium)
    
    # Task 2: Creative Strategy (The core marketing angles)
    t2 = tasks.creative_task(agents.creative_director, city, industry, service, premium, blog)
    
    # Task 3: Quality Control
    t3 = tasks.review_task(agents.proofreader, city, industry, service)
    
    # Task 4: 7-DAY CONTENT CALENDAR (NEW FOCUS)
    # We update the campaign task to specifically produce a Monday-Sunday schedule
    t4 = tasks.campaign_task(agents.social_media_manager, city, industry, service, t3) 
    
    # Task 5: Vision & Ad Preview Logic
    t5 = tasks.vision_task(agents.vision_inspector, city, industry, service, [t3, t4]) 

    return Crew(
        agents=[
            agents.market_analyst, 
            agents.creative_director, 
            agents.proofreader,
            agents.social_media_manager,
            agents.vision_inspector
        ],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
        memory=False, 
        cache=True,
        max_rpm=2 
    )

# --- GLOBAL WRAPPER: This is what app.py calls ---
def run_marketing_swarm(inputs):
    """
    Unpacks inputs, kicks off execution, and saves the final result
    to a file that app.py consumes.
    """
    crew_instance = create_marketing_crew(
        city=inputs.get('city', 'Naperville, IL'),
        industry=inputs.get('industry', 'HVAC'),
        service=inputs.get('service', 'Service'),
        premium=inputs.get('premium', True),
        blog=inputs.get('blog', True)
    )
    
    # Kickoff the swarm
    result = crew_instance.kickoff()
    
    # --- CRITICAL UPDATE: Save result to file for app.py ---
    # We save the string representation of the final CrewAI output
    with open("final_marketing_strategy.md", "w", encoding="utf-8") as f:
        f.write(str(result))
        
    return result

# --- FOR MANUAL TERMINAL TESTING ---
def main():
    print("🌬️ BreatheEasy AI: High-Ticket Engine Initialized.")

    inputs = {
        'city': "Naperville, IL",
        'industry': "HVAC",
        'service': "Full System Replacement",
        'premium': True,
        'blog': True
    }

    print(f"\n🚀 Launching Swarm for {inputs['city']}...")
    result = run_marketing_swarm(inputs)
    print("\n✅ CAMPAIGN COMPLETE!")

if __name__ == "__main__":
    main()
