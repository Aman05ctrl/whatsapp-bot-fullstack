"""
Memory Feature — Smart Returning User Detection
================================================
Provides time-aware "welcome back" experiences for returning users.

Three behavior tiers based on time since last interaction:
- < 30 min       → Silent resume (treat as same session)
- 30 min – 7 days → Friendly continuation
- > 7 days        → Confirm intent (user must opt in to resume)

KILL SWITCH:
Controlled by MEMORY_ENABLED env var. Set to "false" to disable globally
(useful for testing — bot treats everyone as a fresh user).

Author: Aman Dominator | Production Memory Module
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Time tier thresholds
SILENT_RESUME_MINUTES = 30
FRIENDLY_RESUME_DAYS = 7

# Memory storage key prefix (so it doesn't collide with other state)
MEMORY_KEY = "memory_context"


class MemoryTier(Enum):
    """Time-based behavior tiers"""
    DISABLED = "disabled"       # Kill switch is off
    NEW_USER = "new_user"       # First-time user, no history
    SILENT = "silent"           # < 30 min — pick up silently
    FRIENDLY = "friendly"       # 30 min – 7 days — acknowledge return
    CONFIRM = "confirm"         # > 7 days — ask if still interested


# ============================================================================
# KILL SWITCH
# ============================================================================

def is_memory_enabled() -> bool:
    """
    Check if the memory feature is enabled globally.
    Reads MEMORY_ENABLED env var. Defaults to TRUE (production behavior).
    
    To disable for testing, set MEMORY_ENABLED=false in .env and restart Flask.
    """
    val = os.getenv('MEMORY_ENABLED', 'true').strip().lower()
    enabled = val not in ('false', '0', 'no', 'off')
    return enabled


# ============================================================================
# TIME-TIER DETECTION
# ============================================================================

def compute_time_tier(last_seen: Optional[datetime]) -> MemoryTier:
    """
    Decide which welcome-back behavior to use based on time elapsed.
    """
    if last_seen is None:
        return MemoryTier.NEW_USER
    
    now = datetime.now(timezone.utc)
    
    # Defensive: ensure last_seen is timezone-aware
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    
    elapsed = now - last_seen
    
    if elapsed < timedelta(minutes=SILENT_RESUME_MINUTES):
        return MemoryTier.SILENT
    if elapsed < timedelta(days=FRIENDLY_RESUME_DAYS):
        return MemoryTier.FRIENDLY
    return MemoryTier.CONFIRM


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """
    Parse various timestamp formats. Handles ISO 8601 with timezone,
    plain datetime, and date-only. Returns None on parse failure.
    """
    if not ts_str:
        return None
    
    cleaned = ts_str.strip()
    
    # Python 3.11+ datetime.fromisoformat handles "+05:30" natively.
    # On earlier versions, this also works for most ISO variants.
    try:
        return datetime.fromisoformat(cleaned)
    except (ValueError, AttributeError):
        pass
    
    # Fallback: try common explicit formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    
    logger.debug(f"[MEMORY] Could not parse timestamp: {ts_str!r}")
    return None


# ============================================================================
# CONTEXT FETCH
# ============================================================================

def get_returning_user_context(
    user_fingerprint: str,
    user_phone: str,
    sheets_logs_fn=None,
    crm_fetch_fn=None,
    correlation_id: str = "N/A",
) -> Dict:
    """
    Pull everything we know about a returning user.
    
    Args:
        user_fingerprint: SHA-256 fingerprint of the user
        user_phone: Phone number (fallback identifier)
        sheets_logs_fn: Callable that returns the user's most recent log row
                        (signature: fn(phone) -> dict | None)
        crm_fetch_fn: Callable that returns lead data from CRM backend
                      (signature: fn(phone) -> dict | None)
        correlation_id: For logging
    
    Returns:
        {
            "is_returning": bool,
            "tier": MemoryTier,
            "last_seen": datetime | None,
            "fields": {city, prop_type, purpose, budget, email},  # what we remember
            "last_state": str | None,                              # FlowState value
            "summary": str | None,                                  # human-readable summary
        }
    """
    context = {
        "is_returning": False,
        "tier": MemoryTier.NEW_USER,
        "last_seen": None,
        "fields": {},
        "last_state": None,
        "summary": None,
    }
    
    # 1. Pull from CRM backend
    crm_data = None
    if crm_fetch_fn:
        try:
            crm_data = crm_fetch_fn(user_phone)
        except Exception as e:
            logger.warning(f"[MEMORY] CRM fetch failed: {e} | {correlation_id}")
    
    # 2. Pull most-recent log entry (for timestamp + last interaction)
    last_log = None
    if sheets_logs_fn:
        try:
            last_log = sheets_logs_fn(user_phone)
        except Exception as e:
            logger.warning(f"[MEMORY] Logs fetch failed: {e} | {correlation_id}")
    
    # 3. If neither source has anything, this is a new user
    if not crm_data and not last_log:
        logger.info(f"[MEMORY] New user (no history) | {correlation_id}")
        return context
    
    context["is_returning"] = True
    
    # 4. Extract last_seen timestamp — try CRM first (most reliable),
    #    then fall back to logs sheet if provided
    if crm_data:
        # CRM has authoritative timestamps: last_updated or created_at
        ts_str = crm_data.get("last_updated") or crm_data.get("created_at")
        if ts_str:
            parsed = parse_timestamp(str(ts_str))
            if parsed:
                context["last_seen"] = parsed
    
    if not context["last_seen"] and last_log and last_log.get("timestamp"):
        parsed = parse_timestamp(str(last_log["timestamp"]))
        if parsed:
            context["last_seen"] = parsed
    
    # 5. Compute behavior tier from time elapsed
    context["tier"] = compute_time_tier(context["last_seen"])
    
    # 6. Pull known fields from CRM (only fields the CRM actually returns)
    if crm_data:
        fields = {}
        # Only restore fields that are non-null AND meaningful
        field_map = [
            ("city", "city"),
            ("email", "email"),
            ("interest", "purpose"),
            ("budget_category", "budget"),
            ("name", "name"),
        ]
        for src_key, dest_key in field_map:
            val = crm_data.get(src_key)
            if val and val != "null" and str(val).strip():
                fields[dest_key] = val
        context["fields"] = fields
        
        # ─── Use CRM's last_updated as the last_seen timestamp ───
        # Your CRM schema uses 'last_updated' for the most recent activity time.
        if not context["last_seen"]:
            last_updated_str = crm_data.get("last_updated")
            if last_updated_str:
                parsed = parse_timestamp(str(last_updated_str))
                if parsed:
                    context["last_seen"] = parsed
                    context["tier"] = compute_time_tier(parsed)
    
    # 7. Build human-readable summary
    context["summary"] = _build_summary(context["fields"])
    
    logger.info(
        f"[MEMORY] Returning user | tier={context['tier'].value} | "
        f"fields={list(context['fields'].keys())} | "
        f"last_seen={context['last_seen']} | {correlation_id}"
    )
    return context


def _build_summary(fields: Dict) -> str:
    """Build a one-line summary of what we remember about the user.
    
    Reads naturally even when only some fields are known:
    - "Apartment in Dubai at AED 100,000"
    - "Apartment in Dubai"
    - "your property search in Dubai"     ← falls back if no type
    - "your property search"               ← falls back if only general
    """
    prop_type = fields.get("prop_type", "").strip() if fields.get("prop_type") else ""
    city = fields.get("city", "").strip() if fields.get("city") else ""
    budget = fields.get("budget")
    
    # Build readable phrase
    if prop_type and city:
        head = f"*{prop_type}* in *{city}*"
    elif prop_type:
        head = f"*{prop_type}*"
    elif city:
        head = f"your property search in *{city}*"
    else:
        head = "your property search"
    
    if budget:
        try:
            # Only show budget if it's a real number
            clean = str(budget).replace(",", "").replace("AED", "").replace("aed", "").strip()
            b = int(float(clean))
            return f"{head} at *AED {b:,}*"
        except (ValueError, TypeError):
            # Budget is a stale tier label like "Low" or "Standard" — skip it
            pass
    return head


# ============================================================================
# WELCOME-BACK MESSAGE BUILDER
# ============================================================================

def build_welcome_back_message(
    user_name: str,
    context: Dict,
) -> Optional[str]:
    """
    Build the tier-appropriate welcome-back message.
    Returns None for SILENT/NEW_USER tiers (no message needed).
    """
    tier = context.get("tier")
    summary = context.get("summary", "")
    first_name = (user_name or "there").split()[0]
    
    if tier == MemoryTier.SILENT:
        return None  # silent resume — no welcome-back needed
    
    if tier == MemoryTier.NEW_USER:
        return None  # not a returning user — normal greeting handles it
    
    if tier == MemoryTier.FRIENDLY:
        if summary:
            # If summary starts with "your" (no specific prop_type), drop "about that"
            # so it reads naturally: "Picking up where we left off — your property search..."
            connector = "—" if summary.startswith("your") else "— about that"
            return (
                f"Welcome back, {first_name}! 👋\n\n"
                f"Picking up where we left off {connector} {summary}. "
                f"Let me know how I can help you continue! 😊"
            )
        return (
            f"Welcome back, {first_name}! 👋\n\n"
            f"Great to see you again. How can I help you today?"
        )
    
    if tier == MemoryTier.CONFIRM:
        if summary:
            return (
                f"Welcome back, {first_name}! 👋\n\n"
                f"It's been a while! Last time you were interested in "
                f"{summary}.\n\n"
                f"Are you still looking for that, or would you like to start fresh? "
                f"Reply *yes* to continue with the same criteria, or *no* to begin a new search. 😊"
            )
        return (
            f"Welcome back, {first_name}! 👋\n\n"
            f"It's been a while. Would you like to start a new property search? "
            f"Reply *yes* to begin. 😊"
        )
    
    return None


# ============================================================================
# LOGGING HELPER (visibility for debugging)
# ============================================================================

def log_memory_event(event: str, context: Dict, correlation_id: str = "N/A"):
    """Standardized log line for memory-related events"""
    tier = context.get("tier", MemoryTier.NEW_USER).value if context else "n/a"
    logger.info(f"[MEMORY] {event} | tier={tier} | {correlation_id}")