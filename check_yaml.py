import yaml
from yaml.loader import SafeLoader

try:
    with open('config.yaml', 'r') as file:
        config = yaml.load(file, Loader=SafeLoader)
    
    admin_data = config['credentials']['usernames']['admin']
    print("--- YAML SUCCESS ---")
    print(f"Admin Username: admin")
    print(f"Admin Email: {admin_data['email']}")
    print(f"Hashed Password found: {admin_data['password'][:10]}...") 
except Exception as e:
    print(f"--- YAML ERROR ---\n{e}")