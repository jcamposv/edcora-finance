import os
from dotenv import load_dotenv

load_dotenv()

def setup_openai_env():
    """Setup OpenAI environment variables for CrewAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. CrewAI agents will use fallback methods.")
        return False
    
    # Set environment variable for CrewAI to pick up
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_MODEL_NAME"] = "gpt-3.5-turbo"
    
    return True

def get_openai_config():
    """Check if OpenAI is properly configured."""
    return setup_openai_env()

def get_advisor_config():
    """Check if OpenAI is properly configured for advisor."""
    return setup_openai_env()