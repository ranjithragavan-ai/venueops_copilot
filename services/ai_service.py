import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Initialize the Gemini client
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_gemini_api_key_here":
    print("WARNING: GEMINI_API_KEY is missing. AI features will fail.")
    client = None
else:
    client = genai.Client(api_key=api_key)

# The model to use (Gemini 2.5 Flash is highly capable and fast for triage)
MODEL_ID = "gemini-2.5-flash"

import datetime

def load_stadium_context():
    try:
        with open("data/stadium_state.json", "r") as f:
            stadium_state = json.load(f)
            
        # Logic to auto-reset match_start_time if match has ended (start_time + 3 hours)
        now = datetime.datetime.now(datetime.timezone.utc)
        start_time_str = stadium_state.get('match_start_time')
        needs_update = False
        
        if not start_time_str:
            needs_update = True
        else:
            try:
                start_dt = datetime.datetime.fromisoformat(start_time_str)
                # Make naive datetimes UTC aware to avoid comparison errors
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                    
                # If 3 hours have passed since start time, the match has ended
                if now > start_dt + datetime.timedelta(hours=3):
                    needs_update = True
            except ValueError:
                needs_update = True
                
        if needs_update:
            new_start = now + datetime.timedelta(minutes=30)
            stadium_state['match_start_time'] = new_start.isoformat()
            with open("data/stadium_state.json", "w") as f:
                json.dump(stadium_state, f, indent=2)

        with open("data/sops.json", "r") as f:
            sops = json.load(f)
        return stadium_state, sops
    except Exception as e:
        print(f"Error loading context: {e}")
        return {}, []

class TicketSchema:
    # We define the schema for structured output to ensure we get a valid JSON for our Kanban board
    schema = {
        "type": "OBJECT",
        "properties": {
            "incident_type": {
                "type": "STRING",
                "description": "Category of the incident (e.g., Medical, Security, Maintenance, Crowd Control)"
            },
            "severity": {
                "type": "STRING",
                "description": "Priority of the incident (Low, Medium, High, Critical)"
            },
            "location": {
                "type": "STRING",
                "description": "The specific gate, sector, or area mentioned."
            },
            "building": {
                "type": "STRING",
                "description": "The building where the incident occurred. MUST be one of exactly: 'Main Stadium', 'Media Center', 'Fan Zone', 'VIP Pavilion'. Infer from location or correct typos if possible."
            },
            "floor": {
                "type": "STRING",
                "description": "The floor where the incident occurred. MUST be one of exactly: 'Basement', 'Ground Floor', 'First Floor', 'Second Floor'. Infer from location if possible."
            },
            "action_required": {
                "type": "STRING",
                "description": "A clear, actionable instruction for the staff based on the SOPs."
            },
            "sop_reference": {
                "type": "STRING",
                "description": "The ID of the relevant SOP (e.g., SOP-14, SOP-01)."
            },
            "required_role": {
                "type": "STRING",
                "description": "The primary role needed to resolve this (e.g., Cleaner, Security, Medical, Maintenance)"
            },
            "escalation_contact": {
                "type": "STRING",
                "description": "The manager or lead to escalate this to based on the SOP (e.g., Facilities Manager, Head of Security, Chief Medical Officer)."
            }
        },
        "required": ["incident_type", "severity", "location", "building", "floor", "action_required", "sop_reference", "required_role", "escalation_contact"]
    }

def triage_incident(report_text):
    """
    Takes a raw text report from a volunteer and uses Gemini Structured Outputs
    to generate a clean, actionable ticket.
    """
    if not client:
        return {"error": "API Key not configured."}

    stadium_state, sops = load_stadium_context()
    
    system_instruction = f"""
    You are the central AI operational intelligence engine for the FIFA World Cup 2026.
    You receive raw incident reports from volunteers and must triage them instantly based on 
    current stadium state and Standard Operating Procedures (SOPs).
    
    CURRENT STADIUM STATE:
    {json.dumps(stadium_state, indent=2)}
    
    AVAILABLE SOPs:
    {json.dumps(sops, indent=2)}
    
    Extract the details of the reported incident and match it to the most relevant SOP.
    Assess severity based on crowd density and match context.
    Output MUST follow the provided JSON schema perfectly.
    """
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=report_text,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=TicketSchema.schema,
                temperature=0.1 # Low temperature for analytical tasks
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error during Gemini generation: {e}")
        return {"error": str(e)}

def chat_with_copilot(chat_history, new_message):
    """
    General purpose chat for operational queries (e.g. "Which gates are crowded?")
    """
    if not client:
        return "I am offline because my API key is not configured."
        
    stadium_state, sops = load_stadium_context()
    
    system_instruction = f"""
    You are the VenueOps Copilot, a highly professional AI assistant for the Stadium Venue Manager.
    Your goal is to help them make decisions. Be concise, direct, and actionable.
    
    CURRENT STADIUM STATE:
    {json.dumps(stadium_state, indent=2)}
    
    AVAILABLE SOPs:
    {json.dumps(sops, indent=2)}
    """
    
    # Construct conversation history
    contents = []
    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=new_message)]))
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4
            )
        )
        return response.text
    except Exception as e:
        print(f"Error during Gemini generation: {e}")
        return "Sorry, I encountered an error while processing your request."
