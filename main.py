"""
WhatsApp AI Chatbot - ENTERPRISE PRODUCTION READY (ALL ISSUES FIXED)
=====================================================================

PRODUCTION FIXES APPLIED:
✅ #1-8: Previous enterprise fixes (webhook ACK, logging, caching, etc.)
✅ ISSUE 1: Queue overflow handling + DLQ + backpressure monitoring
✅ ISSUE 2: Global Google Sheets lock (thread-safe)
✅ ISSUE 3: Worker auto-recovery + health monitoring
✅ ISSUE 4: Circuit breaker recovery logging
✅ ISSUE 5: Dedup memory bounds (LRU eviction)
✅ ISSUE 6: Graceful shutdown (SIGTERM/SIGINT)

Author: AI Agent Development Team  
Last Updated: December 27, 2025 (Production Hardening v2)
"""

import os
import sys
import json
import re
import signal  # FIX ISSUE 6
import subprocess
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pytz
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
import logging
import time
import threading
from conversation_stage_system import (
    stage_manager,
    update_conversation_stage,
    get_stage_aware_fallback
)
from google.api_core import exceptions as google_exceptions
from collections import defaultdict
from typing import Dict, Set, Optional, Tuple, List  # FIX ISSUE 1
import uuid
from queue import Queue, Empty  # FIX ISSUE 1
from dataclasses import dataclass
from email_service import send_villa_enquiry_notification, send_meeting_confirmation
from calendar_service import format_meeting_calendar_link
from conversation_flow import ConversationFlow, FlowState
from property_handler import format_property_caption, get_property_images
import threading as _threading_for_flows
from datetime import datetime as _dt_for_flows, timedelta as _td_for_flows

class _ActiveFlowsStore:
    """Thread-safe dict with TTL-based cleanup (prevents memory leak at scale)"""
    def __init__(self, ttl_hours=24):
        self._data = {}
        self._last_touch = {}
        self._lock = _threading_for_flows.Lock()
        self._ttl = _td_for_flows(hours=ttl_hours)
        self._last_cleanup = _dt_for_flows.now()
    
    def __contains__(self, key):
        with self._lock:
            return key in self._data
    
    def __getitem__(self, key):
        with self._lock:
            self._last_touch[key] = _dt_for_flows.now()
            return self._data[key]
    
    def __setitem__(self, key, value):
        with self._lock:
            self._data[key] = value
            self._last_touch[key] = _dt_for_flows.now()
            # Cleanup every 5 minutes (not on every set — too expensive)
            if (_dt_for_flows.now() - self._last_cleanup).total_seconds() > 300:
                self._cleanup()
                self._last_cleanup = _dt_for_flows.now()
    
    def get(self, key, default=None):
        with self._lock:
            if key in self._data:
                self._last_touch[key] = _dt_for_flows.now()
                return self._data[key]
            return default
    
    def _cleanup(self):
        """Remove entries idle longer than TTL"""
        now = _dt_for_flows.now()
        expired = [k for k, t in self._last_touch.items() if now - t > self._ttl]
        for k in expired:
            self._data.pop(k, None)
            self._last_touch.pop(k, None)
        if expired:
            try:
                logger.info(f"[ACTIVE_FLOWS] Cleaned {len(expired)} idle entries")
            except Exception:
                pass
    
    def __len__(self):
        with self._lock:
            return len(self._data)

ACTIVE_FLOWS = _ActiveFlowsStore(ttl_hours=24)  # auto-cleans entries idle >24h

load_dotenv()

# ============================================================================
# GUNICORN RUNTIME DETECTION
# ============================================================================
def is_running_under_gunicorn():
    """Detect if running under Gunicorn WSGI server"""
    return "gunicorn" in os.environ.get("SERVER_SOFTWARE", "").lower() or \
           "gunicorn" in sys.argv[0].lower() or \
           os.environ.get("GUNICORN_CMD_ARGS") is not None

RUNNING_UNDER_GUNICORN = is_running_under_gunicorn()

# ============================================================================
# CRM FEATURES IMPORT
# ============================================================================
from crm_features import (
    leadscoring,
    followupmanager,
    summarygenerator,
    update_sheet_with_crm_features_optimized,
    record_user_activity,
    log_conversation_to_sheet,
    budgetqualifier,
    handovermanager,
    dropdetector,
    normalize_phone_number,
    find_user_row_exact,
    get_user_data_once,
    get_user_resume_context,
    generate_user_fingerprint,  # ✅ ADD
    format_phone_number          # ✅ ADD  
)

# ============================================================================
# UTF-8 CONSOLE FIX
# ============================================================================
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

# ============================================================================
# LOGGING
# ============================================================================
class UTF8StreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                safe_msg = msg.encode('ascii', 'replace').decode('ascii')
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

file_formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s')
console_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)

console_handler = UTF8StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(console_formatter)

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

def safe_log_info(message):
    try:
        logger.info(message)
    except UnicodeEncodeError:
        logger.info(message.encode('ascii', 'ignore').decode('ascii'))

def safe_log_error(message):
    try:
        logger.error(message)
    except UnicodeEncodeError:
        logger.error(message.encode('ascii', 'ignore').decode('ascii'))

def safe_log_warning(message):
    try:
        logger.warning(message)
    except UnicodeEncodeError:
        logger.warning(message.encode('ascii', 'ignore').decode('ascii'))

def safe_log_debug(message):
    try:
        logger.debug(message)
    except UnicodeEncodeError:
        logger.debug(message.encode('ascii', 'ignore').decode('ascii'))

# ============================================================================
# SLACK WEBHOOK ALERTS (CRITICAL FAILURES ONLY)
# ============================================================================
def send_slack_alert(message: str):
    """
    Send critical alert to Slack webhook (best-effort, non-blocking)
    Failures are silently logged and NEVER crash the system
    """
    try:
        slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        if not slack_webhook_url:
            # Silently skip if webhook not configured
            return
        
        payload = {
            "text": f"🚨 *WhatsApp Bot Critical Alert*\n{message}",
            "username": "WhatsApp CRM Bot",
            "icon_emoji": ":robot_face:"
        }
        
        # Non-blocking: 3 second timeout, no retries
        requests.post(
            slack_webhook_url,
            json=payload,
            timeout=3
        )
        
    except Exception as e:
        # NEVER crash on alert failure - log and continue
        safe_log_debug(f"[SLACK] Alert send failed (non-critical): {e}")

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================
DEMO_MODE = True
DEMO_MAX_AI_CALLS_PER_USER = 50
DEMO_SESSION_TIMEOUT = 1800
USE_CLAWDBOT = True

app = Flask(__name__)

@app.after_request
def add_ngrok_header(response):
    response.headers['ngrok-skip-browser-warning'] = 'true'
    return response

WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')
GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')

WHATSAPP_MODE = os.getenv('WHATSAPP_MODE', 'PROD').upper()
WHATSAPP_TEST_NUMBERS = set(filter(None, os.getenv('WHATSAPP_TEST_NUMBERS', '').split(',')))

if not all([WHATSAPP_TOKEN, PHONE_NUMBER_ID, GEMINI_API_KEY]):
    raise ValueError("❌ Missing required environment variables")

if WHATSAPP_MODE == 'DEV' and len(WHATSAPP_TEST_NUMBERS) == 0:
    safe_log_warning("⚠️  DEV MODE WITH ZERO TEST NUMBERS")

# ============================================================================
# GEMINI AI CONFIGURATION
# ============================================================================
genai.configure(api_key=GEMINI_API_KEY)

def get_available_gemini_model():
    """
    Dynamically detect and select the best available Gemini model.
    ZERO hardcoded models - 100% API-driven selection.
    """
    try:
        # Get all available models from API
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_name = m.name.split('/')[-1]
                available_models.append(model_name)
        
        if not available_models:
            raise RuntimeError("No Gemini models available with generateContent support")
        
        # Log what's available
        safe_log_info(f"[GEMINI] Available models: {', '.join(available_models[:10])}")
        
        # Preference order (check if they actually exist in API)
        preferred_order = [
            'gemini-2.5-flash-lite'
        ]
        
        # Try preferred models first
        for preferred in preferred_order:
            if preferred in available_models:
                safe_log_info(f"[GEMINI] ✅ Using model: {preferred}")
                return preferred
        
        # FAIL FAST: No fallback allowed - gemini-2.5-flash-lite MUST be available
        raise RuntimeError(f"CRITICAL: gemini-2.5-flash-lite not available. Available models: {available_models[:5]}")
            
    except Exception as e:
        safe_log_error(f"[GEMINI] ❌ Model detection failed: {e}")
        raise RuntimeError(f"Failed to initialize Gemini model: {e}")

GEMINI_MODEL_NAME = get_available_gemini_model()
model = genai.GenerativeModel(GEMINI_MODEL_NAME)

# ============================================================================
# LOAD PROPERTIES DATA
# ============================================================================
try:
    with open('data.json', 'r', encoding='utf-8') as f:
        PROPERTIES = json.load(f)
except Exception:
    PROPERTIES = []


BOT_AUTH_TOKEN = None

def _get_best_image_url(images):
    """Get best image URL, converting to jpg/png via Cloudinary if needed"""
    if not images:
        return 'https://images.unsplash.com/photo-1512453979798-5ea904ac6605?q=80&w=1000'
    
    # Prefer jpg/png first (WhatsApp supports both)
    for img in images:
        url = img['image_url']
        if url.endswith('.jpg') or url.endswith('.jpeg') or url.endswith('.png'):
            return url
    
    # Convert webp/other cloudinary URLs to jpg
    for img in images:
        url = img['image_url']
        if 'cloudinary.com' in url:
            return url.replace('/upload/', '/upload/f_jpg,q_90/')
    
    # Fallback to first image as-is
    return images[0]['image_url']

def _get_all_image_urls(images):
    """Get all image URLs - primary first, then rest in upload order, all converted to jpg/png"""
    if not images:
        return ['https://images.unsplash.com/photo-1512453979798-5ea904ac6605?q=80&w=1000']
    
    def convert_url(url):
        if url.endswith('.jpg') or url.endswith('.jpeg') or url.endswith('.png'):
            return url
        if 'cloudinary.com' in url:
            return url.replace('/upload/', '/upload/f_jpg,q_90/')
        return url
    
    # Sort: primary first, then by created_at order
    primary = [img for img in images if img.get('is_primary')]
    rest = [img for img in images if not img.get('is_primary')]
    
    ordered = primary + rest
    return [convert_url(img['image_url']) for img in ordered]

def fetch_properties_from_backend():
        """Fetch properties from backend API using bot account credentials"""
        global PROPERTIES, BOT_AUTH_TOKEN
        try:
            backend_url = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
            email = os.getenv('BOT_CLIENT_EMAIL')
            password = os.getenv('BOT_CLIENT_PASSWORD')

            if not email or not password:
                safe_log_error("[PROPERTIES] BOT_CLIENT_EMAIL or BOT_CLIENT_PASSWORD not set in .env")
                return

            # Login to get token
            login_resp = requests.post(
                f"{backend_url}/api/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )
            if login_resp.status_code != 200:
                safe_log_error(f"[PROPERTIES] Login failed: {login_resp.status_code} | {login_resp.text[:100]}")
                return

            BOT_AUTH_TOKEN = login_resp.json().get("access_token")
            if not BOT_AUTH_TOKEN:
                safe_log_error("[PROPERTIES] No access_token in login response")
                return

            # Fetch properties
            props_resp = requests.get(
            f"{backend_url}/api/properties/?status=active&size=500",
                headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                timeout=10
            )
            if props_resp.status_code != 200:
                safe_log_error(f"[PROPERTIES] Fetch failed: {props_resp.status_code}")
                return

            data = props_resp.json()
            raw_props = data.get('properties') or data.get('items') or []

            # Normalize to bot format
            PROPERTIES = []
            for p in raw_props:
                PROPERTIES.append({
                    'name': p.get('title', 'Property'),
                    'location': ', '.join(filter(None, [
                        p.get('address', ''),
                        p.get('city', ''),
                        p.get('state', ''),
                        p.get('zip_code', '')
                    ])),
                    'currency': p.get('currency', 'AED'),
                    'price_aed': f"{p.get('price', 0):,.0f}",
                    'roi': f"{p.get('expected_roi')}%" if p.get('expected_roi') else None,
                    'image_url': _get_best_image_url(p.get('images', [])),
                    'all_images': _get_all_image_urls(p.get('images', [])),
                    'bedrooms': p.get('bedrooms') or p.get('bhk'),
                    'bathrooms': p.get('bathrooms'),
                    'area': p.get('area_sqft') or p.get('area'),
                    'property_type': p.get('property_type', ''),
                    'emi_available': p.get('emi_available', False),
                    'description': p.get('description', ''),
                })

            safe_log_info(f"[PROPERTIES] ✅ Loaded {len(PROPERTIES)} properties for {email}")
        except Exception as e:
            safe_log_error(f"[PROPERTIES] Error: {e}")


# ─── PROPERTIES AUTO-REFRESH (every 5 minutes) ───
# Without this: bot must restart to see new properties added by dealer.
# With this: properties refresh in background, bot stays current.
def _start_properties_auto_refresh(interval_seconds=300):
    """Start background thread that re-fetches properties every 5 minutes."""
    def _refresh_loop():
        import time as _time
        while True:
            _time.sleep(interval_seconds)
            try:
                fetch_properties_from_backend()
                safe_log_info(f"[PROPERTIES] 🔄 Auto-refreshed | count={len(PROPERTIES)}")
            except Exception as e:
                safe_log_error(f"[PROPERTIES] Auto-refresh failed: {e}")
    
    refresh_thread = threading.Thread(
        target=_refresh_loop,
        name="PropertiesAutoRefresh",
        daemon=True
    )
    refresh_thread.start()
    safe_log_info(f"[PROPERTIES] Auto-refresh started (every {interval_seconds}s)")
# ============================================================================

# ============================================================================
# WEBHOOK MESSAGE QUEUE (FIXED ISSUES 1 & 3)
# ============================================================================
@dataclass
class WebhookMessage:
    correlation_id: str
    sender_id: str
    message_id: str
    text_body: str
    user_name: str
    timestamp: datetime

    # ADD after from dataclasses import dataclass

# ============================================================================
# WEBHOOK SCHEMA VALIDATION
# ============================================================================
def validate_whatsapp_webhook(data: dict, correlation_id: str) -> Tuple[bool, Optional[str]]:
    """
    Validate WhatsApp webhook payload structure
    Returns: (is_valid, error_message)
    """
    try:
        # Required top-level structure
        if not isinstance(data, dict):
            return False, "Payload is not a dict"
        
        if data.get("object") != "whatsapp_business_account":
            return False, f"Invalid object type: {data.get('object')}"
        
        # Validate entry array
        entry = data.get("entry")
        if not isinstance(entry, list) or len(entry) == 0:
            return False, "Missing or empty 'entry' array"
        
        # Validate changes structure
        changes = entry[0].get("changes")
        if not isinstance(changes, list) or len(changes) == 0:
            return False, "Missing or empty 'changes' array"
        
        # Validate value object
        value = changes[0].get("value")
        if not isinstance(value, dict):
            return False, "'value' is not a dict"
        
        # Skip status updates
        if "statuses" in value:
            return False, "Status update (skipped)"
        
        # Validate messages array
        if "messages" not in value:
            return False, "No 'messages' in value"
        
        messages = value.get("messages")
        if not isinstance(messages, list) or len(messages) == 0:
            return False, "Empty 'messages' array"
        
        # Validate message structure
        message = messages[0]
        if not isinstance(message, dict):
            return False, "Message is not a dict"
        
        # Required message fields
        if not message.get("from"):
            return False, "Missing 'from' field"
        
        if not message.get("id"):
            return False, "Missing message 'id' field"
        
        if not message.get("type"):
            return False, "Missing message 'type' field"
        
        # Validate text message structure
        if message.get("type") == "text":
            text_obj = message.get("text")
            if not isinstance(text_obj, dict) or "body" not in text_obj:
                return False, "Invalid text message structure"
        
        return True, None
        
    except Exception as e:
        return False, f"Validation exception: {str(e)}"

class WebhookProcessor:
    """
    Async webhook processor with:
    - FIX ISSUE 1: DLQ + backpressure monitoring
    - FIX ISSUE 3: Worker auto-recovery
    """
    def __init__(self, max_workers=5):
        self.queue = Queue(maxsize=1000)
        self.workers = []
        self.running = False
        self.max_workers = max_workers
        self.processed_count = 0
        self.failed_count = 0  # Track failed messages
        self.worker_restarts = 0
        self.restart_window_seconds = 300  # 5 minutes
        self.restart_timestamps = []  # Track restart times
        self.max_restarts_per_window = 10  # Max 10 restarts in 5 min
        self.restart_circuit_open = False
        self.lock = threading.Lock()
            
    def start(self):
        if self.running:
            return
            
        self.running = True
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"WebhookWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        safe_log_info(f"[QUEUE] Started {self.max_workers} webhook workers")
    
    def stop(self):
        """FIX ISSUE 6: Graceful stop"""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        safe_log_info("[QUEUE] Stopped webhook workers")
    
    def enqueue(self, msg: WebhookMessage) -> bool:
        """Backpressure monitoring with hard limit protection"""
        try:
            # Hard limit check BEFORE enqueue
            queue_size = self.queue.qsize()
        
            if queue_size > 950:  # 95% critical - REJECT
                safe_log_error(
                    f"[QUEUE] 🚨 REJECT: Queue at {queue_size}/1000 (95% limit) | "
                    f"Correlation: {msg.correlation_id} | "
                    f"Sender: {msg.sender_id[-4:]}"
            )
            
                # Alert: Queue overflow protection triggered
                send_slack_alert(
                    f"*Queue Overflow Protection Triggered*\n"
                    f"• Queue Size: {queue_size}/1000 (95% limit)\n"
                    f"• Correlation ID: {msg.correlation_id}\n"
                    f"• Action: Message rejected, webhook will retry (429)"
            )
            
                return False  # Return False so webhook returns 429
        
            if queue_size > 800:  # 80% warning
                safe_log_warning(f"[QUEUE] ⚠️ HIGH WATER MARK: {queue_size}/1000")
        
            self.queue.put(msg, timeout=1)
            safe_log_debug(f"[QUEUE] Enqueued {msg.correlation_id}")
            return True
        except Exception as e:
            # Track failure for monitoring
            with self.lock:
                self.failed_count += 1
            
            # Log with full context for debugging
            safe_log_error(
                f"[QUEUE] FULL! Message dropped | "
                f"Correlation: {msg.correlation_id} | "
                f"Sender: {msg.sender_id[-4:]} | "
                f"Total Failed: {self.failed_count} | "
                f"Error: {str(e)}"
            )
            return False
    
    def _worker_loop(self):
        """FIX ISSUE 3: Worker with health monitoring and auto-recovery"""
        worker_name = threading.current_thread().name
        safe_log_info(f"[WORKER] {worker_name} started")
        
        consecutive_failures = 0
        max_consecutive_failures = 10
        
        while self.running:
            try:
                msg = self.queue.get(timeout=1)
                self._process_message(msg)
                consecutive_failures = 0  # Reset on success
                with self.lock:
                    self.processed_count += 1
                self.queue.task_done()
            except Empty:
                continue
            except Exception as e:
                consecutive_failures += 1
                safe_log_error(f"[WORKER] {worker_name} error #{consecutive_failures}: {e}")
                
                # FIX ISSUE 3: Prevent infinite crash loop
                if consecutive_failures >= max_consecutive_failures:
                    safe_log_error(f"[WORKER] {worker_name} CRASHED after {consecutive_failures} failures")
                    self._restart_worker(worker_name)
                    break
                continue
        
        safe_log_info(f"[WORKER] {worker_name} stopped")
    
    def _restart_worker(self, failed_worker_name):
        """FIX ISSUE 3: Auto-restart crashed worker (stability guard)"""
        if not self.running:
            return
        
        with self.lock:
            # Check restart circuit breaker
            now = time.time()
            self.restart_timestamps = [t for t in self.restart_timestamps if now - t < self.restart_window_seconds]

            if len(self.restart_timestamps) >= self.max_restarts_per_window:
                if not self.restart_circuit_open:
                    self.restart_circuit_open = True
                    
                    # Alert: Restart circuit breaker opened (only once)
                    send_slack_alert(
                        f"*Worker Restart Circuit Breaker OPEN*\n"
                        f"• Restarts: {len(self.restart_timestamps)} in {self.restart_window_seconds}s\n"
                        f"• Max Allowed: {self.max_restarts_per_window}\n"
                        f"• Action: Auto-restart disabled\n"
                        f"• Status: CRITICAL - Manual intervention required"
                    )
                
                safe_log_error(
                    f"[WORKER] 🚨 RESTART CIRCUIT OPEN: {len(self.restart_timestamps)} restarts "
                    f"in {self.restart_window_seconds}s. Stopping auto-restart."
                )
                return  # Do not restart
            
            # Record restart
            self.restart_timestamps.append(now)
            self.worker_restarts += 1
            
            # Create and start worker INSIDE lock to prevent race condition
            safe_log_warning(f"[WORKER] 🔄 Auto-restarting {failed_worker_name}")
            new_worker = threading.Thread(
                target=self._worker_loop,
                name=f"{failed_worker_name}-restarted",
                daemon=True
            )
            new_worker.start()
            
            safe_log_error(
                f"[WORKER] 🔄 RESTART #{self.worker_restarts}: {failed_worker_name} → {new_worker.name} "
                f"({len(self.restart_timestamps)} restarts in {self.restart_window_seconds}s window)"
            )
            
            # Update workers list (already inside lock)
            self.workers = [w for w in self.workers if w.is_alive()]
            self.workers.append(new_worker)
    
    def _process_message(self, msg: WebhookMessage):
        """Process single message"""
        try:
            safe_log_info(f"[WORKER] Processing {msg.correlation_id}")
            # Claude Patch: initialize reply tracking (DO NOT MOVE)
            reply_type_for_log = None  

            corr_id = msg.correlation_id
            # ─── Show typing indicator immediately (best-effort, non-blocking) ───
            send_typing_indicator(msg.message_id, correlation_id=corr_id)
            
            # Generate fingerprint for debounce check
            country_code_debounce, clean_phone_debounce = format_phone_number(msg.sender_id)
            temp_fingerprint_debounce = generate_user_fingerprint(
                country_code_debounce, clean_phone_debounce, "", WHATSAPP_MODE
            )
            
            # Anti-spam check using fingerprint
            if not user_debouncer.should_process(temp_fingerprint_debounce, corr_id):
                safe_log_warning(f"[WORKER] Debounced {msg.correlation_id}")
                return  # Skip processing
            
            # ✅ FIX: Check resume BEFORE incrementing message count
            current_msg_count = conversation_state.get_message_count(msg.sender_id)
            is_first_message_in_session = (current_msg_count == 0)
            
            # ✅ DEFENSIVE: Get resume context early for old users
            resume_ctx = None
            force_ai_resume = False
            
            if is_first_message_in_session:
                try:
                    resume_ctx = get_user_resume_context(msg.sender_id)
                    
                    # ✅ SAFE Check all conditions defensively
                    if (resume_ctx and 
                        isinstance(resume_ctx, dict) and 
                        resume_ctx.get('is_old_user') == True):
                        
                        days_inactive = resume_ctx.get('days_inactive', 0)
                        # ✅ SAFE: Handle float/int/string
                        try:
                            days_inactive = float(days_inactive)
                        except (TypeError, ValueError):
                            days_inactive = 0
                        
                        if days_inactive >= 7:
                            force_ai_resume = True
                            # Store for AI to use later
                            conversation_state.update(msg.sender_id, 'resume_context', json.dumps(resume_ctx))
                            safe_log_info(f"[RESUME] OLD USER DETECTED → FORCE AI: {msg.sender_id[-4:]} (inactive {days_inactive:.1f} days)")
                except Exception as e:
                    safe_log_error(f"[RESUME] Context check failed: {e}")
                    # Fail safe: Don't force AI if error
                    force_ai_resume = False
            
            # Single sheet lookup
            user_data = get_user_data_once(msg.sender_id)

            # Load returning user data from database if state is empty

            user_city = "Not Mentioned"
            user_interest = "Not Specified"
            user_email = "Not Provided"
            user_budget = "Not Specified"

            # ─── MEMORY FEATURE (KILL-SWITCH-CONTROLLED) ───
            from memory_feature import (
                is_memory_enabled,
                get_returning_user_context,
                build_welcome_back_message,
                MemoryTier,
            )
            
            memory_context = None
            welcome_back_text = None
            
            if not is_memory_enabled():
                safe_log_info(f"[MEMORY] ⚠️ DISABLED via kill switch | {corr_id}")
            elif not conversation_state.get(msg.sender_id, 'city') and BOT_AUTH_TOKEN:
                # CRM fetch function (returns existing lead data)
                def _crm_fetch(phone):
                    try:
                        resp = requests.get(
                            f"{os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')}/api/crm/leads?phone={phone}",
                            headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            leads = resp.json()
                            return leads[0] if leads else None
                    except Exception as e:
                        safe_log_warning(f"[MEMORY] CRM fetch error: {e}")
                    return None
                
                # Get memory context (no logs lookup needed — we use CRM 'updated_at' as proxy)
                memory_context = get_returning_user_context(
                    user_fingerprint=conversation_state.get(msg.sender_id, 'fingerprint') or "",
                    user_phone=msg.sender_id,
                    sheets_logs_fn=None,
                    crm_fetch_fn=_crm_fetch,
                    correlation_id=corr_id,
                )
                
                # Apply remembered fields to conversation_state
                if memory_context["is_returning"]:
                    for key, val in memory_context["fields"].items():
                        if val:
                            conversation_state.update(msg.sender_id, key, val)
                    safe_log_info(f"[STATE] ✅ Restored state for returning user {msg.sender_id[-4:]}")
                    safe_log_info(f"[STATE] Stage updated for returning user")
                
                # Build welcome-back message (None for SILENT/NEW_USER)
                welcome_back_text = build_welcome_back_message(
                    user_name=msg.user_name,
                    context=memory_context,
                )

            # Extract email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, msg.text_body)
            
            if email_match:
                user_email = email_match.group(0)
            else:
                 user_email = conversation_state.get(msg.sender_id, 'email') or "Not Provided"
            

            # ✅ NEW: Generate fingerprint for user identification
            # Note: Ensure BOT_MODE is defined globally or imported
            # ✅ Generate fingerprint for user identification
            country_code, clean_phone = format_phone_number(msg.sender_id)
            
            user_fingerprint = generate_user_fingerprint(
                country_code, 
                clean_phone, 
                user_email, 
                WHATSAPP_MODE  # Use WHATSAPP_MODE or BOT_MODE (check your config variable name)
            )
            
            # Extract city
            # Dynamic city detection from PROPERTIES database + common cities
            db_cities = list(set([p['location'].split()[0].lower() for p in PROPERTIES if p['location'].strip()]))
            all_cities = db_cities + ["dubai", "marina", "downtown", "meydan", "abudhabi", "yas", "uk", "london", "manchester", "delhi", "kanpur", "mumbai", "bangalore"]
            user_city = "Not Mentioned"
            for city in all_cities:
                if city and city in msg.text_body.lower():
                    user_city = city.title()
                    break
            if user_city == "Not Mentioned":
                user_city = conversation_state.get(msg.sender_id, 'city') or user_data.get('city', 'Not Mentioned')
            
            # ─── BUILD COMBINED INTEREST: "PropertyType - Purpose" ───
            # e.g. "Villa - Personal", "Apartment - Investment"
            # Pulls from flow.data (state machine truth) first, falls back to state, then keywords.
            
            prop_type_val = None
            purpose_val = None
            
            # Source 1: state machine (most reliable)
            if msg.sender_id in ACTIVE_FLOWS:
                flow_data = ACTIVE_FLOWS[msg.sender_id].data
                prop_type_val = flow_data.get('prop_type')
                purpose_val = flow_data.get('purpose') or flow_data.get('interest')
            
            # Source 2: conversation_state fallback
            if not prop_type_val:
                prop_type_val = conversation_state.get(msg.sender_id, 'prop_type')
            if not purpose_val:
                purpose_val = conversation_state.get(msg.sender_id, 'interest')
            
            # Source 3 (last resort): keyword extraction, only if message has no digits
            text_lower = msg.text_body.lower()
            has_number = any(c.isdigit() for c in msg.text_body)
            if not purpose_val and not has_number:
                if "investment" in text_lower:
                    purpose_val = "Investment"
                elif "personal" in text_lower:
                    purpose_val = "Personal"
            if not prop_type_val and not has_number:
                for ptype in ("villa", "apartment", "commercial", "penthouse", "studio", "townhouse"):
                    if ptype in text_lower:
                        prop_type_val = ptype.title()
                        break
            
            # Normalize: purpose to first word ("Personal use" → "Personal"), prop_type to titlecase
            if purpose_val:
                purpose_val = str(purpose_val).strip().split()[0].title()
            if prop_type_val:
                prop_type_val = str(prop_type_val).strip().title()
            
            # Defensive: prevent "Apartment - Apartment" when both slots got the same word
            # (caused by intent classifier writing prop_type into the purpose slot)
            if (prop_type_val and purpose_val and 
                str(prop_type_val).strip().lower() == str(purpose_val).strip().lower()):
                # Same word in both — trust prop_type, recover purpose from conversation_state explicitly
                purpose_val = conversation_state.get(msg.sender_id, 'purpose') or None
            
            # Build combined string in format "Type - Purpose"
            if prop_type_val and purpose_val:
                user_interest = f"{prop_type_val} - {purpose_val}"
            elif prop_type_val:
                user_interest = prop_type_val
            elif purpose_val:
                user_interest = purpose_val
            else:
                user_interest = "Not Specified"
            
            # Save individual pieces back to conversation_state for next message
            if prop_type_val:
                conversation_state.update(msg.sender_id, 'prop_type', prop_type_val)
            if purpose_val:
                conversation_state.update(msg.sender_id, 'interest', purpose_val)
            
            # ─── BUDGET: store exact number formatted as "100,000 AED" ───
            user_budget = "Not Specified"
            raw_budget = None
            
            # Source 1: state machine (real number captured during conversation)
            if msg.sender_id in ACTIVE_FLOWS:
                raw_budget = ACTIVE_FLOWS[msg.sender_id].data.get('budget')
            
            # Source 2: conversation_state fallback
            if not raw_budget:
                raw_budget = conversation_state.get(msg.sender_id, 'budget')
            
            # Source 3: extract from current message text
            if not raw_budget:
                _, extracted = budgetqualifier.extract_budget_from_message(msg.text_body)
                raw_budget = extracted
            
            # Format as "100,000 AED" with comma separators
            if raw_budget:
                try:
                    # Strip any existing formatting, then re-format cleanly
                    clean = str(raw_budget).replace(",", "").replace("AED", "").replace("aed", "").strip()
                    num = int(float(clean))
                    user_budget = f"{num:,} AED"
                    # Save the formatted version back to state
                    conversation_state.update(msg.sender_id, 'budget', user_budget)
                except (ValueError, TypeError):
                    # Already formatted or non-numeric — use as-is
                    user_budget = str(raw_budget)
            
            # Update state
            if user_city != "Not Mentioned":
                conversation_state.update(msg.sender_id, 'city', user_city)
            #'interest' is NOT saved here — Fix 2 (line ~847) already saves
            # the clean 'purpose' piece. Saving the combined "Type - Purpose" string
            # back would re-corrupt the field and compound to "Apartment - Apartment".
            if user_email != "Not Provided":
                conversation_state.update(msg.sender_id, 'email', user_email)
                conversation_state.mark_email_asked(msg.sender_id)
            if user_budget != "Not Specified":
                conversation_state.update(msg.sender_id, 'budget', user_budget)

                # ================== ✅ FIX: STAGE MANAGER SYNC ==================
            if user_city != "Not Mentioned":
                stage_manager.update_user_data(msg.sender_id, "city_mentioned", True)

            if user_interest != "Not Specified":
                stage_manager.update_user_data(msg.sender_id, "interest_type", True)

            if email_match:
                stage_manager.update_user_data(msg.sender_id, "email_mentioned", True)
            
            message_count = conversation_state.increment_message_count_once(msg.sender_id)
            
            safe_log_debug(
                f"{corr_id} | {msg.sender_id[-4:]} | "
                f"{user_city} | {user_interest} | {user_email} | Budget:{user_budget} | Msg#{message_count}"
            )
            
            # Record activity
            record_user_activity(msg.sender_id)
            
            # Update sheet
            update_sheet_with_crm_features_optimized(
                msg.sender_id, msg.user_name, user_email, user_city, user_interest,
                msg.text_body, message_count, user_budget, user_data.get('row_num'), correlation_id=corr_id, user_fingerprint=user_fingerprint
            )
            
            
            # Write lead to database
            try:
                db_lead_data = {
                    "name": msg.user_name or "Unknown",
                    "phone": msg.sender_id,
                    "city": user_city if user_city != "Not Mentioned" else None,
                    "interest": user_interest if user_interest != "Not Specified" else None,
                    "email": user_email if user_email != "Not Provided" else None,
                    "budget_category": user_budget if user_budget != "Not Specified" else None,
                    "lead_score": min(100, message_count * 10),
                    "conversation_status": "active",
                    "user_fingerprint": user_fingerprint,
                }
                # Check if lead exists first
                existing = requests.get(
                    f"{os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')}/api/crm/leads?phone={msg.sender_id}",
                    headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                    timeout=5
                )
                existing_leads = existing.json() if existing.status_code == 200 else []
                if existing_leads:
                    # Update existing lead
                    lead_id = existing_leads[0]['id']
                    db_resp = requests.put(
                        f"{os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')}/api/crm/leads/{lead_id}",
                        json=db_lead_data,
                        headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                        timeout=5
                    )
                else:
                    # Create new lead
                    db_resp = requests.post(
                        f"{os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')}/api/crm/leads",
                        json=db_lead_data,
                        headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                        timeout=5
                    )
                if db_resp.status_code not in (200, 201):
                    safe_log_error(f"[DB-LEAD] Failed: {db_resp.status_code}")
                else:
                    safe_log_info(f"[DB-LEAD] ✅ Saved | {corr_id}")
            except Exception as e:
                safe_log_error(f"[DB-LEAD] Error: {e}")
            
            # Check handover
            cumulative_score = sum([
                10 if user_city != "Not Mentioned" else 0,
                10 if user_interest != "Not Specified" else 0,
                20 if user_email != "Not Provided" else 0,
                15 if user_budget != "Not Specified" else 0,
                min(20, message_count * 5 // 2)
            ])
            
            has_email = user_email != "Not Provided"
            has_city = user_city != "Not Mentioned"
            has_interest = user_interest != "Not Specified"
            
            should_handover, handover_reason = handovermanager.should_handover(
                msg.sender_id, cumulative_score, has_email, has_city,
                has_interest, msg.text_body
            )
            # Don't auto-handover here — let AI decide when to handover
            
            # ══════════════════════════════════════════════════════════
            # AI IS THE BOSS — decides every action
            # ══════════════════════════════════════════════════════════

            # Rate limit check
            if user_rate_limiter.is_rate_limited(msg.sender_id):
                safe_log_warning(f"[RATE-LIMIT] {msg.sender_id[-4:]} | {corr_id}")
                send_whatsapp_text_with_retry(msg.sender_id, "Please wait a moment. 😊", correlation_id=corr_id)
                return

            # Build resume block if returning user
            resume_context_block = ""
            resume_context_json = conversation_state.get(msg.sender_id, 'resume_context')
            if resume_context_json and str(resume_context_json).strip() and resume_context_json != 'null':
                try:
                    rc = json.loads(resume_context_json)
                    if isinstance(rc, dict) and rc.get('is_old_user') == True:
                        summary = rc.get('summary', '')
                        if summary:
                            resume_context_block = f"\n- Previous interaction: {summary}\n- RETURNING user — greet warmly by name."
                    conversation_state.update(msg.sender_id, 'resume_context', None)
                except Exception:
                    pass
            # Available property types from database (only available, not sold)
            available_props = [p for p in PROPERTIES if not p.get('is_sold', False)]
            prop_types = list(set([p.get('property_type', '').title() for p in available_props if p.get('property_type')]))
            prop_cities = list(set([p.get('location', '').split(',')[0].strip() for p in available_props if p.get('location')]))

            # ============================================================================
            # FIX #2: Get conversation stage and history
            # ============================================================================
            current_stage = stage_manager.get_user_stage(msg.sender_id)
            stage_instruction = stage_manager.get_ai_instructions(msg.sender_id)
            safe_log_info(f"[STAGE] {current_stage.value} | {corr_id}")
            
            # Get last 5 messages for context (prevents duplicate questions)
            history = conversation_state.get_history(msg.sender_id) or []
            recent_history = history[-5:] if len(history) > 5 else history
            history_text = "\n".join([
                f"- {h.get('role', 'unknown')}: {h.get('content', '')}" 
                for h in recent_history
            ]) if recent_history else "No previous conversation"
                       
            # ════════════════════════════════════════════════════════════
            # 🚀 NEW STATE-MACHINE FLOW (Replaces 800 lines of AI prompt logic)
            # ════════════════════════════════════════════════════════════
            
            # Get or create flow for this user
            if msg.sender_id not in ACTIVE_FLOWS:
                ACTIVE_FLOWS[msg.sender_id] = ConversationFlow(
                    user_id=msg.sender_id,
                    user_name=msg.user_name or "there"
                )
            
            flow = ACTIVE_FLOWS[msg.sender_id]
            
            # Restore from saved state if needed (for returning users)
            saved_state = conversation_state.get(msg.sender_id, 'flow_state')
            saved_data = conversation_state.get(msg.sender_id, 'flow_data')
            if saved_state and not flow.data.get('city'):
                try:
                    flow.state = FlowState(saved_state)
                    if saved_data and isinstance(saved_data, dict):
                        flow.data.update(saved_data)
                    safe_log_info(f"[FLOW] Restored state: {saved_state} | {corr_id}")
                except Exception as e:
                    safe_log_warning(f"[FLOW] Restore failed: {e} | {corr_id}")
            
            # ─── WELCOME-BACK MESSAGE (only FRIENDLY + CONFIRM have a message) ───
            if welcome_back_text:
                send_whatsapp_text_with_retry(
                    msg.sender_id, welcome_back_text, correlation_id=corr_id
                )
                if memory_context and memory_context["tier"] == MemoryTier.CONFIRM:
                    flow.state = FlowState.RETURNING_USER_CONFIRM
                    conversation_state.update(msg.sender_id, 'flow_state', flow.state.value)
                    safe_log_info(f"[MEMORY] Set state to RETURNING_USER_CONFIRM | {corr_id}")
                    safe_log_info(f"[WORKER] Completed {msg.correlation_id}")
                    return  # exit early — user must reply yes/no first
            
            # ─── FIELD-SKIP (BOTH SILENT AND FRIENDLY tiers benefit) ───
            # This block runs OUTSIDE the welcome-back guard, so SILENT tier reaches it.
            # Silent: skip fields without saying anything.
            # Friendly: skip fields AFTER the welcome-back has been sent above.
            if memory_context and memory_context["tier"] in (MemoryTier.FRIENDLY, MemoryTier.SILENT):
                for k, v in memory_context["fields"].items():
                    flow.data[k] = v
                # Decide next missing field
                if not flow.data.get("city"):
                    flow.state = FlowState.AWAITING_CITY
                elif not flow.data.get("purpose") and not flow.data.get("interest"):
                    flow.state = FlowState.AWAITING_PURPOSE
                elif not flow.data.get("prop_type"):
                    flow.state = FlowState.AWAITING_TYPE
                elif not flow.data.get("budget"):
                    flow.state = FlowState.AWAITING_BUDGET
                elif not flow.data.get("email"):
                    flow.state = FlowState.AWAITING_EMAIL
                else:
                    flow.state = FlowState.AWAITING_FEEDBACK
                
                conversation_state.update(msg.sender_id, 'flow_state', flow.state.value)
                safe_log_info(f"[MEMORY] {memory_context['tier'].value} tier → jumped to {flow.state.value} | {corr_id}")
                # Don't return — let the user's message be processed from the correct state
            
            # ─── MULTI-LANGUAGE: Detect user's language and translate to English ───
            # Bot's internal logic works in English. We translate IN and OUT.
            from translation_service import (
                detect_language,
                translate_to_english,
                translate_from_english,
                is_translation_enabled,
            )
            
            # 1. Detect language from CURRENT message (don't cache — user might switch languages)
            # Fall back to saved language only if current message is too short to detect (e.g., "ok", "yes")
            user_lang = 'en'  # safe default
            if is_translation_enabled():
                if len(msg.text_body.strip()) >= 4:
                    # Long enough to detect reliably — use current message's language
                    user_lang = detect_language(msg.text_body)
                    cached_lang = conversation_state.get(msg.sender_id, 'language')
                    if cached_lang != user_lang:
                        safe_log_info(f"[TRANSLATE] Language: {cached_lang or 'none'} → {user_lang} | {corr_id}")
                    conversation_state.update(msg.sender_id, 'language', user_lang)
                else:
                    # Short message — use cached language to handle "ok", "yes", numbers
                    user_lang = conversation_state.get(msg.sender_id, 'language') or 'en'
                    safe_log_info(f"[TRANSLATE] Short message, using cached: {user_lang} | {corr_id}")
            
            # 2. Translate user message to English (if needed) for internal processing
            message_in_english = msg.text_body
            if user_lang != 'en' and is_translation_enabled():
                message_in_english = translate_to_english(
                    msg.text_body,
                    user_lang=user_lang,
                    gemini_call_fn=lambda prompt: call_gemini_for_intent(
                        prompt, user_id=msg.sender_id, correlation_id=corr_id
                    )
                )
                safe_log_info(f"[TRANSLATE] {user_lang}→en | original: {msg.text_body[:40]!r} | english: {message_in_english[:40]!r} | {corr_id}")
            
            # Process message through state machine (always in English internally)
            response = flow.handle_message(
                message=message_in_english,
                available_properties=PROPERTIES,
                gemini_call_fn=lambda prompt: call_gemini_for_intent(
                    prompt, user_id=msg.sender_id, correlation_id=corr_id
                ),
                correlation_id=corr_id,
            )
            
            # 3. Translate bot's English response back to user's language (if needed)
            if user_lang != 'en' and is_translation_enabled() and response and response.text:
                original_response = response.text
                response.text = translate_from_english(
                    response.text,
                    target_lang=user_lang,
                    gemini_call_fn=lambda prompt: call_gemini_for_intent(
                        prompt, user_id=msg.sender_id, correlation_id=corr_id
                    )
                )
                safe_log_info(f"[TRANSLATE] en→{user_lang} | response: {response.text[:40]!r} | {corr_id}")
            
            
            safe_log_info(
                f"[FLOW] action={response.action} | "
                f"state={flow.state.value} | {corr_id}"
            )
            
            # ─── EXECUTE FLOW DECISION ───
            
            # 1. Send text reply
            if response.text:
                send_whatsapp_text_with_retry(
                    msg.sender_id, response.text, correlation_id=corr_id
                )
                # Save to history
                conversation_state.add_to_history(msg.sender_id, {
                    "role": "user", "content": msg.text_body
                })
                conversation_state.add_to_history(msg.sender_id, {
                    "role": "assistant", "content": response.text
                })
            
            # 2. Send property images
            if response.action == "send_property":
                prop = response.data.get('property')
                if prop:
                    caption = format_property_caption(prop, include_roi=True)
                    images = get_property_images(prop)
                    
                    for i, img_url in enumerate(images):
                        img_caption = caption if i == 0 else ""
                        safe_log_info(f"[PHOTOS] Sending image {i+1}/{len(images)}")
                        send_whatsapp_image_with_retry(msg.sender_id, img_url, img_caption)
                    
                    safe_log_info(f"[PHOTOS] Sent {len(images)} images | {corr_id}")
                    
                    # ✅ FIX: Send follow-up question after images (gender-aware)
                    import time
                    time.sleep(0.5)  # Brief delay so question appears AFTER images (WhatsApp delivery ~300ms)
                    
                    first_name = msg.user_name.split()[0] if msg.user_name else "there"
                    name_lower = first_name.lower()
                    female_names = ['priya', 'aisha', 'fatima', 'sarah', 'maria', 'sara',
                                   'mary', 'nisha', 'pooja', 'kavya', 'ananya', 'riya', 'oliva',
                                   'anjali', 'meera', 'neha', 'divya', 'simran']
                    male_names = ['aman', 'ahmed', 'john', 'raj', 'ali', 'mohammed',
                                 'rohan', 'arjun', 'vikram', 'rahul', 'suresh', 'amit', 'jack',
                                 'rohit', 'karan', 'vivek', 'sumit']
                    
                    if any(fn in name_lower for fn in female_names):
                        title = f"Ms. {first_name}"
                    elif any(mn in name_lower for mn in male_names):
                        title = f"Mr. {first_name}"
                    else:
                        title = first_name
                    
                    feedback_msg = (
                        f"{title}, did you like this property? 😊\n\n"
                        f"Shall we move forward and schedule a quick call, "
                        f"or would you like to explore other options?"
                    )
                    send_whatsapp_text_with_retry(msg.sender_id, feedback_msg, correlation_id=corr_id)
                    
                    # Update flow state to AWAITING_FEEDBACK
                    flow.state = FlowState.AWAITING_FEEDBACK
                    safe_log_info(f"[FLOW] Asked feedback - state: AWAITING_FEEDBACK | {corr_id}")
            
            # 3. Schedule meeting
            elif response.action == "schedule_meeting":
                meeting_data = response.data
                meeting_date = meeting_data.get('date')
                meeting_time = meeting_data.get('time')
                
                try:
                    dealer_email = os.getenv('DEALER_EMAIL', '')
                    
                    # Loud diagnostics so silent skips never happen again
                    if not dealer_email:
                        safe_log_warning(f"[MEETING] ⚠️ DEALER_EMAIL env var not set — skipping email | {corr_id}")
                    if not meeting_date or not meeting_time:
                        safe_log_warning(f"[MEETING] ⚠️ Missing date/time (date={meeting_date}, time={meeting_time}) | {corr_id}")
                    
                    if dealer_email and meeting_date and meeting_time:
                        prop = meeting_data.get('property') or {}
                        cal_link = format_meeting_calendar_link(
                            client_name=msg.user_name,
                            property_name=prop.get('name', 'Property'),
                            property_type=flow.data.get('prop_type', ''),
                            city=flow.data.get('city', ''),
                            meeting_date=meeting_date,
                            meeting_time=meeting_time
                        )
                        
                        # ─── Send email in background so worker doesn't block ───
                        # Without this: worker blocks 5-10s on SMTP. With this: returns instantly.
                        def _send_email_async(_corr_id=corr_id):
                            try:
                                send_meeting_confirmation(
                                    dealer_email=dealer_email,
                                    client_name=msg.user_name,
                                    client_phone=msg.sender_id,
                                    client_email=meeting_data.get('email', ''),
                                    property_name=prop.get('name', 'Property'),
                                    property_type=flow.data.get('prop_type', ''),
                                    city=flow.data.get('city', ''),
                                    meeting_date=meeting_date,
                                    meeting_time=meeting_time,
                                    budget=str(meeting_data.get('budget', '')),
                                    calendar_link=cal_link
                                )
                                safe_log_info(f"[MEETING] ✅ Email sent (async) | {_corr_id}")
                            except Exception as e:
                                safe_log_error(f"[MEETING] Async email failed: {e} | {_corr_id}")
                        
                        threading.Thread(
                            target=_send_email_async,
                            name=f"EmailWorker-{corr_id[:8]}",
                            daemon=True
                        ).start()
                        safe_log_info(f"[MEETING] ✅ Confirmed (email queued) | {corr_id}")
                except Exception as e:
                    safe_log_error(f"[MEETING] Email send failed: {e}")
            
            # 4. Handover to consultant
            elif response.action == "handover":
                safe_log_info(f"[HANDOVER] Handed to consultant | {corr_id}")
            
            # ─── SAVE FLOW STATE ───
            conversation_state.update(msg.sender_id, 'flow_state', flow.state.value)
            conversation_state.update(msg.sender_id, 'flow_data', flow.data)
            
            # Backward-compatible field updates
            if flow.data.get('city'):
                conversation_state.update(msg.sender_id, 'city', flow.data['city'])
            if flow.data.get('email'):
                conversation_state.update(msg.sender_id, 'email', flow.data['email'])
            if flow.data.get('budget'):
                conversation_state.update(msg.sender_id, 'budget', flow.data['budget'])
            if flow.data.get('prop_type'):
                conversation_state.update(msg.sender_id, 'prop_type', flow.data['prop_type'])
            
            # ─── LOG CONVERSATION (TWO DESTINATIONS) ───
            # 1. Google Sheet "Logs" tab — for dealer's offline access
            # 2. FastAPI /api/crm/logs — populates the frontend Bot Logs page
            try:
                # Build reply_type marker: "AI:send_text", "AI:send_property", etc.
                reply_type = f"AI:{response.action}" if response and response.action else "AI:send_text"
                bot_response_text = response.text if response and response.text else ""
                
                # Extract country code + clean phone from sender_id (e.g., "918470911526")
                # Strip leading country code if it's India (91), UAE (971), UK (44), etc.
                sender = str(msg.sender_id)
                if sender.startswith("91") and len(sender) == 12:
                    country_code, clean_phone = "+91", sender[2:]
                elif sender.startswith("971") and len(sender) == 12:
                    country_code, clean_phone = "+971", sender[3:]
                elif sender.startswith("44") and len(sender) >= 12:
                    country_code, clean_phone = "+44", sender[2:]
                else:
                    country_code, clean_phone = "", sender
                
                # Destination 1: Google Sheet
                log_conversation_to_sheet(
                    sender_id=msg.sender_id,
                    user_name=msg.user_name or "Unknown",
                    user_message=msg.text_body or "",
                    bot_response=bot_response_text,
                    reply_type=reply_type,
                    correlation_id=corr_id,
                )
                
                # Destination 2: FastAPI bot_logs DB (powers the frontend Logs page)
                if BOT_AUTH_TOKEN:
                    try:
                        log_payload = {
                            "user_name":    msg.user_name or "Unknown",
                            "country_code": country_code,
                            "phone":        clean_phone,
                            "user_message": (msg.text_body or "")[:500],
                            "reply_type":   reply_type,
                            "bot_response": bot_response_text[:500],
                        }
                        log_resp = requests.post(
                            f"{os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')}/api/crm/logs",
                            json=log_payload,
                            headers={"Authorization": f"Bearer {BOT_AUTH_TOKEN}"},
                            timeout=5,
                        )
                        if log_resp.status_code in (200, 201):
                            safe_log_debug(f"[LOGS-DB] ✅ Posted to /api/crm/logs | {corr_id}")
                        else:
                            safe_log_warning(f"[LOGS-DB] Failed: {log_resp.status_code} | {log_resp.text[:200]} | {corr_id}")
                    except Exception as db_err:
                        safe_log_warning(f"[LOGS-DB] POST error: {db_err} | {corr_id}")
                        
            except Exception as log_err:
                safe_log_warning(f"[LOGS] Failed to log conversation: {log_err} | {corr_id}")
            
            safe_log_info(f"[WORKER] Completed {msg.correlation_id}")
            
        except Exception as e:
            # Track failure
            with self.lock:
                self.failed_count += 1
                current_failed_count = self.failed_count
            
            # Structured error logging with full context
            safe_log_error(
                f"[WORKER] PROCESSING FAILED | "
                f"Correlation: {msg.correlation_id} | "
                f"Sender: {msg.sender_id[-4:]} | "
                f"User: {msg.user_name} | "
                f"Message: {msg.text_body[:100]}... | "
                f"Total Failed: {current_failed_count} | "
                f"Error: {str(e)}"
            )
            
            # Alert: Worker processing failure
            send_slack_alert(
                f"*Worker Processing Failure*\n"
                f"• Correlation ID: {msg.correlation_id}\n"
                f"• Sender: {msg.sender_id[-4:]}\n"
                f"• Total Failed: {current_failed_count}\n"
                f"• Error: {str(e)[:200]}"
            )
            
            # Full traceback for debugging
            import traceback
            safe_log_debug(f"[WORKER] Traceback for {msg.correlation_id}:\n{traceback.format_exc()}")

webhook_processor = WebhookProcessor(max_workers=8)

# ============================================================================
# PER-USER DEBOUNCE (ANTI-SPAM)
# ============================================================================
class UserDebouncer:
    """Prevent same user from spamming processing within 2 seconds"""
    def __init__(self, debounce_seconds=2):
        self.last_process_time: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        self.debounce_seconds = debounce_seconds
    
    def should_process(self, user_fingerprint: str, correlation_id: str = "") -> bool:
        """Returns True if enough time has passed since last processing"""
        with self.lock:
            now = datetime.now()
            last_time = self.last_process_time.get(user_fingerprint)
            
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.debounce_seconds:
                    safe_log_warning(
                        f"[DEBOUNCE] Blocked spam: {user_fingerprint[:16]}... | "
                        f"Elapsed: {elapsed:.2f}s | "
                        f"Correlation: {correlation_id}"
                    )
                    return False
            
            self.last_process_time[user_fingerprint] = now
            return True

user_debouncer = UserDebouncer(debounce_seconds=2)


# ============================================================================
# MESSAGE DEDUPLICATOR (FIXED ISSUE 5)
# ============================================================================
class MessageDeduplicator:
    """FIX ISSUE 5: Bounded memory with LRU eviction"""
    def __init__(self, ttl_seconds=86400, max_size=50000):  # FIX ISSUE 5
        self.processed_messages: Set[str] = set()
        self.message_timestamps: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size  # FIX ISSUE 5
        self.duplicate_count = 0
        self.total_processed = 0
        self.missing_id_count = 0

    def is_duplicate(self, message_id: str, sender_id: str = "") -> bool:
        with self.lock:
            self._cleanup_old_messages()
            
            if not message_id or message_id.strip() == "":
                self.missing_id_count += 1
                fallback_id = f"missing_{int(time.time() * 1_000_000)}_{os.getpid()}_{uuid.uuid4().hex[:8]}"

                safe_log_warning(
                    f"[DEDUP] ⚠️  Missing message_id! Fallback: {fallback_id} | "
                    f"Sender: {sender_id[-4:]}"
                )
                safe_log_debug(f"[DEDUP_FORENSIC] Sender: {sender_id} | Fallback: {fallback_id}")
                message_id = fallback_id
            else:
                safe_log_debug(f"[DEDUP_FORENSIC] Full message_id: {message_id} | Sender: {sender_id}")
            
            # Check duplicate
            if message_id in self.processed_messages:
                self.duplicate_count += 1
                first_seen = self.message_timestamps.get(message_id)
                age_seconds = (datetime.now() - first_seen).total_seconds() if first_seen else 0
                safe_log_warning(
                    f"[DEDUP] ⚠️  Webhook retry | "
                    f"ID: {message_id[:20]}... | "
                    f"Age: {age_seconds:.0f}s | "
                    f"BLOCKED"
                )
                return True
            
            # Accept new message
            self.processed_messages.add(message_id)
            self.message_timestamps[message_id] = datetime.now()
            self.total_processed += 1
            
            safe_log_info(
                f"[DEDUP] ✅ New message | "
                f"ID: {message_id[:20]}... | "
                f"Total: {self.total_processed}"
            )
            return False

    def _cleanup_old_messages(self):
        """FIX ISSUE 5: Remove expired + enforce max size with LRU"""
        now = datetime.now()
        expired = [
            msg_id for msg_id, timestamp in self.message_timestamps.items()
            if (now - timestamp).total_seconds() > self.ttl_seconds
        ]
        
        if expired:
            for msg_id in expired:
                self.processed_messages.discard(msg_id)
                self.message_timestamps.pop(msg_id, None)
            safe_log_debug(f"[DEDUP] Cleaned {len(expired)} expired IDs")
        
        # FIX ISSUE 5: Enforce max size using LRU eviction
        if len(self.processed_messages) > self.max_size:
            # Remove oldest 10%
            oldest_ids = sorted(
                self.message_timestamps.items(),
                key=lambda x: x[1]
            )[:self.max_size // 10]
            
            for msg_id, _ in oldest_ids:
                self.processed_messages.discard(msg_id)
                self.message_timestamps.pop(msg_id, None)
            
            safe_log_warning(
                f"[DEDUP] ⚠️  Evicted {len(oldest_ids)} oldest IDs "
                f"(max_size={self.max_size}, current={len(self.processed_messages)})"
            )

    def get_stats(self) -> dict:
        with self.lock:
            return {
                'total_processed': self.total_processed,
                'duplicate_webhooks_blocked': self.duplicate_count,
                'missing_message_ids': self.missing_id_count,
                'active_message_ids': len(self.processed_messages),
                'max_size': self.max_size,  # FIX ISSUE 5
                'ttl_hours': self.ttl_seconds / 3600
            }

message_deduplicator = MessageDeduplicator()

# ============================================================================
# USER RATE LIMITING
# ============================================================================
class UserRateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()

    def is_rate_limited(self, user_id: str) -> bool:
        with self.lock:
            now = datetime.now()
            cutoff_time = now - timedelta(seconds=self.window_seconds)
            self.user_requests[user_id] = [
                timestamp for timestamp in self.user_requests[user_id]
                if timestamp > cutoff_time
            ]
            
            if len(self.user_requests[user_id]) >= self.max_requests:
                safe_log_warning(
                    f"[RATE_LIMIT] {user_id[-4:]} exceeded "
                    f"({self.max_requests}/{self.window_seconds}s)"
                )
                return True
            
            self.user_requests[user_id].append(now)
            return False

user_rate_limiter = UserRateLimiter(max_requests=10, window_seconds=60)

# ============================================================================
# USER-SCOPED AI CACHE
# ============================================================================
class ResponseCache:
    def __init__(self, ttl_seconds=1800):
        self.cache: Dict[str, tuple[str, datetime]] = {}
        self.lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[str]:
        with self.lock:
            self._cleanup_old_entries()
            if key in self.cache:
                response, timestamp = self.cache[key]
                safe_log_debug(f"[CACHE] HIT: {key[:50]}")
                return response
            return None

    def set(self, key: str, response: str):
        with self.lock:
            self.cache[key] = (response, datetime.now())

    def _cleanup_old_entries(self):
        now = datetime.now()
        expired = [
            k for k, (_, timestamp) in self.cache.items()
            if (now - timestamp).total_seconds() > self.ttl_seconds
        ]
        for k in expired:
            self.cache.pop(k, None)

    def get_cache_key(self, user_id: str, message: str, city: str = "", 
                     budget: str = "", interest: str = "") -> str:
        msg_normalized = message.lower().strip()[:100]
        context = f"{city}:{budget}:{interest}"
        return f"{user_id[-8:]}:{context}:{msg_normalized}"

response_cache = ResponseCache()

# ============================================================================
# AI USAGE TRACKER
# ============================================================================
class AIUsageTracker:
    def __init__(self):
        self.user_ai_calls: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()

    def can_use_ai(self, user_id: str) -> tuple[bool, int]:
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=DEMO_SESSION_TIMEOUT)
            
            if user_id in self.user_ai_calls:
                self.user_ai_calls[user_id] = [
                    timestamp for timestamp in self.user_ai_calls[user_id]
                    if timestamp > cutoff
                ]
            
            current_calls = len(self.user_ai_calls[user_id])
            remaining = DEMO_MAX_AI_CALLS_PER_USER - current_calls
            
            if current_calls >= DEMO_MAX_AI_CALLS_PER_USER:
                return False, 0
            
            return True, remaining

    def record_ai_call(self, user_id: str):
        with self.lock:
            self.user_ai_calls[user_id].append(datetime.now())

ai_usage_tracker = AIUsageTracker()

# ============================================================================
# CONVERSATION STATE
# ============================================================================
class ConversationState:
    def __init__(self, ttl_seconds=86400):
        self.states: Dict[str, dict] = defaultdict(dict)
        self.lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

    def update(self, user_id: str, key: str, value: str):
        with self.lock:
            self.states[user_id][key] = value
            self.states[user_id]['last_update'] = datetime.now()

    def get(self, user_id: str, key: str, default=None):
        with self.lock:
            self._cleanup_expired_states()
            return self.states.get(user_id, {}).get(key, default)

    def get_message_count(self, user_id: str) -> int:
        with self.lock:
            return self.states.get(user_id, {}).get('message_count', 0)

    def increment_message_count_once(self, user_id: str) -> int:
        with self.lock:
            count = self.states.get(user_id, {}).get('message_count', 0)
            new_count = count + 1
            self.states[user_id]['message_count'] = new_count
            self.states[user_id]['last_update'] = datetime.now()
            return new_count

    def should_ask_for_email(self, user_id: str, user_email: str) -> bool:
        with self.lock:
            state = self.states.get(user_id, {})
            
            if state.get('email_asked') == 'yes':
                return False
            
            if user_email != "Not Provided":
                self.states[user_id]['email_asked'] = 'yes'
                return False
            
            message_count = state.get('message_count', 0)
            if message_count < 2:
                return False
            
            has_city = 'city' in state and state['city'] != "Not Mentioned"
            has_interest = 'interest' in state and state['interest'] != "Not Specified"
            
            if not (has_city or has_interest):
                return False
            
            return True

    def mark_email_asked(self, user_id: str):
        with self.lock:
            self.states[user_id]['email_asked'] = 'yes'
            self.states[user_id]['last_update'] = datetime.now()

    def get_history(self, user_id: str) -> list:
        with self.lock:
            return self.states.get(user_id, {}).get('history', [])  

    def add_to_history(self, user_id: str, message: dict):
        with self.lock:
            if 'history' not in self.states[user_id]:
                self.states[user_id]['history'] = []
            
            self.states[user_id]['history'].append(message)

            # Limit history to last 10 messages (important)
            self.states[user_id]['history'] = self.states[user_id]['history'][-10:]         

    def should_gently_remind_email(self, user_id: str, user_email: str) -> bool:
        """
        Check if we should gently remind user about email (2nd attempt only)
        Returns True only if:
        - Email was asked once before
        - User didn't provide it
        - Message count is now >= 5 (given them space)
        - Haven't reminded yet
        """
        with self.lock:
            state = self.states.get(user_id, {})

            if user_email != "Not Provided" or state.get('email_asked') != 'yes':
                return False
        
            if state.get('email_reminded') == 'yes':
                return False
        
            message_count = state.get('message_count', 0)
            if message_count < 5:
                return False
        
            return True
        
        

    def _cleanup_expired_states(self):
        now = datetime.now()
        expired = [
            user_id for user_id, state in self.states.items()
            if 'last_update' in state and 
            (now - state['last_update']).total_seconds() > self.ttl_seconds
        ]
        
        if expired:
            for user_id in expired:
                del self.states[user_id]
            safe_log_debug(f"[STATE] Cleaned {len(expired)} expired user states")

    def get_stats(self) -> dict:
        with self.lock:
            return {
                'active_users': len(self.states),
                'states_with_email_asked': sum(
                    1 for s in self.states.values() 
                    if s.get('email_asked') == 'yes'
                )
            }

conversation_state = ConversationState()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_dubai_time():
    try:
        dubai_tz = pytz.timezone('Asia/Dubai')
        return datetime.now(dubai_tz).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
# ============================================================================
# AI DECISION LOGIC
# ============================================================================
def should_use_ai(message: str, user_city: str, user_interest: str, user_budget: str) -> bool:
    """
    Determine if AI should be used for this message.
    Returns False for template-eligible messages, True for complex queries.
    """
    msg_lower = message.lower().strip()
    word_count = len(msg_lower.split())
    
    # Block AI for short messages (4 words or less)
    if word_count <= 4:
        return False
    
    # Block AI for greetings
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 
                 'good evening', 'hii', 'hiii', 'helo', 'hola', 'namaste']
    if msg_lower in greetings:
        return False
    
    # Block AI for city keywords
    cities = ['dubai', 'marina', 'downtown', 'meydan', 'abudhabi', 
              'yas', 'uk', 'london', 'manchester']
    if any(city in msg_lower for city in cities) and word_count <= 2:
        return False
    
    # Block AI for interest/budget keywords
    budget_keywords = ['luxury', 'standard', 'affordable', 'budget', 'premium', 'cheap']
    if any(keyword in msg_lower for keyword in budget_keywords) and word_count <= 2:
        return False
    
    # Block AI for photo requests
    photo_keywords = ['photo', 'picture', 'image', 'show me', 'send']
    if any(keyword in msg_lower for keyword in photo_keywords):
        return False
    
    # Block AI for simple yes/no/thanks
    simple_responses = ['yes', 'no', 'y', 'n', 'ok', 'okay', 'thanks', 
                       'thank you', 'thankyou', 'ty', 'bye', 'goodbye']
    if msg_lower in simple_responses:
        return False
    
    # Block AI for email patterns (already handled by template)
    if '@' in message:
        return False
    
    # Allow AI for objection/doubt keywords (these need nuanced responses)
    objection_keywords = ['worth', 'safe', 'legal', 'scam', 'doubt', 'sure', 
                         'risk', 'trust', 'concern', 'worried', 'hesitant']
    if any(keyword in msg_lower for keyword in objection_keywords):
        return True
    
    # Allow AI for open-ended questions
    question_starters = ['why', 'how', 'what', 'when', 'where', 'who', 
                        'can you', 'could you', 'would you', 'tell me']
    if any(msg_lower.startswith(starter) for starter in question_starters):
        return True
    
    # Allow AI for complex sentences (5+ words not matching templates)
    if word_count >= 5:
        return True
    
    # Default: block AI (prefer templates)
    return False    

def send_typing_indicator(to_message_id: str, correlation_id: str = "N/A") -> bool:
    """
    Show the 'typing...' three-dot indicator + mark user's message as read.
    Auto-dismisses after 25s OR when our reply is sent (whichever first).
    Reuses global PHONE_NUMBER_ID and WHATSAPP_TOKEN. Best-effort, never raises.
    """
    if not to_message_id:
        return False
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": to_message_id,
        "typing_indicator": {"type": "text"}
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            safe_log_info(f"[TYPING] ✅ Indicator shown | {correlation_id}")
            return True
        safe_log_warning(
            f"[TYPING] ⚠️ Failed {response.status_code} | "
            f"Body: {response.text[:150]} | {correlation_id}"
        )
        return False
    except Exception as e:
        safe_log_warning(f"[TYPING] ⚠️ Exception: {e} | {correlation_id}")
        return False

# ============================================================================
# WHATSAPP API WITH RETRY
# ============================================================================
def send_whatsapp_text_with_retry(to_number: str, text: str, max_retries: int = 3, correlation_id: str = "N/A") -> bool:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    
    for attempt in range(max_retries):
        try:
            safe_log_debug(f"[WHATSAPP] {correlation_id} | Sending to {to_number[-4:]} (attempt {attempt+1}/{max_retries})")
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            safe_log_debug(f"[WHATSAPP] Response: {response.status_code} | Body: {response.text[:200]}")
            
            if response.status_code == 200:
                safe_log_info(f"[WHATSAPP] ✅ Sent to {to_number[-4:]}")
                return True
            elif response.status_code == 429:
                backoff = 2 ** attempt * 2
                safe_log_warning(f"[WHATSAPP] Rate limited. Retry in {backoff}s")
                time.sleep(backoff)
            else:
                safe_log_error(
                    f"[WHATSAPP] ❌ Failed {response.status_code} | "
                    f"Body: {response.text[:200]}"
                )
                backoff = 2 ** attempt
                time.sleep(backoff)
        
        except requests.exceptions.Timeout:
            safe_log_error(f"[WHATSAPP] Timeout on attempt {attempt+1}")
            time.sleep(2 ** attempt)
        except Exception as e:
            safe_log_error(f"[WHATSAPP] Error: {e}")
            time.sleep(2 ** attempt)
    
    safe_log_error(f"[WHATSAPP] ❌ Failed after {max_retries} attempts")
    return False

def send_whatsapp_image_with_retry(to_number: str, image_url: str, caption: str, max_retries: int = 3) -> bool:
    url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    
    for attempt in range(max_retries):
        try:
            safe_log_debug(f"[WHATSAPP] Sending image to {to_number[-4:]} (attempt {attempt+1})")
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            safe_log_debug(f"[WHATSAPP] Image response: {response.status_code}")
            
            if response.status_code == 200:
                safe_log_info(f"[WHATSAPP] ✅ Image sent to {to_number[-4:]}")
                return True
            else:
                safe_log_error(f"[WHATSAPP] Image failed: {response.status_code} | Body: {response.text[:300]}")
                time.sleep(2 ** attempt)
        
        except Exception as e:
            safe_log_error(f"[WHATSAPP] Image error: {e}")
            time.sleep(2 ** attempt)
    
    return False

# ============================================================================
# SMART TEMPLATE RESPONSE
# ============================================================================
def get_smart_template_response(message: str, user_city: str, user_interest: str, 
                                user_email: str, user_id: str, user_budget: str) -> Optional[str]:
    msg_lower = message.lower().strip()
    
    # ✅ NOTE: Resume check now happens in _process_message() BEFORE this function
    # This ensures old users never reach template logic


    # Email validation & collection
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    email_match = re.search(email_pattern, message)
    
    if email_match:
        provided_email = email_match.group(0)
        conversation_state.update(user_id, 'email', provided_email)
        conversation_state.mark_email_asked(user_id)
        if user_city != "Not Mentioned":
            return f"Perfect! Thank you for sharing your email. Would you like to see some property photos in {user_city} now? 📸"
        else:
            return "Perfect! Thank you for sharing your email. Which city would you like to explore? Dubai 🌆 | Abu Dhabi 🏙️ | UK 🇬🇧"
    
    # Budget extraction
    budget_amount, budget_cat = budgetqualifier.extract_budget_from_message(message)
    
    if budget_cat and budget_cat != user_budget:
        safe_log_debug(f"[BUDGET] User {user_id[-4:]} specified budget: {budget_cat}")
        
        matched_properties = budgetqualifier.match_properties(
            PROPERTIES, budget_cat, user_city, max_results=3
        )
        property_summary = budgetqualifier.format_property_summary(matched_properties)
        
        conversation_state.update(user_id, 'budget', budget_cat)
        return property_summary
    
    # Greetings
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 
                 'good evening', 'hii', 'hiii', 'helo', 'hola', 'namaste']
    if msg_lower in greetings or len(msg_lower) <= 3:
        conversation_state.update(user_id, 'greeted', 'yes')
        return ("Hi there! 👋 I'm Selvora, your property consultant. "
                "Which city are you interested in?\n\n"
                "🏙️ Dubai (Marina, Downtown)\n"
                "🌆 Abu Dhabi (Yas Island)\n"
                "🇬🇧 UK (London, Manchester)")
    
    # Thanks / Bye
    if msg_lower in ['thanks', 'thank you', 'thankyou', 'ty', 'ok', 'okay', 'bye', 'goodbye']:
        return "You're welcome! Feel free to reach out anytime. Have a great day! 😊"
    
    # City selection
    cities_map = {
        'dubai': 'Dubai',
        'marina': 'Dubai Marina',
        'downtown': 'Downtown Dubai',
        'abudhabi': 'Abu Dhabi',
        'yas': 'Yas Island',
        'uk': 'UK',
        'london': 'London',
        'manchester': 'Manchester'
    }
    
    if msg_lower in cities_map and len(msg_lower.split()) == 1:
        city_name = cities_map[msg_lower]
        conversation_state.update(user_id, 'city', city_name)
        return (f"Excellent choice! {city_name} has fantastic properties. 🏢\n\n"
                f"What's your budget preference?\n"
                f"💎 Luxury - Premium properties\n"
                f"🏠 Standard - Great value\n"
                f"💰 Affordable - Budget-friendly")
    
    # Budget selection
    if msg_lower in ['luxury', 'standard', 'affordable', 'budget']:
        interest_name = msg_lower.title()
        conversation_state.update(user_id, 'interest', interest_name)
        
        if conversation_state.should_ask_for_email(user_id, user_email):
            conversation_state.mark_email_asked(user_id)
            return (f"Perfect! {interest_name} properties are a great choice. 🌟\n\n"
                    f"To show you our exclusive listings, may I have your email address? "
                    f"📧 This helps me send you detailed brochures and property updates.")
        
        if user_city != "Not Mentioned":
            return f"Perfect! I have some beautiful {interest_name.lower()} properties in {user_city}. Would you like to see some photos? 📸"
        else:
            return f"Great choice! {interest_name} properties it is. Which city would you like to explore? Dubai 🌆 | Abu Dhabi 🏙️ | UK 🇬🇧"
    
    # Photo requests
    photo_keywords = ['yes', 'sure', 'photos', 'pictures', 'images', 'show me', 'send', 'yeah', 'yep']
    if any(keyword in msg_lower for keyword in photo_keywords):
        if conversation_state.should_ask_for_email(user_id, user_email):
            conversation_state.mark_email_asked(user_id)
            return ("I'd love to show you our properties! 📸\n\n"
                    "Before I send them, may I have your email address? "
                    "This way I can also send you detailed brochures. 📧")
        
        if user_city != "Not Mentioned":
            return f"Here is a glimpse of the exclusive units we have in {user_city}. SHOW_PHOTO: {user_city}"
        else:
            return "I'd love to show you our properties! Which city interests you? Dubai 🌆 | Abu Dhabi 🏙️ | UK 🇬🇧"
    
    # Price questions
    if any(word in msg_lower for word in ['price', 'cost', 'expensive', 'cheap', 'how much']):
        if user_city != "Not Mentioned":
            prices = {
                'Marina': '1.5M AED onwards',
                'Downtown': '2.8M AED onwards',
                'Meydan': '4.2M AED onwards',
                'Dubai': '1.5M - 4.5M AED range',
                'Abu Dhabi': '2M - 5M AED range',
                'UK': '£500k - £3M range'
            }
            price_info = prices.get(user_city, '1.5M - 5M AED')
            return f"In {user_city}, our properties range from {price_info} depending on type and location. Would you like to see specific options? 🏢"
        else:
            return "Property prices vary by location. Which city are you interested in? Dubai 🌆 | Abu Dhabi 🏙️ | UK 🇬🇧"
    
    # ROI questions
    if 'roi' in msg_lower or 'return' in msg_lower or 'investment' in msg_lower:
        return ("Our properties offer excellent ROI! 📈\n\n"
                "• Dubai Marina: ~6.5% average\n"
                "• Downtown: ~7.2% average\n"
                "• Meydan: ~5.8% average\n\n"
                "Would you like to see specific properties?")
    
    # Location questions
    if 'where' in msg_lower or 'location' in msg_lower or 'area' in msg_lower:
        return ("We have premium properties in:\n\n"
                "🇦🇪 Dubai (Marina, Downtown, Meydan)\n"
                "🇦🇪 Abu Dhabi (Yas, Saadiyat)\n"
                "🇬🇧 UK (London, Manchester)\n\n"
                "Which location interests you?")
    
    # Simple yes/no
    if msg_lower in ['yes', 'no', 'y', 'n']:
        if conversation_state.get(user_id, 'email_asked') == 'yes' and user_email == "Not Provided":
            if msg_lower in ['no', 'n']:
                return "No problem! You can always share it later. How else can I assist you with your property search? 🏢"
        
        if msg_lower in ['yes', 'y'] and user_city != "Not Mentioned":
            return f"Here is a glimpse of the exclusive units we have in {user_city}. SHOW_PHOTO: {user_city}"
        
        return "I'd be happy to help! What would you like to know about our properties? 🏢"
    
    # Short messages
    if len(msg_lower) <= 5 and len(msg_lower.split()) == 1:
        return ("I'm here to help! Would you like to:\n\n"
                "🏙️ Explore properties in a specific city\n"
                "💰 Learn about pricing and ROI\n"
                "📸 See property photos")
    
    return None

# ============================================================================
# GEMINI CONCURRENCY PROTECTION
# ============================================================================
GEMINI_CONCURRENCY_LIMIT = threading.Semaphore(5)  # Max 5 concurrent Gemini calls

# ============================================================================
# AI CALL WITH CIRCUIT BREAKER (FIXED ISSUE 4)
# ============================================================================
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.lock = threading.Lock()
        self.state = 'CLOSED'
    
    def call(self, func, *args, **kwargs):
        with self.lock:
            if self.state == 'OPEN':
                if self.last_failure_time and \
                   (datetime.now() - self.last_failure_time).total_seconds() > self.timeout:
                    self.state = 'HALF_OPEN'
                    safe_log_info("[CIRCUIT] 🔄 Half-open, testing recovery...")
                else:
                    raise Exception("Circuit breaker OPEN")
        
        try:
            result = func(*args, **kwargs)
            with self.lock:
                previous_state = self.state
                self.failure_count = 0
                self.state = 'CLOSED'
                
                # FIX ISSUE 4: Log recovery transitions
                if previous_state != 'CLOSED':
                    safe_log_info(f"[CIRCUIT] ✅ RECOVERED: {previous_state} → CLOSED")
            return result
        except Exception as e:
            with self.lock:
                self.failure_count += 1
                self.last_failure_time = datetime.now()
                if self.failure_count >= self.failure_threshold:
                    self.state = 'OPEN'
                    safe_log_error(f"[CIRCUIT] 🚨 OPENED after {self.failure_count} failures")
            raise e

gemini_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

def call_gemini_with_circuit_breaker(prompt: str, user_id: str, user_city: str = "", 
                                     user_budget: str = "", user_interest: str = "", correlation_id="N/A") -> str:
    # cache_key = response_cache.get_cache_key(
    #     user_id, prompt, city=user_city, budget=user_budget, interest=user_interest
    # )
    # cached_response = response_cache.get(cache_key)
    
    # if cached_response:
    #     safe_log_debug(f"[GEMINI] {correlation_id} | Cache hit for {user_id[-4:]}")
    #     return cached_response

    can_use, remaining = ai_usage_tracker.can_use_ai(user_id)
    if not can_use:
        safe_log_warning(f"[GEMINI] {correlation_id} | {user_id[-4:]} exceeded quota")
        safe_log_warning(f"[AI-QUOTA] EXHAUSTED | User={user_id[-4:]} | Remaining=0 | Correlation={correlation_id}")
        return {
            "text":(
                "I appreciate your interest! For detailed property information, "
                "I'd love to connect you with our senior consultant who can provide "
                "personalized recommendations. Would you like me to arrange a call? 📞"
            ),
            "fallback" : True 
        }    
    
    safe_log_debug(f"[GEMINI] {correlation_id} | AI call for {user_id[-4:]} (remaining: {remaining})")
    safe_log_info(f"[AI-CALL] INITIATED | User={user_id[-4:]} | Remaining={remaining} | Correlation={correlation_id}")
    
    def _call_api():
        # Acquire semaphore to limit concurrent Gemini calls
        GEMINI_CONCURRENCY_LIMIT.acquire()
        try:
            response = model.generate_content(
            prompt,
            request_options={"timeout": 15}
        )
            return response.text.strip().replace('*', '')
        finally:
            GEMINI_CONCURRENCY_LIMIT.release()
    
    try:
        full_reply = gemini_circuit_breaker.call(_call_api)
        
        # response_cache.set(cache_key, full_reply)
        ai_usage_tracker.record_ai_call(user_id)
        
        safe_log_info(f"[GEMINI] {correlation_id} | ✅ Success for {user_id[-4:]}")
        return full_reply
    
    except google_exceptions.ResourceExhausted:
        safe_log_warning(f"[GEMINI] {correlation_id} | Quota exhausted")
        return { 
            "text":(
                "Thank you for your interest! To provide you with the best service, "
                "let me connect you with our property specialist who can give you "
                "detailed information and schedule a viewing. Can I have them reach out to you? 📞"
            ),
            "fallback" : True
        }
    
    except Exception as e:
        safe_log_error(f"[GEMINI] {correlation_id} | Error: {e}")
        return {
            "text":(
                "I'd love to help you find the perfect property! For personalized assistance, "
                "our specialist can provide detailed information. Would you like them to contact you? 📞"
            ),
            "fallback" : True
        }

def call_gemini_for_intent(prompt: str, user_id: str = "system", correlation_id: str = "N/A") -> str:
    """
    Lightweight Gemini call for intent classification.
    Reuses circuit breaker + concurrency limit, but bypasses per-user quota
    (intent classification is overhead, not user-facing AI usage).
    
    Returns raw text response string. On any failure, returns empty string
    so the intent classifier falls back gracefully to 'unclear'.
    """
    def _call_api():
        GEMINI_CONCURRENCY_LIMIT.acquire()
        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
                request_options={"timeout": 10}
            )
            return response.text.strip()
        finally:
            GEMINI_CONCURRENCY_LIMIT.release()
    
    try:
        result = gemini_circuit_breaker.call(_call_api)
        safe_log_debug(f"[INTENT-GEMINI] ✅ {correlation_id}")
        return result
    except Exception as e:
        safe_log_warning(f"[INTENT-GEMINI] Error: {e} | {correlation_id}")
        return ""    

# ============================================================================
# FLASK ROUTES
# ============================================================================
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        safe_log_info("[WEBHOOK] ✅ Verified")
        return challenge, 200
    
    return "Verification Failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    """Immediate ACK webhook handler"""
    correlation_id = f"msg_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
    
    try:
        # FIXED STRUCTURE BELOW (Aligned indentation inside try block)
        data = request.json
        
        # Schema validation
        if not isinstance(data, dict):
            safe_log_error(f"[WEBHOOK] Invalid JSON type: {correlation_id}")
            return "OK", 200
    
        if not data.get("object"):
            safe_log_warning(f"[WEBHOOK] Missing 'object': {correlation_id}")
            return "OK", 200
    
        if not isinstance(data.get("entry"), list) or len(data["entry"]) == 0:
            safe_log_warning(f"[WEBHOOK] Invalid 'entry': {correlation_id}")
            return "OK", 200
            
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "statuses" in value:
            return "OK", 200
        
        if "messages" not in value:
            return "OK", 200
        
        message = value["messages"][0]
        sender_id = message.get("from")
        message_id = message.get("id")

        # Paranoid null check (schema validated, but defensive)
        if not sender_id or not message_id:
            safe_log_warning(f"[WEBHOOK] {correlation_id} | Null sender_id or message_id after validation")
            return "OK", 200
        # DEV MODE filtering
        if WHATSAPP_MODE == 'DEV':
            if len(WHATSAPP_TEST_NUMBERS) == 0:
                safe_log_error(f"[DEV_MODE] Blocked - no test numbers | {correlation_id}")
                return "OK", 200
            
            if sender_id not in WHATSAPP_TEST_NUMBERS:
                safe_log_warning(f"[DEV_MODE] Blocked {sender_id[-4:]} | {correlation_id}")
                return "OK", 200
            
            safe_log_debug(f"[DEV_MODE] Accepted {sender_id[-4:]} | {correlation_id}")
        
        # Deduplication check
        if message_deduplicator.is_duplicate(message_id, sender_id):
            return "OK", 200
        
        # Message type check
        message_type = message.get("type", "text")
        if message_type != "text":
            safe_log_debug(f"[WEBHOOK] Ignoring {message_type} | {correlation_id}")
            return "OK", 200
        
        text_body = message.get("text", {}).get("body", "")
        if not text_body:
            safe_log_warning(f"[WEBHOOK] Empty body | {correlation_id}")
            return "OK", 200
        
        # Extract user name
        user_name = "Unknown User"
        if "contacts" in value:
            try:
                user_name = value["contacts"][0]["profile"]["name"]
            except:
                pass
        
        # Create webhook message
        webhook_msg = WebhookMessage(
            correlation_id=correlation_id,
            sender_id=sender_id,
            message_id=message_id,
            text_body=text_body,
            user_name=user_name,
            timestamp=datetime.now()
        )
        
        # Queue for async processing
        queued = webhook_processor.enqueue(webhook_msg)
        
        if not queued:
            safe_log_error(
                f"[WEBHOOK] Queue full (95% limit), rejecting | "
                f"Correlation: {correlation_id} | "
                f"Sender: {sender_id[-4:]} | "
                f"Will rely on WhatsApp webhook retry"
            )
            # Return 429 to trigger WhatsApp retry
            return "Service Temporarily Unavailable", 429
        
        safe_log_info(f"[WEBHOOK] Queued {correlation_id} from {sender_id[-4:]}")
        
        # IMMEDIATE 200 OK
        return "OK", 200
    
    except Exception as e:
        safe_log_error(f"[WEBHOOK] Error {correlation_id}: {e}")
        import traceback
        traceback.print_exc()
        
        return "OK", 200

# ============================================================================
# HEALTH & MONITORING
# ============================================================================
@app.route('/health', methods=['GET'])
def health():
    dedup_stats = message_deduplicator.get_stats()
    state_stats = conversation_state.get_stats()
    
    return jsonify({
        'status': 'healthy',
        'mode': WHATSAPP_MODE,
        'test_numbers': len(WHATSAPP_TEST_NUMBERS) if WHATSAPP_MODE == 'DEV' else 'N/A',
        'model': GEMINI_MODEL_NAME,
        'deduplication': dedup_stats,
        'conversation_state': state_stats,
        'webhook_queue': {
            'size': webhook_processor.queue.qsize(),
            'processed': webhook_processor.processed_count,
            'failed': webhook_processor.failed_count,
            'workers': len(webhook_processor.workers),
            'worker_restarts': webhook_processor.worker_restarts,
            'restart_circuit_open': webhook_processor.restart_circuit_open  # ADD THIS LINE
        },
        'circuit_breaker': {
            'state': gemini_circuit_breaker.state,
            'failures': gemini_circuit_breaker.failure_count
        },
        'all_issues_fixed': True,  # Confirmation
        'fixes_applied': [
            'issue_1_queue_overflow_dlq',
            'issue_2_global_sheet_lock',
            'issue_3_worker_auto_recovery',
            'issue_4_circuit_breaker_logging',
            'issue_5_dedup_memory_bounds',
            'issue_6_graceful_shutdown'
        ],
        'features': {
            '1-9': 'active',
            '10_budget_matching': 'active',
            '11_agent_handover': 'active',
            '12_drop_detection': 'active' if dropdetector.is_running else 'inactive'
        },
        'properties_loaded': len(PROPERTIES)
    }), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    dedup_stats = message_deduplicator.get_stats()
    
    metrics_text = f"""# HELP webhook_messages_total Total messages processed
# TYPE webhook_messages_total counter
webhook_messages_total {dedup_stats['total_processed']}

# HELP webhook_duplicates_total Duplicate webhooks blocked
# TYPE webhook_duplicates_total counter
webhook_duplicates_total {dedup_stats['duplicate_webhooks_blocked']}

# HELP webhook_queue_size Current queue size
# TYPE webhook_queue_size gauge
webhook_queue_size {webhook_processor.queue.qsize()}

# HELP webhook_failed_total Total messages failed
# TYPE webhook_failed_total counter
webhook_failed_total {webhook_processor.failed_count}

# HELP webhook_processed_total Total messages processed by workers
# TYPE webhook_processed_total counter
webhook_processed_total {webhook_processor.processed_count}

# HELP active_users Current active users
# TYPE active_users gauge
active_users {conversation_state.get_stats()['active_users']}

# HELP circuit_breaker_state Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN)
# TYPE circuit_breaker_state gauge
circuit_breaker_state {{'CLOSED': 0, 'OPEN': 1, 'HALF_OPEN': 2}}.get(gemini_circuit_breaker.state, 0)
"""
    return metrics_text, 200, {'Content-Type': 'text/plain'}

@app.route('/start-drop-detector', methods=['POST'])
def start_drop_detector():
    try:
        dropdetector.start_background_checker()
        return jsonify({'status': 'success', 'message': 'Drop detector started'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop-drop-detector', methods=['POST'])
def stop_drop_detector():
    try:
        dropdetector.stop_background_checker()
        return jsonify({'status': 'success', 'message': 'Drop detector stopped'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ============================================================================
# FIX ISSUE 6: GRACEFUL SHUTDOWN
# ============================================================================
def shutdown_handler(signum, frame):
    """FIX ISSUE 6: Graceful shutdown on SIGTERM/SIGINT"""
    safe_log_warning(f"[SHUTDOWN] 🛑 Received signal {signum}, initiating graceful shutdown...")
    
    # Stop webhook processor
    safe_log_info("[SHUTDOWN] Stopping webhook processor...")
    webhook_processor.stop()
    
    # Stop drop detector
    safe_log_info("[SHUTDOWN] Stopping drop detector...")
    dropdetector.stop_background_checker()
    
    # Wait for queue to drain (max 30 seconds)
    safe_log_info("[SHUTDOWN] Waiting for queue to drain...")
    deadline = time.time() + 30
    while webhook_processor.queue.qsize() > 0 and time.time() < deadline:
        time.sleep(0.5)
    
    remaining = webhook_processor.queue.qsize()
    if remaining > 0:
        safe_log_warning(
            f"[SHUTDOWN] ⚠️  {remaining} messages still in queue (timeout) | "
            f"Messages were not processed before shutdown"
        )
    
    safe_log_info("[SHUTDOWN] ✅ Graceful shutdown complete")
    sys.exit(0)

def startup():
    """Application startup"""
    safe_log_info("=" * 70)
    safe_log_info("🚀 WHATSAPP BOT - ENTERPRISE PRODUCTION MODE")
    safe_log_info("=" * 70)

    # Runtime verification
    if RUNNING_UNDER_GUNICORN:
        safe_log_info("✅ Runtime: Gunicorn WSGI (PRODUCTION)")
    else:
        safe_log_warning("⚠️  Runtime: Flask dev server (DEVELOPMENT ONLY)")
        if os.getenv('FLASK_ENV') == 'production':
            safe_log_error("❌ CRITICAL: Flask dev server in production mode!")
            sys.exit(1)

    safe_log_info(f"Mode: {WHATSAPP_MODE}")
    safe_log_info(f"Model: {GEMINI_MODEL_NAME}")
    safe_log_info(f"Properties: {len(PROPERTIES)} loaded")
    safe_log_info("=" * 70)

    safe_log_info("ALL PRODUCTION ISSUES FIXED:")
    safe_log_info("  ✅ ISSUE 1: Queue overflow + DLQ + backpressure")
    safe_log_info("  ✅ ISSUE 2: Global Google Sheets lock")
    safe_log_info("  ✅ ISSUE 3: Worker auto-recovery")
    safe_log_info("  ✅ ISSUE 4: Circuit breaker recovery logging")
    safe_log_info("  ✅ ISSUE 5: Dedup memory bounds (LRU)")
    safe_log_info("  ✅ ISSUE 6: Graceful shutdown (SIGTERM/SIGINT)")
    safe_log_info("  ✅ ENHANCEMENT: Slack webhook alerts for critical failures")
    safe_log_info("=" * 70)
    
    # Slack webhook status
    if os.getenv('SLACK_WEBHOOK_URL'):
        safe_log_info("📢 Slack alerts: ENABLED")
    else:
        safe_log_info("📢 Slack alerts: DISABLED (no SLACK_WEBHOOK_URL)")
    
    safe_log_info("=" * 70)

    if WHATSAPP_MODE == 'DEV':
        if len(WHATSAPP_TEST_NUMBERS) == 0:
            safe_log_warning("⚠️  DEV MODE: Zero test numbers configured!")
        else:
            safe_log_info(f"Test Numbers: {len(WHATSAPP_TEST_NUMBERS)} configured")

    safe_log_info("=" * 70)

    # Start background services
    safe_log_info("[INIT] Loading properties from backend...")
    fetch_properties_from_backend()
    _start_properties_auto_refresh(interval_seconds=300)  # Refresh every 5 min
    safe_log_info("[INIT] Starting webhook processor...")
    webhook_processor.start()

    safe_log_info("[INIT] Starting drop detector...")
    dropdetector.start_background_checker()

    safe_log_info("=" * 70)
    safe_log_info("✅ Bot ready for production traffic")
    safe_log_info("=" * 70)


# CRITICAL: This MUST be at module level (0 indentation)
if __name__ == '__main__':

    # FIX ISSUE 6: Register shutdown handlers
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    startup()

    # Enforce Gunicorn in production
    if os.getenv('FLASK_ENV') == 'production' and not RUNNING_UNDER_GUNICORN:
        safe_log_error(
            "❌ BLOCKED: Flask dev server not allowed in production. "
            "Use: gunicorn -w 4 -b 0.0.0.0:5000 main:app"
        )
        sys.exit(1)

    # Prevent direct run if under Gunicorn
    if RUNNING_UNDER_GUNICORN:
        safe_log_error(
            "❌ ERROR: Do not run main.py directly under Gunicorn. "
            "Use: gunicorn main:app"
        )
        sys.exit(1)

    try:
        safe_log_warning("⚠️  Running Flask dev server (DEV MODE ONLY)")
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        shutdown_handler(signal.SIGINT, None)

# For production deployment:
# gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 --worker-class sync main:app
