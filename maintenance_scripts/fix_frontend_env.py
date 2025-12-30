import os
from dotenv import load_dotenv

def fix_env():
    # Load backend env
    load_dotenv()
    
    sb_url = os.getenv("SUPABASE_URL")
    sb_anon = os.getenv("SUPABASE_KEY")
    sb_service = os.getenv("SUPABASE_SERVICE_KEY")
    
    # Hardcoded backend url as per user request
    railway_url = "https://scraperbackend-production-1393.up.railway.app"
    
    content = f"""NEXT_PUBLIC_SUPABASE_URL={sb_url}
NEXT_PUBLIC_SUPABASE_ANON_KEY={sb_anon}
SUPABASE_SERVICE_ROLE_KEY={sb_service}
NEXT_PUBLIC_BACKEND_URL={railway_url}
"""
    
    frontend_path = os.path.join("..", "SCraper_frontend", ".env.local")
    
    print(f"Writing to {frontend_path}...")
    print(f"URL: {sb_url}")
    print(f"ANON: {sb_anon[:10]}...")
    print(f"SERVICE: {sb_service[:10]}...")
    
    with open(frontend_path, "w") as f:
        f.write(content)
        
    print("✅ Successfully wrote .env.local")

if __name__ == "__main__":
    fix_env()
