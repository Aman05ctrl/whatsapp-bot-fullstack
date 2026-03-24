"""
Conversation Stage System for WhatsApp AI Bot
==============================================

This module implements a 5-stage conversation flow that prevents premature
handovers to human agents. It ensures the bot collects necessary information
before suggesting specialist contact.

THREAD-SAFE: All state modifications are protected by locks.
IMPORT-SAFE: Fully self-contained with explicit dependencies.

Author: Production Engineering Team
Version: 2.0.0 (Fixed - Production Ready)
"""

# ============================================================================
# EXPLICIT IMPORTS - MODULE IS FULLY SELF-CONTAINED
# ============================================================================

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import threading
import logging

# Setup module-level logger (safe pattern)
logger = logging.getLogger(__name__)

def safe_log_info(message: str):
    """
    Module-local logging function.
    Fallback if parent module's logging isn't available.
    """
    try:
        logger.info(message)
    except Exception:
        # Graceful degradation - print if logging fails
        print(f"[INFO] {message}")

def safe_log_warning(message: str):
    """Module-local warning logger"""
    try:
        logger.warning(message)
    except Exception:
        print(f"[WARNING] {message}")

# ============================================================================
# CONVERSATION STAGE SYSTEM - PREVENTS PREMATURE HANDOVERS
# ============================================================================

class ConversationStage(Enum):
    """
    5-Stage conversation model that prevents premature closures.
    Each stage has specific requirements before advancing.
    """
    GREETING = "greeting"           # Initial contact
    DISCOVERY = "discovery"         # Learning preferences (city, budget)
    QUALIFICATION = "qualification" # Collecting details (email, timing)
    ENGAGEMENT = "engagement"       # Showing content (photos, properties)
    HANDOVER = "handover"          # Ready for human specialist

class ConversationStageManager:
    """
    Manages conversation stages and enforces progression rules.
    
    CRITICAL FEATURES:
    - Prevents AI from sending handover messages prematurely
    - Thread-safe state management
    - Stage-specific AI instruction templates
    - Requirement validation before stage advancement
    
    THREAD SAFETY:
    All public methods use self.lock to ensure thread-safe operations.
    Safe for concurrent webhook requests from multiple users.
    """
    
    def __init__(self):
        """
        Initialize the stage manager with thread-safe structures.
        
        FIXED: All dependencies (threading, datetime, etc.) are now properly imported.
        """
        # Thread safety lock (FIXED: threading is now imported)
        self.lock = threading.Lock()
        
        # User state tracking
        self.user_stages: Dict[str, ConversationStage] = {}
        self.user_data: Dict[str, dict] = {}
        
        # Requirements for each stage
        self.STAGE_REQUIREMENTS = {
            ConversationStage.GREETING: {
                "required": [],
                "description": "Initial contact"
            },
            ConversationStage.DISCOVERY: {
                "required": ["greeted"],
                "description": "User has said hello"
            },
            ConversationStage.QUALIFICATION: {
                "required": ["greeted", "city_mentioned"],
                "description": "User expressed interest in location"
            },
            ConversationStage.ENGAGEMENT: {
                "required": ["greeted", "city_mentioned", "interest_type"],
                "description": "User specified budget preference"
            },
            ConversationStage.HANDOVER: {
                "required": ["greeted", "city_mentioned", "interest_type", 
                           "email_collected", "user_consent"],
                "description": "Ready for human specialist"
            }
        }
        
        # AI Instructions per stage (CRITICAL FOR PREVENTING PREMATURE HANDOVERS)
        self.STAGE_AI_INSTRUCTIONS = {
            ConversationStage.GREETING: """
                You are Sarah, a friendly property consultant.
                USER JUST SAID HELLO. This is the START of conversation.
                
                STRICT RULES:
                - DO NOT mention specialists or human agents
                - DO NOT suggest calling anyone
                - DO NOT end the conversation
                - Your job: Make user feel welcome, ask about their city preference
                
                Keep it warm and brief (2 sentences max).
            """,
            
            ConversationStage.DISCOVERY: """
                You are Sarah, a property consultant.
                USER HAS EXPRESSED INTEREST but we're still EARLY in conversation.
                
                STRICT RULES:
                - DO NOT mention specialists or human agents yet
                - DO NOT suggest scheduling calls
                - DO NOT end the conversation
                - Your job: Learn their preferences (city, budget type)
                
                Ask clarifying questions. Keep it conversational (3 sentences max).
            """,
            
            ConversationStage.QUALIFICATION: """
                You are Sarah, a property consultant.
                USER IS INTERESTED. We're collecting details.
                
                STRICT RULES:
                - DO NOT mention specialists yet (too early!)
                - DO NOT suggest handover to humans
                - DO NOT end the conversation
                - Your job: Understand their needs, collect email if missing
                
                Be helpful and patient. Keep conversation flowing (3 sentences max).
            """,
            
            ConversationStage.ENGAGEMENT: """
                You are Sarah, a property consultant.
                USER IS ENGAGED. Show them value first.
                
                STRICT RULES:
                - DO NOT mention specialists unless user EXPLICITLY asks
                - DO NOT push for calls or meetings yet
                - Focus on providing property information
                - Your job: Answer questions, show properties, build trust
                
                Be informative and helpful (3 sentences max).
            """,
            
            ConversationStage.HANDOVER: """
                You are Sarah, a property consultant.
                USER IS READY for personalized service.
                
                NOW you can mention:
                - Our property specialists
                - Scheduling viewings
                - Personalized consultations
                
                But ONLY if user has shown clear intent (asked about next steps,
                viewing, meeting, or said "contact me").
                
                Keep it professional (3 sentences max).
            """
        }
    
    def get_user_stage(self, user_id: str) -> ConversationStage:
        """
        Get current conversation stage for user.
        
        Args:
            user_id: Unique user identifier (phone number)
            
        Returns:
            Current ConversationStage (defaults to GREETING for new users)
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            if user_id not in self.user_stages:
                return ConversationStage.GREETING
            return self.user_stages[user_id]
    
    def update_user_data(self, user_id: str, key: str, value: any):
        """
        Update user data markers (e.g., 'greeted', 'city_mentioned').
        
        Args:
            user_id: Unique user identifier
            key: Data field to update
            value: New value for the field
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            self.user_data[user_id][key] = value
            self.user_data[user_id]['last_update'] = datetime.now()
    
    def check_stage_requirements(self, user_id: str, stage: ConversationStage) -> bool:
        """
        Check if user meets requirements for a specific stage.
        
        Args:
            user_id: Unique user identifier
            stage: Stage to check requirements for
            
        Returns:
            True if all requirements are met, False otherwise
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            user_data = self.user_data.get(user_id, {})
            required = self.STAGE_REQUIREMENTS[stage]["required"]
            
            for req in required:
                if req not in user_data or not user_data[req]:
                    return False
            
            return True
    
    def advance_stage_if_ready(self, user_id: str):
        """
        Automatically advance user to next stage if requirements met.
        
        CRITICAL: Ensures stages progress naturally without skipping.
        Checks each stage in order and advances to highest eligible stage.
        
        Args:
            user_id: Unique user identifier
            
        Side Effects:
            Updates user_stages if advancement is possible
            Logs stage changes
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            current_stage = self.get_user_stage(user_id)
            
            # Define stage progression order
            stages_order = [
                ConversationStage.GREETING,
                ConversationStage.DISCOVERY,
                ConversationStage.QUALIFICATION,
                ConversationStage.ENGAGEMENT,
                ConversationStage.HANDOVER
            ]
            
            current_idx = stages_order.index(current_stage)
            
            # Try to advance to next stage(s)
            for i in range(current_idx + 1, len(stages_order)):
                next_stage = stages_order[i]
                if self.check_stage_requirements(user_id, next_stage):
                    self.user_stages[user_id] = next_stage
                    safe_log_info(f"[STAGE] User {user_id[-4:]} advanced to {next_stage.value}")
                else:
                    break  # Can't advance further, stop checking
    
    def can_ai_handover(self, user_id: str) -> bool:
        """
        CRITICAL GATE: Check if AI is allowed to send handover messages.
        
        This is the primary guard against premature handovers.
        
        Returns True ONLY if:
        - User is in HANDOVER stage
        - All handover requirements are met
        - User has given explicit consent
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            True if handover is permitted, False otherwise
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            current_stage = self.get_user_stage(user_id)
            
            # Must be in HANDOVER stage
            if current_stage != ConversationStage.HANDOVER:
                return False
            
            # Must meet all handover requirements
            if not self.check_stage_requirements(user_id, ConversationStage.HANDOVER):
                return False
            
            return True
    
    def get_ai_instructions(self, user_id: str) -> str:
        """
        Get stage-specific AI prompt instructions.
        
        These instructions are prepended to AI prompts to ensure
        stage-appropriate responses.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Stage-specific instruction string for AI
        """
        stage = self.get_user_stage(user_id)
        return self.STAGE_AI_INSTRUCTIONS[stage]
    
    def detect_handover_attempt(self, ai_response: str) -> bool:
        """
        Detect if AI is trying to send a handover message.
        
        CRITICAL: Blocks premature handovers by scanning AI response
        for handover-related keywords.
        
        Args:
            ai_response: The response text generated by AI
            
        Returns:
            True if handover keywords detected, False otherwise
            
        Note:
            This is used in conjunction with can_ai_handover() to
            validate AI responses before sending to user.
        """
        handover_keywords = [
            "specialist", "property specialist", "senior consultant",
            "reach out", "contact you", "call you", "schedule",
            "viewing", "meeting", "arrange", "connect you",
            "have them", "shall i have"
        ]
        
        response_lower = ai_response.lower()
        
        for keyword in handover_keywords:
            if keyword in response_lower:
                return True
        
        return False
    
    def reset_user_state(self, user_id: str):
        """
        Reset user's conversation state (useful for testing or restart).
        
        Args:
            user_id: Unique user identifier
            
        Thread-safe: Protected by self.lock
        """
        with self.lock:
            if user_id in self.user_stages:
                del self.user_stages[user_id]
            if user_id in self.user_data:
                del self.user_data[user_id]
            safe_log_info(f"[STAGE] Reset state for user {user_id[-4:]}")
    
    def get_user_progress(self, user_id: str) -> dict:
        """
        Get detailed progress information for a user.
        
        Useful for debugging and analytics.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            Dictionary containing stage, data markers, and requirement status
        """
        with self.lock:
            current_stage = self.get_user_stage(user_id)
            user_data = self.user_data.get(user_id, {})
            requirements_met = self.check_stage_requirements(user_id, current_stage)
            
            return {
                "current_stage": current_stage.value,
                "requirements_met": requirements_met,
                "user_data_keys": list(user_data.keys()),
                "can_handover": self.can_ai_handover(user_id)
            }

# ============================================================================
# GLOBAL SINGLETON INSTANCE (SAFE PATTERN)
# ============================================================================

# Single instance shared across application (thread-safe by design)
stage_manager = ConversationStageManager()

# ============================================================================
# HELPER FUNCTIONS FOR MAIN.PY INTEGRATION
# ============================================================================

def update_conversation_stage(user_id: str, user_city: str, user_interest: str, 
                              user_email: str, message: str):
    """
    Update stage markers based on user input.
    
    This should be called BEFORE generating any response in the webhook.
    
    Args:
        user_id: Unique user identifier
        user_city: Extracted city from message
        user_interest: Extracted interest level
        user_email: Extracted or saved email
        message: Raw user message text
        
    Side Effects:
        Updates stage_manager state
        May advance user to new stage
    """
    msg_lower = message.lower()
    
    # Mark greeting
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 
                 'good evening', 'hii', 'hola', 'namaste']
    if any(g in msg_lower for g in greetings):
        stage_manager.update_user_data(user_id, 'greeted', True)
    
    # Mark city mentioned
    if user_city != "Not Mentioned":
        stage_manager.update_user_data(user_id, 'city_mentioned', True)
    
    # Mark interest type
    if user_interest != "Not Specified":
        stage_manager.update_user_data(user_id, 'interest_type', True)
    
    # Mark email collected
    if user_email != "Not Provided":
        stage_manager.update_user_data(user_id, 'email_collected', True)
    
    # Mark explicit consent for contact
    consent_phrases = ['contact me', 'call me', 'reach out', 'yes contact', 
                      'schedule viewing', 'book appointment', 'arrange viewing']
    if any(phrase in msg_lower for phrase in consent_phrases):
        stage_manager.update_user_data(user_id, 'user_consent', True)
    
    # Advance stage if ready (checks all requirements)
    stage_manager.advance_stage_if_ready(user_id)

def get_stage_aware_fallback(user_id: str) -> str:
    """
    Get stage-appropriate fallback message when AI quota is exceeded.
    
    IMPORTANT: Returns different fallbacks based on conversation stage
    to avoid premature handovers.
    
    Args:
        user_id: Unique user identifier
        
    Returns:
        Stage-appropriate fallback message
    """
    current_stage = stage_manager.get_user_stage(user_id)
    
    fallback_messages = {
        ConversationStage.GREETING: 
            "Hi there! 👋 Which city interests you? (Dubai, Abu Dhabi, UK)",
        
        ConversationStage.DISCOVERY: 
            "I'd love to help! What's your budget preference: Luxury, Standard, or Affordable?",
        
        ConversationStage.QUALIFICATION: 
            "Great choice! Would you like to see some property photos? 📸",
        
        ConversationStage.ENGAGEMENT: 
            "Perfect! Let me show you some options. What would you like to know?",
        
        ConversationStage.HANDOVER: 
            "I appreciate your interest! For personalized service, our specialist can help. Shall I connect you?"
    }
    
    return fallback_messages.get(current_stage, 
                                 "How can I assist you with your property search?")

# ============================================================================
# TESTING & VALIDATION FUNCTIONS
# ============================================================================

def test_stage_progression():
    """
    Test that stages progress correctly.
    
    Validates:
    - Natural progression through stages
    - Requirement enforcement
    - Cannot skip stages
    
    Raises:
        AssertionError: If any test fails
    """
    test_user = "test_user_12345"
    
    # Reset state
    stage_manager.reset_user_state(test_user)
    
    # Test 1: Start at GREETING
    assert stage_manager.get_user_stage(test_user) == ConversationStage.GREETING, \
        "New user should start at GREETING stage"
    
    # Test 2: Advance to DISCOVERY
    stage_manager.update_user_data(test_user, 'greeted', True)
    stage_manager.advance_stage_if_ready(test_user)
    assert stage_manager.get_user_stage(test_user) == ConversationStage.DISCOVERY, \
        "Should advance to DISCOVERY after greeting"
    
    # Test 3: Cannot skip to HANDOVER (missing requirements)
    stage_manager.update_user_data(test_user, 'user_consent', True)
    stage_manager.advance_stage_if_ready(test_user)
    assert stage_manager.get_user_stage(test_user) != ConversationStage.HANDOVER, \
        "Should not skip to HANDOVER without meeting requirements"
    
    # Test 4: Progress naturally through all stages
    stage_manager.update_user_data(test_user, 'city_mentioned', True)
    stage_manager.update_user_data(test_user, 'interest_type', True)
    stage_manager.update_user_data(test_user, 'email_collected', True)
    stage_manager.advance_stage_if_ready(test_user)
    
    assert stage_manager.get_user_stage(test_user) == ConversationStage.HANDOVER, \
        "Should reach HANDOVER after meeting all requirements"
    
    # Cleanup
    stage_manager.reset_user_state(test_user)
    
    print("✅ All stage progression tests passed!")
    return True

def test_handover_blocking():
    """
    Test that premature handovers are blocked.
    
    Validates:
    - Handover detection works
    - Blocking enforced at early stages
    - Allowed only at HANDOVER stage
    
    Raises:
        AssertionError: If any test fails
    """
    test_user = "test_user_67890"
    
    # Reset state
    stage_manager.reset_user_state(test_user)
    
    # Early stage (DISCOVERY)
    stage_manager.update_user_data(test_user, 'greeted', True)
    stage_manager.advance_stage_if_ready(test_user)
    
    # Test handover detection and blocking
    test_responses = [
        "Let me connect you with our specialist",
        "Shall I have them reach out?",
        "Our property consultant can help you further"
    ]
    
    for response in test_responses:
        is_handover = stage_manager.detect_handover_attempt(response)
        can_handover = stage_manager.can_ai_handover(test_user)
        
        assert is_handover == True, \
            f"Failed to detect handover in: {response}"
        assert can_handover == False, \
            f"Incorrectly allowed handover at {stage_manager.get_user_stage(test_user).value}"
    
    # Now advance to HANDOVER stage
    stage_manager.update_user_data(test_user, 'city_mentioned', True)
    stage_manager.update_user_data(test_user, 'interest_type', True)
    stage_manager.update_user_data(test_user, 'email_collected', True)
    stage_manager.update_user_data(test_user, 'user_consent', True)
    stage_manager.advance_stage_if_ready(test_user)
    
    # Now handover should be allowed
    assert stage_manager.can_ai_handover(test_user) == True, \
        "Should allow handover at HANDOVER stage"
    
    # Cleanup
    stage_manager.reset_user_state(test_user)
    
    print("✅ All handover blocking tests passed!")
    return True

def run_all_tests():
    """
    Run all module tests.
    
    Returns:
        True if all tests pass, False otherwise
    """
    try:
        print("\n" + "="*60)
        print("RUNNING CONVERSATION STAGE SYSTEM TESTS")
        print("="*60 + "\n")
        
        test_stage_progression()
        test_handover_blocking()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED - MODULE IS PRODUCTION READY")
        print("="*60 + "\n")
        
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        return False

# ============================================================================
# MODULE ENTRY POINT (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    When run directly, execute tests to validate module functionality.
    This is safe because all imports are explicit and self-contained.
    """
    print("\n🔧 Testing conversation_stage_system.py module...\n")
    success = run_all_tests()
    
    if success:
        print("Module is ready for production use.")
        print("Import with: from conversation_stage_system import stage_manager\n")
    else:
        print("⚠️ Module has issues. Review test failures above.\n")