"""
Intent Classifier — Gemini-powered semantic understanding
==========================================================
Replaces brittle keyword matching with intent classification.

Classifies user messages into intents and extracts entities — all in one
Gemini call. Returns a structured dict the state machine can act on.

This module is PURE: no global state, no imports of main.py.
The Gemini call itself is injected via the gemini_call_fn parameter so
the same circuit breaker / concurrency limits / quota tracking apply.
"""

import json
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

INTENT_PROMPT_TEMPLATE = """You are an intent classifier for a real-estate WhatsApp bot named Selvora.
Analyze the user's message in conversation context. Return ONLY a JSON object — NO other text, NO markdown, NO code fences.

CONTEXT:
- Current bot state: {state}
- Already captured from user: {captured}
- Properties available in inventory:
  - Types: {types}
  - Cities: {cities}

USER MESSAGE: "{message}"

Return this EXACT JSON schema:
{{
  "intent": "<one of: provide_info | correct_field | restart_search | confirm_yes | confirm_no | ask_question | smalltalk | unclear>",
  "fields": {{
    "city": "<city name from inventory, or null>",
    "prop_type": "<type from inventory like Apartment/Commercial/Villa, or null>",
    "purpose": "<investment, personal_use, or null>",
    "budget": <integer in AED or null>,
    "email": "<email address or null>",
    "datetime": "<DD-MM-YYYY HH:MM AM/PM or null>"
  }},
  "wants_restart": <true if user wants to start the search over with new criteria, else false>,
  "confidence": <float 0.0 to 1.0>
}}

INTENT GUIDE:
- "provide_info": user is answering the question they were asked (giving city/budget/email/etc.)
- "correct_field": user wants to change ONE previously-given answer
- "restart_search": user wants to abandon current track and search for something else
  (e.g. "I changed my mind, I want X in Y instead" with multiple fields)
- "confirm_yes": affirmative (yes, sure, ok, sounds good, 👍, etc.)
- "confirm_no": negative (no, not interested, nope, etc.)
- "ask_question": user is asking for info (about ROI, location details, etc.)
- "smalltalk": greetings, thanks, off-topic chitchat
- "unclear": cannot determine intent

CRITICAL RULES:
- "Delhi" → fields.city = "Delhi" (only if Delhi is in available cities, else null)
- "100k" or "100000" or "1 lakh" → fields.budget = 100000 (integer, no commas)
- "I'll go with apartment" → intent: provide_info, fields.prop_type: "Apartment"
- "actually let me try commercial instead" → intent: correct_field, fields.prop_type: "Commercial"
- "I changed my mind, I want commercial in Delhi" → intent: restart_search, fields: {{"city": "Delhi", "prop_type": "Commercial"}}, wants_restart: true
- IMPORTANT: When extracting fields from a restart message, extract ONLY what the user explicitly says. Do NOT invent or infer values. The bot will preserve previously-captured fields the user didn't re-mention.
- "yes", "ok", "👍", "sure", "sounds good" → intent: confirm_yes
- If user says a city/type NOT in inventory, still extract it for the bot to handle gracefully
- If unsure, prefer "unclear" over guessing — confidence < 0.5 means low quality

EXAMPLES:
Message: "100000 AED" → {{"intent":"provide_info","fields":{{"budget":100000}},"wants_restart":false,"confidence":0.98}}
Message: "I changed my mind, I want commercial in Delhi" → {{"intent":"restart_search","fields":{{"city":"Delhi","prop_type":"Commercial"}},"wants_restart":true,"confidence":0.95}}
Message: "yeah sounds great 👍" → {{"intent":"confirm_yes","fields":{{}},"wants_restart":false,"confidence":0.97}}
Message: "what's the ROI?" → {{"intent":"ask_question","fields":{{}},"wants_restart":false,"confidence":0.9}}

Now classify this message and return ONLY the JSON.
"""


def classify_intent(
    message: str,
    state: str,
    captured: Dict,
    available_types: List[str],
    available_cities: List[str],
    gemini_call_fn: Callable[[str], str],
    correlation_id: str = "N/A"
) -> Dict:
    """
    Classify user intent using Gemini. Returns dict with intent, fields, and metadata.
    
    Args:
        message: The user's message text
        state: Current FlowState value (e.g., "awaiting_email")
        captured: Dict of fields already captured (city, prop_type, budget, etc.)
        available_types: Property types in inventory
        available_cities: Cities in inventory
        gemini_call_fn: Function that takes a prompt str and returns Gemini's text response.
                        Should reuse main.py's circuit breaker / concurrency limits.
        correlation_id: For logging
    
    Returns:
        Parsed dict with keys: intent, fields, wants_restart, confidence.
        On any failure, returns a safe fallback with intent="unclear".
    """
    fallback = {
        "intent": "unclear",
        "fields": {},
        "wants_restart": False,
        "confidence": 0.0,
    }
    
    try:
        # Build the prompt
        prompt = INTENT_PROMPT_TEMPLATE.format(
            state=state,
            captured=json.dumps(captured, default=str),
            types=", ".join(available_types) if available_types else "none",
            cities=", ".join(available_cities) if available_cities else "none",
            message=message.replace('"', "'"),  # avoid breaking JSON in prompt
        )
        
        # Call Gemini through the injected function (reuses circuit breaker)
        raw_response = gemini_call_fn(prompt)
        
        # Defensive: if circuit breaker returned a fallback dict instead of str
        if isinstance(raw_response, dict):
            logger.warning(f"[INTENT] Gemini returned fallback dict | {correlation_id}")
            return fallback
        
        if not raw_response or not isinstance(raw_response, str):
            logger.warning(f"[INTENT] Empty response | {correlation_id}")
            return fallback
        
        # Strip code fences if Gemini added them despite instructions
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip("` \n")
        
        # Parse JSON
        result = json.loads(cleaned)
        
        # Sanity-validate shape
        if "intent" not in result:
            logger.warning(f"[INTENT] Missing 'intent' key | raw: {cleaned[:200]} | {correlation_id}")
            return fallback
        
        # Normalize fields: ensure dict, drop nulls
        fields = result.get("fields") or {}
        if not isinstance(fields, dict):
            fields = {}
        fields = {k: v for k, v in fields.items() if v not in (None, "", "null")}
        result["fields"] = fields
        result.setdefault("wants_restart", False)
        result.setdefault("confidence", 0.5)
        
        logger.info(
            f"[INTENT] {result['intent']} | conf={result.get('confidence'):.2f} | "
            f"restart={result.get('wants_restart')} | fields={list(fields.keys())} | {correlation_id}"
        )
        return result
        
    except json.JSONDecodeError as e:
        logger.warning(f"[INTENT] JSON parse failed: {e} | raw: {raw_response[:200] if 'raw_response' in dir() else 'N/A'} | {correlation_id}")
        return fallback
    except Exception as e:
        logger.warning(f"[INTENT] Classification error: {e} | {correlation_id}")
        return fallback