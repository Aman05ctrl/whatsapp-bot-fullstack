"""
Conversation Stage System - REWRITTEN FOR MAIN.PY ALIGNMENT
============================================================
Matches exact AI prompt flow from main.py:
MSG 1: Name + City
MSG 2-3: Purpose → Type (ONE at a time)
MSG 4+: Budget → Email → Properties

Version: 3.0 (Production - Main.py Aligned)
Date: March 28, 2026
"""

from enum import Enum
from typing import Dict
import threading
import logging

logger = logging.getLogger(__name__)

def safe_log_info(message: str):
    try:
        logger.info(message)
    except Exception:
        print(f"[INFO] {message}")

def safe_log_warning(message: str):
    try:
        logger.warning(message)
    except Exception:
        print(f"[WARNING] {message}")

# ============================================================================
# STAGES - Aligned with main.py MSG flow
# ============================================================================
class ConversationStage(Enum):
    """
    5 stages matching main.py message flow:
    - GREETING: MSG 1 only
    - DISCOVERY: MSG 2-3 (city → purpose → type)
    - QUALIFICATION: MSG 4+ (budget → email)
    - ENGAGEMENT: Showing properties
    - HANDOVER: Ready for specialist
    """
    GREETING = "greeting"
    DISCOVERY = "discovery"
    QUALIFICATION = "qualification"
    ENGAGEMENT = "engagement"
    HANDOVER = "handover"

# ============================================================================
# STAGE MANAGER - Thread-safe, deadlock-free
# ============================================================================
class ConversationStageManager:
    """
    Manages conversation stages matching main.py AI prompt rules.
    
    CRITICAL FIX: No nested locks - all lock operations are flat.
    """
    
    def __init__(self):
        self.lock = threading.Lock() # Ek time pe ek hi process data edit kare.
        self.user_stages: Dict[str, ConversationStage] = {} # Har user ka current stage store karega.
        self.user_data: Dict[str, dict] = {} # Har user ki info store karega.
        
        # Stage requirements matching main.py flow
        self.STAGE_REQUIREMENTS = {       # Kis stage me jaane ke liye kya kya required hai.
            ConversationStage.GREETING: {
                "required": [],
                "description": "MSG 1 - Initial contact"
            },
            ConversationStage.DISCOVERY: {  #Greeting hone ke baad hi discovery phase.
                "required": ["greeted"],
                "description": "MSG 2-3 - Collecting city/purpose/type"
            },
            ConversationStage.QUALIFICATION: {
                "required": ["greeted", "city_mentioned", "purpose_asked", "type_asked"],
                "description": "MSG 4+ - Budget and email"
            },
            ConversationStage.ENGAGEMENT: {
                "required": ["greeted", "city_mentioned", "purpose_asked", "type_asked", "budget_asked"],
                "description": "Showing properties"
            },
            ConversationStage.HANDOVER: {
                "required": ["greeted", "city_mentioned", "purpose_asked", "type_asked", "budget_asked", "email_collected"],
                "description": "Ready for specialist"
            }
        }
        
        # AI Instructions - EXACTLY matching main.py rules
        self.STAGE_AI_INSTRUCTIONS = {                      # Har stage me AI ko kya bolna hai uske rules.
            ConversationStage.GREETING: """
YOU ARE AT MSG 1 - FIRST CONTACT.

STRICT RULES FOR MSG 1:
- Use user's name ONCE: "Hi {name}! 👋"
- Introduce: "I'm Sarah, your property consultant"
- Ask ONE question ONLY: "Which city interests you?"
- DO NOT ask: email, budget, purpose, or property type
- Keep it 2 sentences max

ALLOWED ACTION: "send_text" ONLY
FORBIDDEN: Do NOT send properties, do NOT ask multiple questions
            """,
            
            ConversationStage.DISCOVERY: """
YOU ARE AT MSG 2-3 - DISCOVERY PHASE.

CHECK CONTEXT FIRST:
- If city == "Not Mentioned" → Ask: "Which city interests you? (Dubai, Abu Dhabi, UK)"
- If city known BUT purpose == "Not Asked" → Ask: "Is this for investment or personal use?"
- If purpose known BUT prop_type == "Not Asked" → Ask: "What type of property? ('apartment', 'villa', 'plot', 'commercial', 'farmhouse', 'other')"

STRICT RULES:
- Ask ONE question at a time ONLY
- DO NOT use user's name (already used in MSG 1)
- DO NOT ask email yet (too early)
- DO NOT show properties yet (need more info)
- Keep it conversational, 2-3 sentences max

ALLOWED ACTION: "send_text" ONLY
FORBIDDEN: Do NOT send properties yet, do NOT ask email
            """,
            
            ConversationStage.QUALIFICATION: """
YOU ARE AT MSG 4+ - QUALIFICATION PHASE.

CHECK CONTEXT FIRST - Ask ONLY what's missing:
- If budget == "Not Specified" → Ask FIRST: "What budget range are you working with?"
- If budget known AND email == "Not Provided" AND message_count >= 4 → Ask: "Where should I send the brochures? 📧"
- DO NOT ask about purpose/type again - already collected
- If budget + email known → action = "send_properties"

STRICT RULES:
- ONE question at a time
- DO NOT repeat questions already answered
- DO NOT use user's name
- If user asks to see properties → action = "send_properties"
- Keep it helpful, 2-3 sentences max

ALLOWED ACTIONS: "send_text" or "send_properties" (if user requests)
FORBIDDEN: Do NOT ask already-answered questions
            """,
            
            ConversationStage.ENGAGEMENT: """
YOU ARE IN ENGAGEMENT - SHOWING PROPERTIES.

STRICT RULES:
- Answer questions about properties shown
- Provide details user asks for
- DO NOT push for meetings yet
- Let user explore naturally
- Keep it informative, 2-3 sentences max

ALLOWED ACTIONS: "send_text", "send_properties"
FORBIDDEN: Do NOT force handover, do NOT push meetings
            """,
            
            ConversationStage.HANDOVER: """
YOU ARE AT HANDOVER - USER IS READY.

TRIGGER: User said "contact me", "book viewing", "meet agent", or similar.

NOW you can:
- Mention specialists
- Schedule meetings
- Offer consultations

STRICT RULES:
- ONLY if user showed intent
- Keep it professional, 2-3 sentences max

ALLOWED ACTIONS: "send_text", "handover", "schedule_meeting"
            """
        }
    
    def get_user_stage(self, user_id: str) -> ConversationStage:            # User ka current stage return karta hai.
        """Get current stage. Thread-safe, no nested locks."""
        with self.lock:
            if user_id not in self.user_stages:                             # Naya user ho toh greeting se start.
                return ConversationStage.GREETING
            return self.user_stages[user_id]
    
    def update_user_data(self, user_id: str, key: str, value: any):         # User ke data me nayi info save karta hai.
        """Update user data. Thread-safe."""
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            self.user_data[user_id][key] = value
    
    def get_user_data(self, user_id: str) -> dict:
        """Get all user data. Thread-safe."""
        with self.lock:
            return self.user_data.get(user_id, {}).copy()                  # User ka pura data return karega.
    
    def check_stage_requirements(self, user_id: str, stage: ConversationStage) -> bool:
        """Check if user meets requirements for a stage."""
        with self.lock:
            requirements = self.STAGE_REQUIREMENTS[stage]["required"]
            user_info = self.user_data.get(user_id, {})
            return all(user_info.get(req, False) for req in requirements)
    
    def advance_stage_if_ready(self, user_id: str): #Current stage kya hai,Next stage ki requirements complete hui?Agar hui toh next stage me bhej do.
        """
        Advance stage based on collected data.
        CRITICAL FIX: No nested locks - direct access to user_stages.
        """
        with self.lock:
            # Direct access - avoid calling get_user_stage (nested lock)
            if user_id not in self.user_stages:
                current_stage = ConversationStage.GREETING
            else:
                current_stage = self.user_stages[user_id]
            
            # Stage progression order
            stages_order = [                        # Stage ka order define hai.
                ConversationStage.GREETING,
                ConversationStage.DISCOVERY,
                ConversationStage.QUALIFICATION,
                ConversationStage.ENGAGEMENT,
                ConversationStage.HANDOVER
            ]
            
            current_idx = stages_order.index(current_stage)
            
            # Try to advance ONE stage at a time
            for i in range(current_idx + 1, len(stages_order)):
                next_stage = stages_order[i]
                requirements = self.STAGE_REQUIREMENTS[next_stage]["required"]
                user_info = self.user_data.get(user_id, {})
                
                # Check if requirements met
                if all(user_info.get(req, False) for req in requirements):
                    self.user_stages[user_id] = next_stage
                    safe_log_info(f"[STAGE] Advancing {user_id[-4:]} from {current_stage.value} to {next_stage.value}")
                    break  # ONLY advance ONE stage per call
                else:
                    break
    
    def get_ai_instructions(self, user_id: str) -> str:    # Current stage ke hisaab se AI prompt rules return karega.
        """Get stage-specific AI instructions."""
        with self.lock:
            # Direct access - avoid nested lock
            if user_id not in self.user_stages:
                stage = ConversationStage.GREETING
            else:
                stage = self.user_stages[user_id]
            return self.STAGE_AI_INSTRUCTIONS[stage]
    
    def can_ai_handover(self, user_id: str) -> bool:     # Agar handover stage hai toh True.
        """Check if AI can handover to human."""
        with self.lock:
            # Direct access
            if user_id not in self.user_stages:
                current = ConversationStage.GREETING
            else:
                current = self.user_stages[user_id]
            return current == ConversationStage.HANDOVER
    
    def detect_handover_attempt(self, ai_response: str) -> bool: # Agar AI jaldi human transfer karne ki baat kare toh detect karega, specialist
        """Detect if AI trying to handover prematurely."""
        handover_keywords = [
            'specialist', 'consultant will', 'team will reach',
            'schedule a call', 'book a viewing', 'arrange a meeting',
            'connect you with', 'have someone contact'
        ]
        response_lower = ai_response.lower()
        return any(keyword in response_lower for keyword in handover_keywords)
    
    def reset_user_state(self, user_id: str):
        """Reset user state (for testing)."""
        with self.lock:
            if user_id in self.user_stages:
                del self.user_stages[user_id]       # User ka pura state reset.
            if user_id in self.user_data:
                del self.user_data[user_id]

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
stage_manager = ConversationStageManager()  # Is class ka object bana diya gaya.

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def update_conversation_stage(user_id: str, user_city: str, user_interest: str,         # Yeh real chat ke time run hoga.
                              user_email: str, message: str):
    """
    Update stage based on collected info.
    Matches main.py message flow exactly.
    """
    msg_lower = message.lower()
    
    # Mark greeting
    greetings = ['hi', 'hello', 'hey', 'good morning', 'hii', 'hola', 'namaste', 'hely']
    if any(g in msg_lower for g in greetings):                                         # Agar hi/hello likha user ne.
        stage_manager.update_user_data(user_id, 'greeted', True)
    
    # Mark city mentioned
    if user_city != "Not Mentioned":
        stage_manager.update_user_data(user_id, 'city_mentioned', True)             # City mil gayi toh mark true.
    
    # Mark interest type
    if user_interest != "Not Specified":                                            # Purpose mil gaya.
        stage_manager.update_user_data(user_id, 'interest_type', True)
        stage_manager.update_user_data(user_id, 'purpose_asked', True)

    # Mark budget asked
    budget_keywords = ['lakh', 'crore', 'aed', 'dirham', 'thousand', 'million', 'budget']
    if any(keyword in msg_lower for keyword in budget_keywords):
        stage_manager.update_user_data(user_id, 'budget_asked', True)    


    # Mark property type asked
    property_types = ['apartment', 'villa', 'plot', 'commercial', 'farmhouse', 'other'] # Agar user ne property type mention kiya toh mark true.
    if any(ptype in msg_lower for ptype in property_types):
        stage_manager.update_user_data(user_id, 'type_asked', True)    
    
    
    # Mark email collected
    if user_email != "Not Provided":                                                # Email mil gaya.       
        stage_manager.update_user_data(user_id, 'email_collected', True)
    
    # Mark explicit consent for contact
    consent_phrases = ['contact me', 'call me', 'reach out', 'yes contact',         # Agar user ne bola toh consent true.
                      'schedule viewing', 'book appointment', 'arrange viewing']
    if any(phrase in msg_lower for phrase in consent_phrases):
        stage_manager.update_user_data(user_id, 'user_consent', True)
    
    # Advance stage if ready
    stage_manager.advance_stage_if_ready(user_id)                                       # Stage update kar dega.

def get_stage_aware_fallback(user_id: str) -> str:                  # Agar AI fail ho jaye toh stage ke hisaab se fallback reply dega.
    """Get fallback message based on stage."""
    current_stage = stage_manager.get_user_stage(user_id)
    
    fallback_messages = {
        ConversationStage.GREETING: 
            "Hi! 👋 Which city interests you? (Dubai, Abu Dhabi, UK)",
        
        ConversationStage.DISCOVERY: 
            "I'd love to help! What brings you to property search today?",
        
        ConversationStage.QUALIFICATION: 
            "Great! What budget range are you considering?",
        
        ConversationStage.ENGAGEMENT: 
            "Would you like to see some property options?",
        
        ConversationStage.HANDOVER: 
            "I can connect you with our specialist. Interested?"
    }
    
    return fallback_messages.get(current_stage, 
                                 "How can I assist you with your property search?")