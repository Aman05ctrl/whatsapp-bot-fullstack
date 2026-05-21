"""
Conversation Flow - State Machine Based
========================================
Predictable, deterministic conversation handler for WhatsApp Real Estate Bot.

NO MORE:
- JSON leaks (no AI generating structure)
- Infinite loops (state machine prevents)
- Repetitive questions (state tracks what's asked)
- Hallucinations (validated inputs)

Author: Built for Aman Dominator's Sarah Bot
Version: 1.0 (Production)
"""

from enum import Enum
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# STATES - Each step in the conversation
# ============================================================================
class FlowState(Enum):
    GREETING = "greeting"                          # MSG 1: Hi
    AWAITING_CITY = "awaiting_city"                # User says city
    AWAITING_PURPOSE = "awaiting_purpose"          # Investment/Personal
    AWAITING_TYPE = "awaiting_type"                # Apartment/Villa/etc
    TYPE_UNAVAILABLE = "type_unavailable"          # Type not in inventory
    AWAITING_BUDGET = "awaiting_budget"            # Budget collection
    AWAITING_EMAIL = "awaiting_email"              # Email collection
    SHOWING_PROPERTY = "showing_property"          # Property shown
    AWAITING_FEEDBACK = "awaiting_feedback"        # Did you like?
    AWAITING_FALLBACK_OFFER = "awaiting_fallback_offer"  # Yes/no to "AED X options" after BUDGET_TOO_HIGH
    SHOWING_ALTERNATIVES = "showing_alternatives"  # Showing ±30k options
    AWAITING_BUDGET_INCREASE = "awaiting_budget_increase"  # Increase budget?
    AWAITING_NEW_BUDGET = "awaiting_new_budget"    # New higher budget
    AWAITING_MEETING_DATETIME = "awaiting_meeting_datetime"  # When to meet
    MEETING_CONFIRMED = "meeting_confirmed"        # Meeting booked
    CONSULTANT_HANDOVER = "consultant_handover"    # Specialist will help
    RETURNING_USER_CONFIRM = "returning_user_confirm"  # > 7 days — confirm resume


# ============================================================================
# RESPONSE - What bot returns after handling a message
# ============================================================================
@dataclass
class FlowResponse:
    """What the flow returns to main.py"""
    text: Optional[str] = None
    action: str = "send_text"  # send_text | send_property | schedule_meeting | handover
    data: Dict = field(default_factory=dict)
    next_state: Optional[FlowState] = None


# ============================================================================
# CONVERSATION FLOW - The State Machine
# ============================================================================
class ConversationFlow:
    """
    Manages a single user's conversation through deterministic states.
    
    Usage:
        flow = ConversationFlow(user_id="123", user_name="Aman")
        response = flow.handle_message("Hello", available_properties=[...])
        # response.text contains what bot should say
        # response.action tells main.py what to do
    """
    
    def __init__(self, user_id: str, user_name: str = ""):
        self.user_id = user_id
        self.user_name = user_name or "there"
        self.state = FlowState.GREETING
        self.data = {
            'city': None,
            'purpose': None,
            'prop_type': None,
            'requested_type': None,  # What user originally asked (e.g., villa)
            'budget': None,
            'email': None,
            'budget_increased': False,
            'shown_property': None,
            'meeting_date': None,
            'meeting_time': None,
        }
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    def handle_message(
        self,
        message: str,
        available_properties: List[Dict],
        gemini_call_fn=None,
        correlation_id: str = "N/A"
    ) -> FlowResponse:
        """
        Route message to appropriate state handler.
        
        If gemini_call_fn is provided, uses Gemini-powered intent classification
        for adaptive understanding (handles corrections, restarts, smalltalk, etc.)
        BEFORE falling back to keyword-based handlers. If gemini_call_fn is None,
        falls back to legacy state-only routing.
        """
        message = (message or "").strip()
        
        # ─── INTENT CLASSIFICATION (NEW) ───
        intent_data = None
        if gemini_call_fn is not None:
            try:
                from intent_classifier import classify_intent
                inventory_types = list(self._extract_inventory_types(available_properties))
                inventory_cities = list(self._extract_inventory_cities(available_properties))
                intent_data = classify_intent(
                    message=message,
                    state=self.state.value,
                    captured=self.data,
                    available_types=inventory_types,
                    available_cities=inventory_cities,
                    gemini_call_fn=gemini_call_fn,
                    correlation_id=correlation_id,
                )
            except Exception as e:
                logger.warning(f"[FLOW] Intent classifier failed: {e} | {correlation_id}")
                intent_data = None
        
        # ─── GLOBAL INTENT HANDLING (works in ANY state) ───
        if intent_data and intent_data.get("confidence", 0) >= 0.7:
            # User wants to start over with new criteria — handle globally
            if intent_data.get("wants_restart"):
                restart_response = self._handle_intent_restart(
                    intent_data, available_properties
                )
                if restart_response:
                    if restart_response.next_state:
                        logger.info(
                            f"[FLOW] {self.user_id[-4:]}: {self.state.value} → "
                            f"{restart_response.next_state.value} (RESTART)"
                        )
                        self.state = restart_response.next_state
                    return restart_response
            
            # Apply field corrections globally — works in any state
            if intent_data.get("intent") == "correct_field":
                correction_response = self._handle_intent_correction(
                    intent_data, available_properties
                )
                if correction_response:
                    return correction_response
        
        # ─── STATE DISPATCH (existing) ───
        handlers = {
            FlowState.GREETING: self._handle_greeting,
            FlowState.AWAITING_CITY: self._handle_city,
            FlowState.AWAITING_PURPOSE: self._handle_purpose,
            FlowState.AWAITING_TYPE: self._handle_type,
            FlowState.TYPE_UNAVAILABLE: self._handle_type_redirect,
            FlowState.AWAITING_BUDGET: self._handle_budget,
            FlowState.AWAITING_EMAIL: self._handle_email,
            FlowState.SHOWING_PROPERTY: self._handle_after_property,
            FlowState.AWAITING_FEEDBACK: self._handle_feedback,
            FlowState.AWAITING_FALLBACK_OFFER: self._handle_fallback_offer,
            FlowState.SHOWING_ALTERNATIVES: self._handle_alternative_feedback,
            FlowState.AWAITING_BUDGET_INCREASE: self._handle_budget_increase,
            FlowState.AWAITING_NEW_BUDGET: self._handle_new_budget,
            FlowState.AWAITING_MEETING_DATETIME: self._handle_meeting_datetime,
            FlowState.MEETING_CONFIRMED: self._handle_post_meeting,
            FlowState.CONSULTANT_HANDOVER: self._handle_post_handover,
            FlowState.RETURNING_USER_CONFIRM: self._handle_returning_user_confirm,
        }
        
        handler = handlers.get(self.state, self._handle_fallback)
        try:
            response = handler(message, available_properties)
            if response.next_state:
                logger.info(f"[FLOW] {self.user_id[-4:]}: {self.state.value} → {response.next_state.value}")
                self.state = response.next_state
            return response
        except Exception as e:
            logger.error(f"[FLOW] Handler error: {e}")
            return self._handle_fallback(message, available_properties)
    
    # ========================================================================
    # STATE HANDLERS
    # ========================================================================
    
    def _handle_greeting(self, message: str, properties: List[Dict]) -> FlowResponse:
        """MSG 1: User just said hi → Greet + ask city"""
        from ai_prompts import GREETING_TEMPLATE
        
        text = GREETING_TEMPLATE.format(name=self.user_name)
        return FlowResponse(
            text=text,
            action="send_text",
            next_state=FlowState.AWAITING_CITY
        )
    
    def _handle_returning_user_confirm(
        self, message: str, properties: List[Dict]
    ) -> FlowResponse:
        """
        User returning after >7 days. They've been asked if they want to
        continue with previous criteria or start fresh.
        """
        intent = self._detect_yes_no(message)
        
        if intent == "yes":
            # Resume with previous criteria — jump to next missing field
            logger.info(f"[FLOW] {self.user_id[-4:]}: resume confirmed → continuing")
            
            if not self.data.get('budget'):
                return FlowResponse(
                    text=("Great! Let's continue. 🚀\n\n"
                          "What budget range are you working with? Please share in AED.\n"
                          "(e.g., 100,000 AED or 200,000 AED) 💰"),
                    action="send_text",
                    next_state=FlowState.AWAITING_BUDGET,
                )
            if not self.data.get('email'):
                return FlowResponse(
                    text=("Great! Let's continue. 🚀\n\n"
                          "Where should I send you the detailed brochures? "
                          "Please share your email address. 📧"),
                    action="send_text",
                    next_state=FlowState.AWAITING_EMAIL,
                )
            # Everything is in place — go to email handler which shows the property
            return FlowResponse(
                text="Great! Let me find the perfect property for you. 🔍",
                action="send_text",
                next_state=FlowState.AWAITING_EMAIL,
            )
        
        if intent == "no":
            # Fresh start — wipe everything except identity
            logger.info(f"[FLOW] {self.user_id[-4:]}: resume declined → fresh start")
            self.data.clear()
            return FlowResponse(
                text=("No problem! Let's start fresh. 🌟\n\n"
                      "Which city interests you for your property search? 🏙️"),
                action="send_text",
                next_state=FlowState.AWAITING_CITY,
            )
        
        # Unclear answer
        return FlowResponse(
            text=("Just to confirm — would you like to continue your previous search? 😊\n\n"
                  "Reply *yes* to continue, or *no* to start fresh."),
            action="send_text",
            next_state=FlowState.RETURNING_USER_CONFIRM,
        )
    
    def _handle_city(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User responding with city → Save + ask purpose. Database-driven."""
        from ai_prompts import CITY_RECEIVED_TEMPLATE, INVALID_CITY_TEMPLATE

        # Build city set from ALL parts of inventory location strings
        inventory_cities = self._extract_inventory_cities(properties)
        
        # Match user's message against actual inventory cities
        # Sort by length DESC so multi-word cities ("New Delhi") win over single-word ("Delhi")
        candidates = sorted(inventory_cities, key=len, reverse=True)
        city = self._extract_city(message, candidates)
        
        if not city:
            # Show REAL inventory cities — whatever the dealer has uploaded
            display = sorted(inventory_cities)[:5] if inventory_cities else []
            cities_text = ", ".join(display) if display else "various locations"
            return FlowResponse(
                text=INVALID_CITY_TEMPLATE.format(cities=cities_text),
                action="send_text",
                next_state=FlowState.AWAITING_CITY
            )
        
        self.data['city'] = city
        return FlowResponse(
            text=CITY_RECEIVED_TEMPLATE.format(city=city),
            action="send_text",
            next_state=FlowState.AWAITING_PURPOSE
        )
    
    def _handle_purpose(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User responding with purpose → Save + ask type"""
        from ai_prompts import PURPOSE_RECEIVED_TEMPLATE, INVALID_PURPOSE_TEMPLATE
        
        correction = self._detect_correction(message, properties)
        if correction:
            return correction

        purpose = self._extract_purpose(message)
        
        if not purpose:
            return FlowResponse(
                text=INVALID_PURPOSE_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_PURPOSE
            )
        
        self.data['purpose'] = purpose
        
        # Get available types from inventory
        available_types = self._get_available_types(properties)
        
        return FlowResponse(
            text=PURPOSE_RECEIVED_TEMPLATE.format(
                purpose=purpose,
                types=", ".join(available_types)
            ),
            action="send_text",
            next_state=FlowState.AWAITING_TYPE
        )
    
    def _handle_type(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User responding with type → Save + ask budget. Database-driven."""
        from ai_prompts import TYPE_AVAILABLE_TEMPLATE, TYPE_UNAVAILABLE_TEMPLATE, INVALID_TYPE_TEMPLATE

        correction = self._detect_correction(message, properties)
        if correction:
            return correction
        
        # Pull all unique types from inventory (whatever the dealer uploaded)
        inventory_types = self._extract_inventory_types(properties)
        
        # Try to extract any type the user mentioned
        requested_type = self._extract_property_type_dynamic(message, inventory_types)
        
        if not requested_type:
            # Couldn't parse anything — show what's actually available
            return FlowResponse(
                text=INVALID_TYPE_TEMPLATE.format(types=", ".join(sorted(inventory_types))),
                action="send_text",
                next_state=FlowState.AWAITING_TYPE
            )
        
        # Check if requested type exists in inventory (case-insensitive)
        types_lower = {t.lower() for t in inventory_types}
        if requested_type.lower() in types_lower:
            self.data['prop_type'] = requested_type
            return FlowResponse(
                text=TYPE_AVAILABLE_TEMPLATE.format(prop_type=requested_type),
                action="send_text",
                next_state=FlowState.AWAITING_BUDGET
            )
        
        # Type not in inventory — diplomatic redirect to what IS available
        self.data['requested_type_unavailable'] = requested_type
        return FlowResponse(
            text=TYPE_UNAVAILABLE_TEMPLATE.format(
                requested=requested_type,
                available_types=", ".join(sorted(inventory_types))
            ),
            action="send_text",
            next_state=FlowState.TYPE_UNAVAILABLE
        )
    
    def _handle_type_redirect(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User chose alternative type after we said original was unavailable"""
        from ai_prompts import TYPE_AVAILABLE_TEMPLATE, INVALID_TYPE_TEMPLATE

        prop_type = self._extract_property_type(message)
        available_types = self._get_available_types(properties)
        available_types_lower = [t.lower() for t in available_types]
        
        if not prop_type or prop_type.lower() not in available_types_lower:
            return FlowResponse(
                text=INVALID_TYPE_TEMPLATE.format(types=", ".join(available_types)),
                action="send_text",
                next_state=FlowState.TYPE_UNAVAILABLE
            )
        
        self.data['prop_type'] = prop_type
        return FlowResponse(
            text=TYPE_AVAILABLE_TEMPLATE.format(prop_type=prop_type),
            action="send_text",
            next_state=FlowState.AWAITING_BUDGET
        )
    
    def _handle_budget(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User provides budget → Save + ask email. Also handles mid-flow type changes."""
        from ai_prompts import BUDGET_RECEIVED_TEMPLATE, INVALID_BUDGET_TEMPLATE

        correction = self._detect_correction(message, properties)
        if correction:
            return correction
        
        # Detect mid-flow type change (e.g., "no I'll go with commercial",
        # or "no I don't want apartment, give me commercial").
        # Find ALL types mentioned and pick the first one that's DIFFERENT from current.
        all_types_in_msg = self._extract_all_property_types(message)
        new_type = None
        if all_types_in_msg:
            available_types = self._get_available_types(properties)
            available_lower = [t.lower() for t in available_types]
            current_type = (self.data.get('prop_type') or '').lower()
            
            for _, t in all_types_in_msg:
                if t.lower() != current_type and t.lower() in available_lower:
                    new_type = t
                    break
        
        if new_type:
                self.data['prop_type'] = new_type
                logger.info(f"[FLOW] {self.user_id[-4:]}: type changed mid-flow → {new_type}")
                
                # If they ALSO gave a budget number in same message, accept both
                budget = self._extract_budget(message)
                if budget and budget >= 10000:
                    self.data['budget'] = budget
                    return FlowResponse(
                        text=(f"Got it — switching to *{new_type}*! 🏠\n\n"
                              + BUDGET_RECEIVED_TEMPLATE.format(budget=f"{budget:,}")),
                        action="send_text",
                        next_state=FlowState.AWAITING_EMAIL
                    )
                # Just the type change — re-ask budget gracefully
                return FlowResponse(
                    text=(f"No problem — switching to *{new_type}*! 🏠\n\n"
                          f"What budget range are you working with? Please share in AED.\n"
                          f"(e.g., 100,000 AED or 200,000 AED) 💰"),
                    action="send_text",
                    next_state=FlowState.AWAITING_BUDGET
                )
        
        budget = self._extract_budget(message)
        
        if not budget or budget < 10000:
            return FlowResponse(
                text=INVALID_BUDGET_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_BUDGET
            )
        
        self.data['budget'] = budget
        return FlowResponse(
            text=BUDGET_RECEIVED_TEMPLATE.format(budget=f"{budget:,}"),
            action="send_text",
            next_state=FlowState.AWAITING_EMAIL
        )
    
    def _handle_email(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User provides email → Smart match with diplomatic responses"""
        from ai_prompts import EMAIL_RECEIVED_TEMPLATE, INVALID_EMAIL_TEMPLATE
        from smart_property_matcher import SmartPropertyMatcher, MatchResult

        correction = self._detect_correction(message, properties)
        if correction:
            return correction
        
        email = self._extract_email(message)
        
        if not email:
            return FlowResponse(
                text=INVALID_EMAIL_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_EMAIL
            )
        
        self.data['email'] = email
        
        # Use smart matcher for intelligent property finding
        matcher = SmartPropertyMatcher(properties)
        result, best_property, context = matcher.find_best_match(
            prop_type=self.data['prop_type'],
            city=self.data['city'],
            budget=self.data['budget'],
            margin=30000
        )
        
        # Handle each match result diplomatically
        if result == MatchResult.PERFECT_MATCH and best_property:
            # ✅ Found within ±30k margin
            self.data['shown_property'] = best_property
            return FlowResponse(
                text=EMAIL_RECEIVED_TEMPLATE.format(
                    email=email,
                    budget=f"{self.data['budget']:,}"
                ),
                action="send_property",
                data={'property': best_property},
                next_state=FlowState.SHOWING_PROPERTY
            )
        
        elif result == MatchResult.BUDGET_TOO_HIGH:
            # User has more money than our inventory - "sold out luxury" narrative
            diplomatic_msg = matcher.get_diplomatic_response(
                result, context, user_name=self.user_name
            )
            # Pre-stage the highest-priced available property for "yes" response
            inv_props = context.get('inventory_stats', {}).get('properties', [])
            self.data['fallback_property'] = (
                max(inv_props, key=lambda x: x[0])[1] if inv_props else None
            )
            return FlowResponse(
                text=diplomatic_msg,
                action="send_text",
                next_state=FlowState.AWAITING_FALLBACK_OFFER
            )
        
        elif result == MatchResult.BUDGET_TOO_LOW:
            # Budget too low - suggest minimum or wait list
            diplomatic_msg = matcher.get_diplomatic_response(
                result, context, user_name=self.user_name
            )
            return FlowResponse(
                text=diplomatic_msg,
                action="send_text",
                next_state=FlowState.AWAITING_BUDGET_INCREASE
            )
        
        elif result in (MatchResult.NO_TYPE_MATCH, MatchResult.NO_CITY_MATCH, 
                       MatchResult.INVENTORY_EMPTY):
            # No suitable property - graceful handover
            diplomatic_msg = matcher.get_diplomatic_response(
                result, context, user_name=self.user_name
            )
            return FlowResponse(
                text=diplomatic_msg,
                action="handover",
                next_state=FlowState.CONSULTANT_HANDOVER
            )
        
        # Fallback: should never reach here
        return FlowResponse(
            text=("Thank you for sharing your details! 📧\n\n"
                  "Our consultant will personally reach out to find the "
                  "perfect property for you within 24 hours. 🤝"),
            action="handover",
            next_state=FlowState.CONSULTANT_HANDOVER
        )
    
    def _handle_after_property(self, message: str, properties: List[Dict]) -> FlowResponse:
        """Right after property shown, user response = feedback"""

        # Treat this same as feedback
        return self._handle_feedback(message, properties)
    
    def _handle_feedback(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User responds to property → Like or dislike"""
        from ai_prompts import (LIKED_PROPERTY_TEMPLATE, DISLIKED_PROPERTY_TEMPLATE,
                                UNCLEAR_FEEDBACK_TEMPLATE)
        from property_handler import find_alternative_properties

        intent = self._detect_yes_no(message)
        
        if intent == "yes":
            # User likes → Ask meeting date/time
            title = self._get_gender_title()
            return FlowResponse(
                text=LIKED_PROPERTY_TEMPLATE.format(title=title),
                action="send_text",
                next_state=FlowState.AWAITING_MEETING_DATETIME
            )
        
        elif intent == "no":
            # User doesn't like → Show alternatives ±30k
            shown_id = self.data.get('shown_property', {}).get('id', None)
            alternatives = find_alternative_properties(
                properties=properties,
                prop_type=self.data['prop_type'],
                city=self.data['city'],
                budget=self.data['budget'],
                margin=30000,
                exclude_id=shown_id
            )
            
            if not alternatives:
                # No alternatives - ask to increase budget
                return FlowResponse(
                    text=("I understand! Would you be open to slightly increasing "
                          "your budget? Sometimes a small adjustment opens up "
                          "premium options that match what you're looking for.\n\n"
                          "Please reply *yes* if you'd like to explore higher options, "
                          "or *no* to connect with our consultant."),
                    action="send_text",
                    next_state=FlowState.AWAITING_BUDGET_INCREASE
                )
            
            # Format alternatives list
            alt_text = self._format_alternatives_list(alternatives)
            return FlowResponse(
                text=DISLIKED_PROPERTY_TEMPLATE.format(
                    budget_min=f"{self.data['budget'] - 30000:,}",
                    budget_max=f"{self.data['budget'] + 30000:,}",
                    alternatives=alt_text
                ),
                action="send_text",
                data={'alternatives': alternatives},
                next_state=FlowState.SHOWING_ALTERNATIVES
            )
        
        else:
            # Unclear response
            return FlowResponse(
                text=UNCLEAR_FEEDBACK_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_FEEDBACK
            )

    def _handle_fallback_offer(self, message: str, properties: List[Dict]) -> FlowResponse:
        """
        User responding to 'we have options at AED X' offer after BUDGET_TOO_HIGH.
        YES → actually send the pre-staged property card.
        NO  → hand over to consultant.
        """
        intent = self._detect_yes_no(message)

        if intent == "yes":
            fallback_prop = self.data.get('fallback_property')

            # Defensive: re-resolve if cache lost (e.g., process restart)
            if not fallback_prop:
                from smart_property_matcher import SmartPropertyMatcher
                matcher = SmartPropertyMatcher(properties)
                stats = matcher.get_inventory_stats(
                    prop_type=self.data['prop_type'],
                    city=self.data['city']
                )
                inv_props = stats.get('properties', [])
                if inv_props:
                    fallback_prop = max(inv_props, key=lambda x: x[0])[1]

            if fallback_prop:
                self.data['shown_property'] = fallback_prop
                return FlowResponse(
                    text="Wonderful! Here's a fantastic option for you 🏠",
                    action="send_property",
                    data={'property': fallback_prop},
                    next_state=FlowState.AWAITING_FEEDBACK
                )

            # Nothing left in inventory → handover
            return FlowResponse(
                text=("Let me connect you with our consultant who'll personally "
                      "share the best matches for you. They'll reach out shortly! 🤝"),
                action="handover",
                next_state=FlowState.CONSULTANT_HANDOVER
            )

        if intent == "no":
            return FlowResponse(
                text=("Absolutely! I'll personally notify you via email the moment "
                      "new luxury listings matching your budget arrive. 💎\n\n"
                      "Our senior consultant will also reach out with off-market "
                      "premium options. Thank you! 🤝"),
                action="handover",
                next_state=FlowState.CONSULTANT_HANDOVER
            )

        # Unclear
        return FlowResponse(
            text=("Just to confirm — would you like to take a look at the "
                  "available options? Reply *yes* to view them, or *no* if "
                  "you'd prefer to wait for new luxury listings. 😊"),
            action="send_text",
            next_state=FlowState.AWAITING_FALLBACK_OFFER
        )    
    
    def _handle_alternative_feedback(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User responding to alternatives - picked one or wants budget increase"""
        from ai_prompts import LIKED_PROPERTY_TEMPLATE
        
        # Check if they picked a number (1, 2, 3)
        match = re.search(r'\b([1-3])\b', message)
        if match:
            idx = int(match.group(1)) - 1
            from property_handler import find_alternative_properties
            
            alternatives = find_alternative_properties(
                properties=properties,
                prop_type=self.data['prop_type'],
                city=self.data['city'],
                budget=self.data['budget'],
                margin=30000,
                exclude_id=self.data.get('shown_property', {}).get('id', None)
            )
            
            if 0 <= idx < len(alternatives):
                selected = alternatives[idx]
                self.data['shown_property'] = selected
                
                return FlowResponse(
                    text=f"Great choice! Here are the details for *{selected.get('name')}* 🏠",
                    action="send_property",
                    data={'property': selected},
                    next_state=FlowState.AWAITING_FEEDBACK
                )
        
        # User said no/unclear → ask to increase budget
        intent = self._detect_yes_no(message)
        if intent == "no":
            return FlowResponse(
                text=("No problem! Would you consider slightly increasing your "
                      "budget? This often unlocks great options.\n\n"
                      "Reply *yes* to explore higher options, or *no* to connect "
                      "with our consultant for personalized guidance."),
                action="send_text",
                next_state=FlowState.AWAITING_BUDGET_INCREASE
            )
        
        # Default: ask them to pick number or move on
        return FlowResponse(
            text=("Please reply with the option number (1, 2, or 3) you'd like "
                  "to see in detail, or say *none* to explore other options."),
            action="send_text",
            next_state=FlowState.SHOWING_ALTERNATIVES
        )
    
    def _handle_budget_increase(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User decides if they want to increase budget"""

        correction = self._detect_correction(message, properties)
        if correction:
            return correction

        intent = self._detect_yes_no(message)
        
        if intent == "yes":
            return FlowResponse(
                text=("Wonderful! What's your new budget range?\n"
                      "Please share in AED (e.g., 150,000 AED or 200,000 AED) 💰"),
                action="send_text",
                next_state=FlowState.AWAITING_NEW_BUDGET
            )
        else:
            # Connect to consultant
            return FlowResponse(
                text=("Absolutely! Our property consultant will personally reach "
                      "out to understand your exact needs and find the perfect "
                      "match for you. They'll contact you at your email shortly. 📞\n\n"
                      "Thank you for your time! 😊"),
                action="handover",
                next_state=FlowState.CONSULTANT_HANDOVER
            )
    
    def _handle_new_budget(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User provides increased budget - use smart matcher"""
        from smart_property_matcher import SmartPropertyMatcher, MatchResult
        from ai_prompts import INVALID_BUDGET_TEMPLATE
        
        correction = self._detect_correction(message, properties)
        if correction:
            return correction

        new_budget = self._extract_budget(message)
        if not new_budget or new_budget < 10000:
            return FlowResponse(
                text=INVALID_BUDGET_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_NEW_BUDGET
            )
        
        # Validate it's actually higher than previous
        prev_budget = self.data['budget']
        if new_budget <= prev_budget:
            return FlowResponse(
                text=(f"Please share a higher budget than your previous one "
                      f"(AED {prev_budget:,}).\n\nFor example: AED {prev_budget + 50000:,} 💰"),
                action="send_text",
                next_state=FlowState.AWAITING_NEW_BUDGET
            )
        
        self.data['budget'] = new_budget
        self.data['budget_increased'] = True
        
        # Use smart matcher
        matcher = SmartPropertyMatcher(properties)
        result, best_property, context = matcher.find_best_match(
            prop_type=self.data['prop_type'],
            city=self.data['city'],
            budget=new_budget,
            margin=30000
        )
        
        if result == MatchResult.PERFECT_MATCH and best_property:
            self.data['shown_property'] = best_property
            return FlowResponse(
                text=(f"Excellent! At AED {new_budget:,}, here's a fantastic option "
                      f"that matches your criteria 🏠"),
                action="send_property",
                data={'property': best_property},
                next_state=FlowState.AWAITING_FEEDBACK
            )
        
        # If still budget too high - diplomatic response
        if result == MatchResult.BUDGET_TOO_HIGH:
            diplomatic_msg = matcher.get_diplomatic_response(
                result, context, user_name=self.user_name
            )
            inv_props = context.get('inventory_stats', {}).get('properties', [])
            self.data['fallback_property'] = (
                max(inv_props, key=lambda x: x[0])[1] if inv_props else None
            )
            return FlowResponse(
                text=diplomatic_msg,
                action="send_text",
                next_state=FlowState.AWAITING_FALLBACK_OFFER
            )
        
        # Anything else - handover
        return FlowResponse(
            text=("Let me connect you with our consultant who has access to "
                  "off-market premium properties. They'll personally reach out "
                  "with options matching your budget within 24 hours! 🤝"),
            action="handover",
            next_state=FlowState.CONSULTANT_HANDOVER
        )
    
    def _handle_meeting_datetime(self, message: str, properties: List[Dict]) -> FlowResponse:
        """User provides date and time for meeting"""
        from ai_prompts import (MEETING_CONFIRMED_TEMPLATE, INVALID_DATETIME_TEMPLATE,
                                YEAR_CONFIRMATION_TEMPLATE)
        
        correction = self._detect_correction(message, properties)
        if correction:
            return correction

        date_str, time_str, needs_year_confirm = self._extract_datetime(message)
        
        if needs_year_confirm:
            return FlowResponse(
                text=YEAR_CONFIRMATION_TEMPLATE.format(date=date_str),
                action="send_text",
                next_state=FlowState.AWAITING_MEETING_DATETIME
            )
        
        if not date_str or not time_str:
            return FlowResponse(
                text=INVALID_DATETIME_TEMPLATE,
                action="send_text",
                next_state=FlowState.AWAITING_MEETING_DATETIME
            )
        
        self.data['meeting_date'] = date_str
        self.data['meeting_time'] = time_str
        
        return FlowResponse(
            text=MEETING_CONFIRMED_TEMPLATE.format(date=date_str, time=time_str),
            action="schedule_meeting",
            data={
                'date': date_str,
                'time': time_str,
                'property': self.data.get('shown_property'),
                'email': self.data.get('email'),
                'budget': self.data.get('budget'),
            },
            next_state=FlowState.MEETING_CONFIRMED
        )
    
    def _handle_post_meeting(self, message: str, properties: List[Dict]) -> FlowResponse:
        """After meeting confirmed - just acknowledge"""

        return FlowResponse(
            text=("Looking forward to our call! If you have any questions before "
                  "the meeting, feel free to reach out. Have a great day! 😊"),
            action="send_text",
            next_state=FlowState.MEETING_CONFIRMED
        )
    
    def _handle_post_handover(self, message: str, properties: List[Dict]) -> FlowResponse:
        """After consultant handover - acknowledge"""

        return FlowResponse(
            text=("Our consultant will be in touch soon. Thank you for your "
                  "patience! If you need anything urgent, please call our "
                  "support line. 📞"),
            action="send_text",
            next_state=FlowState.CONSULTANT_HANDOVER
        )
    
    def _handle_fallback(self, message: str, properties: List[Dict]) -> FlowResponse:
        """Catch-all for unexpected states - DOESN'T reset progress"""

        # If we have property shown, stay in feedback
        if self.data.get('shown_property'):
            return FlowResponse(
                text=("Could you let me know if you're interested?\n\n"
                      "• Reply *yes* to schedule a viewing\n"
                      "• Reply *no* to see other options"),
                action="send_text",
                next_state=FlowState.AWAITING_FEEDBACK
            )
        # If we have email but no property yet
        if self.data.get('email'):
            return FlowResponse(
                text="Could you share your preferences again? I'm here to help! 😊",
                action="send_text",
                next_state=self.state
            )
        # Only reset if truly nothing collected
        return FlowResponse(
            text="I'd love to help! Which city interests you for your property search? 🏙️",
            action="send_text",
            next_state=FlowState.AWAITING_CITY
        )
    
    def _handle_intent_restart(
        self, intent_data: Dict, properties: List[Dict]
    ) -> Optional[FlowResponse]:
        """
        User wants to restart search with new criteria.
        - PRESERVES every field the user explicitly mentioned in the restart message
        - RESETS only downstream state (shown property, email if criteria changed)
        - JUMPS to the next REALLY missing field (skips anything user just gave)
        - For ambiguous restarts (no fields given), confirms with the user first
        """
        fields = intent_data.get("fields", {})
        new_city = fields.get("city")
        new_type = fields.get("prop_type")
        new_budget = fields.get("budget")
        new_purpose = fields.get("purpose")
        
        # ─── If user gave ZERO fields, confirm what they want to restart ───
        if not any([new_city, new_type, new_budget, new_purpose]):
            # Build budget display string OUTSIDE the f-string (cleaner, parses correctly)
            current_budget = self.data.get('budget')
            budget_display = f"AED {current_budget:,}" if current_budget else "not set"
            current_city = self.data.get('city', 'not set')
            current_type = self.data.get('prop_type', 'not set')
            
            return FlowResponse(
                text=(
                    f"No problem! What would you like to change?\n\n"
                    f"Currently I have:\n"
                    f"📍 City: *{current_city}*\n"
                    f"🏠 Type: *{current_type}*\n"
                    f"💰 Budget: *{budget_display}*\n\n"
                    f"Just tell me what to update — for example "
                    f"\"change to Mumbai\" or \"new budget 200000\". 😊"
                ),
                action="send_text",
                next_state=self.state,  # stay in current state
            )
        
        # ─── Apply ONLY the fields the user explicitly mentioned ───
        # Keep existing values for anything the user didn't re-specify
        applied_msgs = []
        if new_city:
            self.data["city"] = new_city
            applied_msgs.append(f"city: *{new_city}*")
        if new_purpose:
            self.data["interest"] = new_purpose
            applied_msgs.append(f"purpose: *{new_purpose}*")
        if new_type:
            self.data["prop_type"] = new_type
            applied_msgs.append(f"type: *{new_type}*")
        if new_budget:
            self.data["budget"] = new_budget
            applied_msgs.append(f"budget: *AED {new_budget:,}*")
        
        # ─── Reset only downstream state that's now stale ───
        # If criteria changed, the previously shown property no longer applies
        self.data.pop("shown_property", None)
        self.data.pop("fallback_property", None)
        # If budget changed, email might still be valid (same user) — keep it
        # If criteria fundamentally changed, also reset email so we re-confirm
        if new_city or new_type:
            # Major change → reset budget+email so we re-qualify the lead
            if not new_budget:  # only reset budget if user didn't provide a new one
                self.data.pop("budget", None)
            self.data.pop("email", None)
        
        # ─── Decide jump target: next REALLY missing field ───
        if not self.data.get("city"):
            next_state = FlowState.AWAITING_CITY
            prompt = "Which city interests you? 🏙️"
        elif not self.data.get("interest"):
            next_state = FlowState.AWAITING_PURPOSE
            prompt = "Is this for *investment* or *personal use*?"
        elif not self.data.get("prop_type"):
            next_state = FlowState.AWAITING_TYPE
            prompt = "What type of property are you looking for?"
        elif not self.data.get("budget"):
            next_state = FlowState.AWAITING_BUDGET
            prompt = ("What budget range are you working with? Please share in AED.\n"
                      "(e.g., 100,000 AED or 200,000 AED) 💰")
        elif not self.data.get("email"):
            next_state = FlowState.AWAITING_EMAIL
            prompt = ("Where should I send you the detailed brochures? "
                      "Please share your email address. 📧")
        else:
            # Everything filled — jump straight to showing the property
            next_state = FlowState.AWAITING_EMAIL  # email handler shows the property
            prompt = "Let me find you the perfect match... 🔍"
        
        ack = f"Got it — fresh search with {', '.join(applied_msgs)}! 🔄"
        return FlowResponse(
            text=f"{ack}\n\n{prompt}",
            action="send_text",
            next_state=next_state,
        )
    
    def _handle_intent_correction(
        self, intent_data: Dict, properties: List[Dict]
    ) -> Optional[FlowResponse]:
        """
        User changed one or more fields. Apply them, then advance to the
        NEXT missing field (smart progression — same as restart handler).
        """
        fields = intent_data.get("fields", {})
        applied_msgs = []
        
        if "city" in fields and fields["city"] and self.data.get("city") != fields["city"]:
            self.data["city"] = fields["city"]
            applied_msgs.append(f"city: *{fields['city']}* 🌆")
        if "prop_type" in fields and fields["prop_type"] and self.data.get("prop_type") != fields["prop_type"]:
            self.data["prop_type"] = fields["prop_type"]
            applied_msgs.append(f"type: *{fields['prop_type']}* 🏠")
        if "budget" in fields and fields["budget"] and self.data.get("budget") != fields["budget"]:
            self.data["budget"] = fields["budget"]
            applied_msgs.append(f"budget: *AED {fields['budget']:,}* 💰")
        if "purpose" in fields and fields["purpose"] and self.data.get("interest") != fields["purpose"]:
            self.data["interest"] = fields["purpose"]
            applied_msgs.append(f"purpose: *{fields['purpose']}*")
        
        if not applied_msgs:
            return None  # Nothing to apply, fall through to normal handler
        
        # Advance to next REALLY missing field — same logic as restart handler
        if not self.data.get("city"):
            next_state = FlowState.AWAITING_CITY
            prompt = "Which city interests you? 🏙️"
        elif not self.data.get("interest"):
            next_state = FlowState.AWAITING_PURPOSE
            prompt = "Is this for *investment* or *personal use*?"
        elif not self.data.get("prop_type"):
            next_state = FlowState.AWAITING_TYPE
            prompt = "What type of property are you looking for?"
        elif not self.data.get("budget"):
            next_state = FlowState.AWAITING_BUDGET
            prompt = ("What budget range are you working with? Please share in AED.\n"
                      "(e.g., 100,000 AED or 200,000 AED) 💰")
        elif not self.data.get("email"):
            next_state = FlowState.AWAITING_EMAIL
            prompt = ("Where should I send you the detailed brochures? "
                      "Please share your email address. 📧")
        else:
            # All core fields collected — keep current state (likely feedback/scheduling)
            next_state = self.state
            prompt = "Let me know how I can help! 😊"
        
        logger.info(f"[FLOW] {self.user_id[-4:]}: correction → {next_state.value}")
        
        return FlowResponse(
            text=f"Got it — updated {', '.join(applied_msgs)}.\n\n{prompt}",
            action="send_text",
            next_state=next_state,
        )

    def _detect_correction(self, message: str, properties: List[Dict]) -> Optional[FlowResponse]:
        """
        Detect mid-flow corrections to ANY previously-captured field
        (city, prop_type, budget, purpose). Returns a FlowResponse confirming
        the correction if detected, or None if no correction.
        
        Called at the top of every handler so the bot stays adaptive throughout
        the flow — user can correct ANY field at ANY time.
        """
        # ─── 1. Budget correction ───
        # Trigger only on explicit correction signals + a number that's clearly a budget
        correction_signals = ['change', 'changed', 'instead', 'actually', 
                              'wait', 'no my', 'not my', 'mind', 'rather',
                              'update', 'updated', 'switch', 'revise', 'revised']
        msg_lower = message.lower()
        has_correction_signal = any(sig in msg_lower for sig in correction_signals)
        
        if has_correction_signal:
            new_budget = self._extract_budget(message)
            current_budget = self.data.get('budget')
            if new_budget and new_budget >= 10000 and current_budget and new_budget != current_budget:
                self.data['budget'] = new_budget
                logger.info(f"[FLOW] {self.user_id[-4:]}: budget corrected → {new_budget:,}")
                # Stay in current state, but acknowledge the change and re-ask
                # the question the user is currently being asked
                return self._continue_after_correction(
                    correction_text=f"Got it — updating your budget to *AED {new_budget:,}* 💰",
                    properties=properties
                )
        
        # ─── 2. City correction ───
        inventory_cities = self._extract_inventory_cities(properties)
        candidates = sorted(inventory_cities, key=len, reverse=True)
        new_city = self._extract_city(message, candidates)
        current_city = (self.data.get('city') or '')
        if new_city and has_correction_signal and current_city and new_city.lower() != current_city.lower():
            self.data['city'] = new_city
            logger.info(f"[FLOW] {self.user_id[-4:]}: city corrected → {new_city}")
            return self._continue_after_correction(
                correction_text=f"Got it — switching to *{new_city}* 🌆",
                properties=properties
            )
        
        # ─── 3. Type correction ───
        # (already handled inside _handle_budget for the AWAITING_BUDGET state;
        #  this catches it in OTHER states like AWAITING_EMAIL)
        inventory_types = self._extract_inventory_types(properties)
        new_type = self._extract_property_type_dynamic(message, inventory_types)
        current_type = (self.data.get('prop_type') or '')
        if new_type and has_correction_signal and current_type and new_type.lower() != current_type.lower():
            types_lower = {t.lower() for t in inventory_types}
            if new_type.lower() in types_lower:
                self.data['prop_type'] = new_type
                logger.info(f"[FLOW] {self.user_id[-4:]}: type corrected → {new_type}")
                return self._continue_after_correction(
                    correction_text=f"Got it — switching to *{new_type}* 🏠",
                    properties=properties
                )
        
        return None  # No correction detected
    
    def _continue_after_correction(self, correction_text: str, properties: List[Dict]) -> FlowResponse:
        """
        After a correction, acknowledge the change and re-prompt the question
        appropriate to the current flow state.
        """
        # Pick the prompt that matches the state we're currently in
        state_prompts = {
            FlowState.AWAITING_CITY: "Which city interests you for your property search? 🏙️",
            FlowState.AWAITING_PURPOSE: "Is this purchase for *investment* or *personal use*?",
            FlowState.AWAITING_TYPE: "What type of property are you looking for?",
            FlowState.AWAITING_BUDGET: "What budget range are you working with? Please share in AED.\n(e.g., 100,000 AED or 200,000 AED) 💰",
            FlowState.AWAITING_EMAIL: "Where should I send you the detailed brochures? Please share your email address. 📧",
            FlowState.AWAITING_MEETING_DATETIME: "Please share your preferred date and time:\n📅 Date: DD-MM-YYYY\n⏰ Time: HH:MM AM/PM",
        }
        prompt = state_prompts.get(self.state, "How can I help you?")
        
        return FlowResponse(
            text=f"{correction_text}\n\n{prompt}",
            action="send_text",
            next_state=self.state  # stay in the same state
        )
    
    # ========================================================================
    # EXTRACTION HELPERS - Pull structured data from user messages
    # ========================================================================
    
    def _extract_city(self, message: str, available_cities: List[str]) -> Optional[str]:
        """Find city name in message"""
        message_lower = message.lower()
        for city in available_cities:
            if city.lower() in message_lower:
                return city
        return None
    
    def _extract_purpose(self, message: str) -> Optional[str]:
        """Detect investment vs personal use"""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ['invest', 'investment', 'rental', 'roi', 'return']):
            return "Investment"
        if any(w in msg_lower for w in ['personal', 'live', 'family', 'home', 'self']):
            return "Personal Use"
        return None
    
    def _extract_property_type(self, message: str) -> Optional[str]:
        """Extract property type"""
        msg_lower = message.lower()
        types = {
            'apartment': ['apartment', 'flat', 'condo'],
            'villa': ['villa', 'house', 'mansion'],
            'plot': ['plot', 'land'],
            'commercial': ['commercial', 'office', 'shop', 'retail'],
            'farmhouse': ['farmhouse', 'farm house'],
            'townhouse': ['townhouse', 'town house'],
            'studio': ['studio'],
            'penthouse': ['penthouse'],
        }
        for ptype, keywords in types.items():
            if any(kw in msg_lower for kw in keywords):
                return ptype.title()
        return None
    
    def _extract_inventory_types(self, properties: List[Dict]) -> set:
        """Pull all unique property types from inventory. Pure DB-driven."""
        types = set()
        for p in properties:
            ptype = p.get('property_type', '').strip()
            if ptype:
                types.add(ptype.title())  # normalize "apartment" / "APARTMENT" → "Apartment"
        return types
    
    def _extract_property_type_dynamic(self, message: str, inventory_types: set) -> Optional[str]:
        """
        Extract any property type the user mentions — whether or not it's in inventory.
        The handler decides what to do with the result (show it, or diplomatically redirect).
        
        Order:
        1. Inventory types (longest first, so multi-word types win)
        2. Universal real-estate vocabulary (so we recognize "villa" even if dealer doesn't sell villas)
        3. Synonyms canonicalized to the inventory's terminology if possible
        """
        msg_lower = message.lower()
        
        # 1. Try inventory types first — longest match wins
        for itype in sorted(inventory_types, key=len, reverse=True):
            if itype.lower() in msg_lower:
                return itype
        
        # 2. Universal real-estate vocabulary — types Sarah should always RECOGNIZE
        #    even if the dealer doesn't sell them. The handler decides what to say.
        universal_types = [
            'penthouse', 'townhouse', 'farmhouse',  # multi-word/longer first
            'apartment', 'commercial', 'villa', 'plot', 'studio', 'duplex',
            'bungalow', 'mansion', 'condo', 'flat', 'office', 'shop',
            'warehouse', 'land',
        ]
        for utype in universal_types:
            if utype in msg_lower:
                # Canonicalize aliases to the dealer's terminology IF inventory has the canonical
                aliases_to_canonical = {
                    'flat': 'Apartment', 'condo': 'Apartment',
                    'house': 'Villa', 'mansion': 'Villa', 'bungalow': 'Villa',
                    'office': 'Commercial', 'shop': 'Commercial',
                    'land': 'Plot',
                }
                types_lower = {t.lower() for t in inventory_types}
                if utype in aliases_to_canonical:
                    canonical = aliases_to_canonical[utype]
                    if canonical.lower() in types_lower:
                        return canonical  # canonicalize to inventory term
                return utype.title()  # return the literal type the user asked for
        
        return None
    
    def _extract_all_property_types(self, message: str) -> List[Tuple[int, str]]:
        """
        Find ALL property types mentioned in message, sorted by position.
        Returns list of (position, type) tuples.
        Used to detect mid-flow corrections like "no I don't want apartment, give me commercial".
        """
        msg_lower = message.lower()
        types = {
            'apartment': ['apartment', 'flat', 'condo'],
            'villa': ['villa', 'house', 'mansion'],
            'plot': ['plot', 'land'],
            'commercial': ['commercial', 'office', 'shop', 'retail'],
            'farmhouse': ['farmhouse', 'farm house'],
            'townhouse': ['townhouse', 'town house'],
            'studio': ['studio'],
            'penthouse': ['penthouse'],
        }
        found = []
        for ptype, keywords in types.items():
            for kw in keywords:
                pos = msg_lower.find(kw)
                if pos >= 0:
                    found.append((pos, ptype.title()))
                    break  # one match per type is enough
        found.sort(key=lambda x: x[0])
        return found
    
    def _extract_inventory_cities(self, properties: List[Dict]) -> set:
        """
        Extract all valid city tokens from inventory location strings.
        Splits on comma, filters out junk (zip codes, blank, single chars).
        Pure database-driven — no hardcoded city names anywhere.
        """
        cities = set()
        for p in properties:
            location = p.get('location', '')
            if not location:
                continue
            for part in location.split(','):
                part = part.strip()
                # Reject: empty, single chars, pure numbers (zip codes), 
                # and obvious form-field junk
                if not part or len(part) < 2 or part.isdigit():
                    continue
                # Reject if mostly digits (zip codes like "110001-A")
                if sum(c.isdigit() for c in part) > len(part) // 2:
                    continue
                cities.add(part)
        return cities
    
    def _extract_budget(self, message: str) -> Optional[int]:
        """Extract budget number from message"""
        # Remove common words
        clean = message.lower().replace(',', '').replace('aed', '').replace('dirham', '')
        clean = clean.replace('rs', '').replace('inr', '').replace('budget', '')
        
        # Find numbers
        numbers = re.findall(r'\d+\.?\d*', clean)
        if not numbers:
            return None
        
        try:
            num = float(numbers[0])
            
            # Handle "lakh" multiplier
            if 'lakh' in message.lower() or 'lac' in message.lower():
                num = num * 100000
            elif 'crore' in message.lower() or 'cr' in message.lower():
                num = num * 10000000
            elif 'k' in message.lower() and num < 10000:
                num = num * 1000
            elif 'million' in message.lower() or 'mil' in message.lower():
                num = num * 1000000
            
            return int(num)
        except:
            return None
    
    def _extract_email(self, message: str) -> Optional[str]:
        """Extract email from message"""
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message)
        return match.group(0) if match else None
    
    def _extract_datetime(self, message: str) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Extract date (DD-MM-YYYY) and time (HH:MM AM/PM) from message.
        Returns: (date, time, needs_year_confirmation)
        """
        from datetime import datetime, timedelta
        
        msg = message.strip()
        msg_lower = msg.lower()
        
        # Get current year/date for safety
        now = datetime.now()
        current_year = now.year
        
        # Try to parse date
        date_str = None
        needs_year_confirm = False
        
        # Pattern 1: DD-MM-YYYY or DD/MM/YYYY
        m = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', msg)
        if m:
            d, mo, y = m.groups()
            try:
                dt = datetime(int(y), int(mo), int(d))
                # Sanity check year
                if dt.year < current_year - 1 or dt.year > current_year + 2:
                    return None, None, False
                date_str = dt.strftime("%d-%m-%Y")
            except:
                pass
        
        # Pattern 2: "26 May" or "May 26" (no year given)
        if not date_str:
            month_names = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            }
            for mname, mnum in month_names.items():
                if mname in msg_lower:
                    # Find day number near month name
                    m2 = re.search(r'(\d{1,2})\D*' + mname + r'|\b' + mname + r'\D*(\d{1,2})', msg_lower)
                    if m2:
                        day = m2.group(1) or m2.group(2)
                        try:
                            dt = datetime(current_year, mnum, int(day))
                            if dt < now:  # Date already passed → assume next year
                                dt = datetime(current_year + 1, mnum, int(day))
                            needs_year_confirm = True  # Always confirm year when not given
                            date_str = dt.strftime("%d-%m-%Y")
                        except:
                            pass
                    break
        
        # Pattern 3: "tomorrow", "today"
        if not date_str:
            if 'tomorrow' in msg_lower:
                date_str = (now + timedelta(days=1)).strftime("%d-%m-%Y")
            elif 'today' in msg_lower:
                date_str = now.strftime("%d-%m-%Y")
        
        # Try to parse time
        time_str = None
        # Pattern: HH:MM AM/PM or HH AM/PM
        m = re.search(r'(\d{1,2}):?(\d{0,2})\s*(am|pm|AM|PM)', msg)
        if m:
            h = int(m.group(1))
            mins = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3).upper()
            if 1 <= h <= 12 and 0 <= mins <= 59:
                time_str = f"{h:02d}:{mins:02d} {ampm}"
        
        # Pattern: "5 o'clock" → ask AM/PM
        if not time_str:
            m = re.search(r'(\d{1,2})\s*o.?clock', msg_lower)
            if m:
                # Has time but no AM/PM - return None to ask
                return date_str, None, needs_year_confirm
        
        return date_str, time_str, needs_year_confirm
    
    def _detect_yes_no(self, message: str) -> str:
        """Detect yes/no/unclear from user response"""
        msg_lower = message.lower().strip()
        
        yes_words = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'alright', 
                    'fine', 'good', 'great', 'love', 'like it', 'amazing',
                    'fantastic', 'perfect', 'awesome', 'i like', 'looks good',
                    'go ahead', 'sounds good', 'works', 'definitely', 'absolutely',
                    'i will', "let's", 'lets', "i'll", 'agreed',
                    # Added more positive words
                    'nice', 'wow', 'beautiful', 'lovely', 'cool', 'super',
                    'excellent', 'brilliant', 'fab', 'fabulous', 'wonderful',
                    'splendid', 'class', 'top', 'best', 'liked', 'loved',
                    'damn', 'mast', 'badhiya']
        
        # Emoji detection (positive vibes)
        positive_emojis = ['👍', '👌', '❤️', '😍', '🔥', '💯', '✨', '🎉', '😊', '🙌']
        if any(emoji in message for emoji in positive_emojis):
            return "yes"
        
        no_words = ['no', 'nope', 'not really', "don't like", 'dont like',
                   'not interested', 'something else', 'different', 'other',
                   'alternative', 'show me others', 'not for me', 'pass',
                   'skip', 'next', 'show more', 'still', "i don't"]
        
        # Check NO first (more specific)
        if any(w in msg_lower for w in no_words):
            return "no"
        
        if any(w in msg_lower for w in yes_words):
            return "yes"
        
        return "unclear"
    
    def _get_available_types(self, properties: List[Dict]) -> List[str]:
        """Get list of property types available in inventory"""
        types = set()
        for p in properties:
            if not p.get('is_sold', False):
                ptype = p.get('property_type', '').strip().title()
                if ptype:
                    types.add(ptype)
        return sorted(list(types))
    
    def _get_gender_title(self) -> str:
        """Determine Mr./Ms. based on name"""
        first_name = self.user_name.split()[0] if self.user_name else "there"
        name_lower = first_name.lower()
        
        female_names = ['priya', 'aisha', 'fatima', 'sarah', 'maria', 'sara',
                       'mary', 'nisha', 'pooja', 'kavya', 'ananya', 'riya',
                       'anjali', 'meera', 'neha', 'divya', 'simran']
        male_names = ['aman', 'ahmed', 'john', 'raj', 'ali', 'mohammed',
                     'rohan', 'arjun', 'vikram', 'rahul', 'suresh', 'amit',
                     'rohit', 'karan', 'vivek', 'sumit']
        
        if any(fn in name_lower for fn in female_names):
            return f"Ms. {first_name}"
        elif any(mn in name_lower for mn in male_names):
            return f"Mr. {first_name}"
        return first_name
    
    def _format_alternatives_list(self, alternatives: List[Dict]) -> str:
        """Format alternatives as numbered list"""
        lines = []
        for idx, alt in enumerate(alternatives[:3], 1):
            price = alt.get('price_aed', 'N/A')
            name = alt.get('name', 'Property')
            ptype = alt.get('property_type', 'Property').title()
            area = alt.get('area', 'N/A')
            
            lines.append(
                f"*{idx}. {name}*\n"
                f"💰 AED {price:,}\n"
                f"🏠 {ptype} | 📐 {area} sqft\n"
            )
        return "\n".join(lines)
    
    # ========================================================================
    # STATE PERSISTENCE - For loading/saving state across messages
    # ========================================================================
    
    def to_dict(self) -> Dict:
        """Serialize state for saving to DB/sheets"""
        return {
            'user_id': self.user_id,
            'user_name': self.user_name,
            'state': self.state.value,
            'data': self.data,
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'ConversationFlow':
        """Restore from saved state"""
        flow = cls(user_id=d['user_id'], user_name=d.get('user_name', ''))
        flow.state = FlowState(d.get('state', 'greeting'))
        flow.data = d.get('data', flow.data)
        return flow