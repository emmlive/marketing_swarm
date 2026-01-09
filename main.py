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
    Dynamically assembles the Crew based on user inputs.
    Injects 'premium' and 'blog' flags into the agent task descriptions.
    """
    
    # Initialize tasks by calling the methods from our MarketingTasks class
    # This ensures the LLM 'sees' the specific city and premium focus
    t1 = tasks.research_task(agents.market_analyst, city, industry, service, premium)
    t2 = tasks.creative_task(agents.creative_director, city, industry, service, premium, blog)
    t3 = tasks.review_task(agents.proofreader, city, industry, service)
    
    # Task 4 & 5 use 'context' so they work on the POLISHED version from Task 3
    t4 = tasks.campaign_task(agents.social_media_manager, city, industry, service, t3) 
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
    Unpacks the inputs and kicks off the execution.
    """
    crew_instance = create_marketing_crew(
        city=inputs.get('city', 'Naperville, IL'),
        industry=inputs.get('industry', 'HVAC'),
        service=inputs.get('service', 'Service'),
        premium=inputs.get('premium', True),
        blog=inputs.get('blog', True)
    )
    # Return the raw result so app.py can parse or save it
    return crew_instance.kickoff()

# --- FOR MANUAL TERMINAL TESTING ---
def main():
    print("🌬️ BreatheEasy AI: High-Ticket Engine Initialized.")

    inputs = {
        'city': input("City: ") or "Naperville, IL",
        'industry': input("Industry: ") or "HVAC",
        'service': input("Service: ") or "Full System Replacement",
        'premium': input("Premium (y/n): ").lower() == 'y',
        'blog': input("Include Blog (y/n): ").lower() == 'y'
    }

    print(f"\n🚀 Launching Swarm for {inputs['city']}...")
    result = run_marketing_swarm(inputs)
    print("\n✅ CAMPAIGN COMPLETE!")

if __name__ == "__main__":
    main()
