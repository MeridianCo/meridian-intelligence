import os
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Load Gemini API key from .env
api_key = os.getenv("GEMINI_API_KEY")

# Load agent role prompt
main_role_prompt = Path(BASE_DIR / "prompts" / "agent_role.txt").read_text().strip()

# Init Gemini client as a class
class GeminiAgent:
    def __init__(self, api_key=api_key):
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.5-flash"  # Default model (free tier)
        self.role = main_role_prompt
        
    def generate_content(self, user_context, target_context, instruction):
        system_prompt = ("TODO") # need to create system prompt and agent_role.txt
        
        response = self.client.models.generate_content(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            ),
            contents=instruction
        )
        return response.text
            
    