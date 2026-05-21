"""
Translation Service — Multi-Language Support for WhatsApp Bot
==============================================================
Handles bidirectional translation so the bot can converse in any language
while internal logic stays in English.

Architecture:
- User message (any language) → detect → translate to English → process
- Bot response (English) → translate to user's language → send

KILL SWITCH:
Set TRANSLATION_ENABLED=false in .env to disable globally (useful for testing).

Author: Aman Dominator | Multi-language module
"""

import os
import logging
import threading
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Supported languages (ISO 639-1 codes returned by langdetect)
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'es': 'Spanish',
    'de': 'German',
    'ja': 'Japanese',
    'fr': 'French',
    'ur': 'Urdu',  # bonus — common in UAE/UK
    'zh-cn': 'Chinese (Simplified)',  # bonus
}

DEFAULT_LANGUAGE = 'en'

# Translation cache (avoids re-translating identical phrases)
_TRANSLATION_CACHE = {}
_CACHE_LOCK = threading.Lock()
_MAX_CACHE_SIZE = 1000


# ============================================================================
# KILL SWITCH
# ============================================================================

def is_translation_enabled() -> bool:
    """Check if translation is enabled globally (env var TRANSLATION_ENABLED)"""
    val = os.getenv('TRANSLATION_ENABLED', 'true').strip().lower()
    return val not in ('false', '0', 'no', 'off')


# ============================================================================
# LANGUAGE DETECTION
# ============================================================================

def detect_language(text: str) -> str:
    """
    Detect the language of a message.
    Returns ISO code ('en', 'hi', 'ar', etc.) or 'en' as safe fallback.
    """
    if not text or len(text.strip()) < 3:
        return DEFAULT_LANGUAGE
    
    try:
        from langdetect import detect, DetectorFactory
        # Make detection deterministic (same input → same output)
        DetectorFactory.seed = 0
        
        detected = detect(text)
        
        # langdetect returns codes like 'zh-cn', map to our supported set
        if detected in SUPPORTED_LANGUAGES:
            return detected
        
        # Try the base language code (e.g., 'zh' → check 'zh-cn')
        base = detected.split('-')[0]
        for supported_code in SUPPORTED_LANGUAGES:
            if supported_code.startswith(base):
                return supported_code
        
        # Unknown language — fall back to English
        logger.debug(f"[TRANSLATE] Unsupported language detected: {detected}, defaulting to {DEFAULT_LANGUAGE}")
        return DEFAULT_LANGUAGE
        
    except Exception as e:
        logger.debug(f"[TRANSLATE] Detection failed: {e}, defaulting to {DEFAULT_LANGUAGE}")
        return DEFAULT_LANGUAGE


# ============================================================================
# TRANSLATION (via Gemini)
# ============================================================================

def translate_text(text: str, source_lang: str, target_lang: str, gemini_call_fn=None) -> str:
    """
    Translate text from source_lang to target_lang using Google Translate (free).
    
    Falls back to Gemini if Google Translate fails (resilience).
    
    Args:
        text: The text to translate
        source_lang: ISO code of source language ('en', 'hi', etc.)
        target_lang: ISO code of target language
        gemini_call_fn: Optional fallback Gemini function (only used if Google fails)
    
    Returns:
        Translated text, or original text if all translation methods fail
    """
    # No-op cases
    if not text or not text.strip():
        return text
    if source_lang == target_lang:
        return text
    if not is_translation_enabled():
        return text
    
    # Check cache first
    cache_key = f"{source_lang}::{target_lang}::{text}"
    with _CACHE_LOCK:
        if cache_key in _TRANSLATION_CACHE:
            return _TRANSLATION_CACHE[cache_key]
    
    # ─── Primary: Google Translate (free, fast, separate from Gemini quota) ───
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        translated = translator.translate(text)
        
        if translated and translated.strip():
            translated = translated.strip()
            
            # Cache it (bounded)
            with _CACHE_LOCK:
                if len(_TRANSLATION_CACHE) >= _MAX_CACHE_SIZE:
                    keys_to_remove = list(_TRANSLATION_CACHE.keys())[:100]
                    for k in keys_to_remove:
                        _TRANSLATION_CACHE.pop(k, None)
                _TRANSLATION_CACHE[cache_key] = translated
            
            logger.info(f"[TRANSLATE] {source_lang}→{target_lang} via Google | {len(text)} chars")
            return translated
        else:
            logger.warning(f"[TRANSLATE] Google returned empty, trying Gemini fallback")
            
    except Exception as e:
        logger.warning(f"[TRANSLATE] Google failed: {e}, trying Gemini fallback")
    
    # ─── Fallback: Gemini (only if Google failed) ───
    if not gemini_call_fn:
        logger.warning("[TRANSLATE] No Gemini fallback available, returning original")
        return text
    
    source_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
    target_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    
    prompt = f"""Translate the following {source_name} text to {target_name}.

CRITICAL RULES:
1. Preserve ALL formatting EXACTLY: asterisks (*), emojis, line breaks, numbers, currency symbols
2. Keep proper nouns unchanged (names, cities like "Dubai", brand names)
3. Keep currency codes unchanged (AED, USD, EUR)
4. Keep email addresses and phone numbers unchanged
5. Return ONLY the translation — no explanations, no quotes around it, no preamble
6. Maintain the same tone (formal/casual) as the source

Text to translate:
{text}

Translation:"""
    
    try:
        translated = gemini_call_fn(prompt)
        if not translated or not translated.strip():
            logger.warning(f"[TRANSLATE] Gemini fallback also empty, returning original")
            return text
        
        translated = translated.strip()
        if (translated.startswith('"') and translated.endswith('"')) or \
           (translated.startswith("'") and translated.endswith("'")):
            translated = translated[1:-1].strip()
        
        with _CACHE_LOCK:
            if len(_TRANSLATION_CACHE) >= _MAX_CACHE_SIZE:
                keys_to_remove = list(_TRANSLATION_CACHE.keys())[:100]
                for k in keys_to_remove:
                    _TRANSLATION_CACHE.pop(k, None)
            _TRANSLATION_CACHE[cache_key] = translated
        
        logger.info(f"[TRANSLATE] {source_lang}→{target_lang} via Gemini fallback | {len(text)} chars")
        return translated
        
    except Exception as e:
        logger.error(f"[TRANSLATE] All translation methods failed: {e}")
        return text


# ============================================================================
# CONVENIENCE WRAPPERS
# ============================================================================

def translate_to_english(text: str, user_lang: str, gemini_call_fn=None) -> str:
    """Translate user's incoming message to English for bot processing"""
    if user_lang == 'en':
        return text
    return translate_text(text, source_lang=user_lang, target_lang='en', gemini_call_fn=gemini_call_fn)


def translate_from_english(text: str, target_lang: str, gemini_call_fn=None) -> str:
    """Translate bot's outgoing English message to user's language"""
    if target_lang == 'en':
        return text
    return translate_text(text, source_lang='en', target_lang=target_lang, gemini_call_fn=gemini_call_fn)