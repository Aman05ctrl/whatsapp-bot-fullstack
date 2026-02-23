import threading
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
import time
from typing import Dict, Set, Optional, List, Tuple
import gspread
from google.oauth2.service_account import Credentials
import os
import hashlib
import uuid      # Random UUID every call (new user every time)
from dotenv import load_dotenv

# ============================================================================
# SHEET COLUMN INDICES (CENTRALIZED)
# ============================================================================
COLUMN_RAW_ID = 9          # Column I: Raw ID (phone)
COLUMN_FINGERPRINT = 17    # Column Q: User_Fingerprint

load_dotenv()

logger = logging.getLogger(__name__)

def safe_log_info(message: str):
    try:
        logger.info(message)
    except Exception:
        print(f"[INFO] {message}")

def safe_log_error(message: str):
    try:
        logger.error(message)
    except Exception:
        print(f"[ERROR] {message}")

def safe_log_warning(message: str):
    try:
        logger.warning(message)
    except Exception:
        print(f"[WARNING] {message}")

def safe_log_debug(message: str):
    try:
        logger.debug(message)
    except Exception:
        print(f"[DEBUG] {message}")

# ============================================================================
# GOOGLE SHEETS CLIENT SINGLETON (Thread-Safe)
# ============================================================================
_SHEETS_CLIENT = None
_SHEETS_CLIENT_LOCK = threading.Lock()

def get_sheets_client():
    """Lazy singleton for Google Sheets client"""
    global _SHEETS_CLIENT
    
    if _SHEETS_CLIENT is None:
        with _SHEETS_CLIENT_LOCK:
            if _SHEETS_CLIENT is None:  # Double-check
                try:
                    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                    creds = Credentials.from_service_account_file('google_key.json', scopes=scope)
                    _SHEETS_CLIENT = gspread.authorize(creds)
                    safe_log_info("[SHEETS] Client initialized")
                except Exception as e:
                    safe_log_error(f"[SHEETS] Client init failed: {e}")
                    raise
    
    return _SHEETS_CLIENT      


def sheets_operation_with_retry(operation, max_retries=3):
    """Retry Google Sheets operations with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1:
                safe_log_error(f"[SHEETS] Failed after {max_retries} attempts: {e}")
                raise
            
            backoff = 2 ** attempt
            safe_log_warning(f"[SHEETS] Retry {attempt+1}/{max_retries} in {backoff}s: {e}")
            time.sleep(backoff)


# ============================================================================
# PHONE NUMBER NORMALIZATION
# ============================================================================

def normalize_phone_number(phone_id: str) -> str:
    """Normalize phone number to canonical format"""
    if not phone_id:
        return ""

    digits_only = re.sub(r'\D', '', str(phone_id))

    if digits_only.startswith('91') and len(digits_only) >= 12:
        return f"91_{digits_only[2:]}"
    elif digits_only.startswith('971') and len(digits_only) >= 12:
        return f"971_{digits_only[3:]}"
    elif digits_only.startswith('1') and len(digits_only) >= 11:
        return f"1_{digits_only[1:]}"
    elif digits_only.startswith('44') and len(digits_only) >= 12:
        return f"44_{digits_only[2:]}"
    else:
        return f"UNKNOWN_{digits_only}"
    
# Valid country codes for E.164 parsing
VALID_COUNTRY_CODES = {
    '1',    # USA, Canada
    '7',    # Russia, Kazakhstan
    '20', '27', '30', '31', '32', '33', '34', '36', '39',
    '40', '41', '43', '44', '45', '46', '47', '48', '49',
    '51', '52', '53', '54', '55', '56', '57', '58',
    '60', '61', '62', '63', '64', '65', '66',
    '81', '82', '84', '86',
    '90', '91', '92', '93', '94', '95', '98',
    '211', '212', '213', '216', '218',
    '220', '221', '222', '223', '224', '225', '226',
    '227', '228', '229',
    '230', '231', '232', '233', '234', '235', '236',
    '237', '238', '239',
    '240', '241', '242', '243', '244', '245', '246',
    '248', '249',
    '250', '251', '252', '253', '254', '255', '256',
    '257', '258',
    '260', '261', '262', '263', '264', '265', '266',
    '267', '268', '269',
    '290', '291',
    '297', '298', '299',
    '350', '351', '352', '353', '354', '355', '356',
    '357', '358', '359',
    '370', '371', '372', '373', '374', '375', '376',
    '377', '378', '380', '381', '382', '383', '385',
    '386', '387', '389',
    '420', '421', '423',
    '500', '501', '502', '503', '504', '505', '506',
    '507', '508', '509',
    '590', '591', '592', '593', '594', '595', '596',
    '597', '598', '599',
    '670', '672', '673', '674', '675', '676', '677',
    '678', '679',
    '680', '681', '682', '683', '685', '686', '687',
    '688', '689',
    '690', '691', '692',
    '850', '852', '853', '855', '856',
    '870', '871', '872', '873', '874', '878',
    '880', '881', '882', '883', '886',
    '960', '961', '962', '963', '964', '965', '966',
    '967', '968', '970', '971', '972', '973', '974',
    '975', '976', '977',
    '992', '993', '994', '995', '996', '998'
}


def format_phone_number(phone_id: str) -> tuple:
    """
    Safely extract country code and national number from E.164 phone number.
    Never guesses. Never mis-parses.
    """
    if not phone_id:
        return ('', '')

    digits = ''.join(filter(str.isdigit, str(phone_id)))
    if len(digits) < 5:
        return ('', digits)

    # Try 3 → 2 → 1 digit country codes
    for length in (3, 2, 1):
        cc = digits[:length]
        national = digits[length:]

        if cc in VALID_COUNTRY_CODES and len(national) >= 4:
            return (f'+{cc}', national)

    # Fallback: do NOT invent a country code
    return ('', digits)

# ============================================================================
# USER FINGERPRINT GENERATION
# ============================================================================
def generate_user_fingerprint(country_code, phone, email, mode):
    """Generate unique user hash/fingerprint"""
    
    # 1. Handle Random Mode immediately
    if mode == "TEST_RANDOM":
        return f"TEST_RANDOM_{uuid.uuid4().hex[:16]}"

    # 2. Decide Base Identity (Your Logic - The Best Part) 🧠
    # Email priority, fallback to Phone
    if email and email != "Not Provided":
        base_identity = email.lower()
    else:
        # Note: Ensure arguments match what you pass (phone vs phone_number)
        base_identity = f"{country_code}:{phone}"

    # 3. Apply Salt/Prefix based on Mode
    if mode == "TEST_DETERMINISTIC":
        raw_data = f"{base_identity}:TEST"
        prefix = "TEST_DET"
    else:  # PROD
        raw_data = base_identity
        prefix = "PROD"

    # 4. Generate Hash
    return f"{prefix}_{hashlib.sha256(raw_data.encode()).hexdigest()[:16]}"

# ============================================================================
# FIX #3: OPTIMIZED SHEET LOOKUP (SINGLE CALL)
# ============================================================================

def find_user_row_exact(sheet, normalized_phone: str, raw_id_column: int = COLUMN_RAW_ID) -> Optional[int]:
    """Find user row by exact match on normalized phone"""
    try:
        all_raw_ids = sheet.col_values(raw_id_column)

        if not all_raw_ids:
            return None

        for idx, raw_id in enumerate(all_raw_ids[1:], start=2):
            if not raw_id:
                continue

            normalized_existing = normalize_phone_number(raw_id)

            if normalized_existing == normalized_phone:
                safe_log_debug(f"[LOOKUP] Found row {idx} for {normalized_phone}")
                return idx

        return None

    except Exception as e:
        safe_log_error(f"[LOOKUP] Error: {e}")
        return None


def find_user_row_by_fingerprint(sheet, user_fingerprint: str, fingerprint_column: int = COLUMN_FINGERPRINT) -> Optional[int]:
    """
    Find user row by fingerprint match (PRIMARY identifier)
    
    Args:
        sheet: Google Sheet object
        user_fingerprint: Hashed fingerprint string
        fingerprint_column: Column Q (17)
    
    Returns:
        Row number or None
    """
    try:
        all_fingerprints = sheet.col_values(fingerprint_column)
        
        if not all_fingerprints or len(all_fingerprints) < 2:
            return None
        
        # Skip header row
        for idx, existing_fingerprint in enumerate(all_fingerprints[1:], start=2):
            if existing_fingerprint and existing_fingerprint == user_fingerprint:
                safe_log_debug(f"[FINGERPRINT] Found row {idx} for {user_fingerprint[:16]}...")
                return idx
        
        return None
    
    except Exception as e:
        safe_log_error(f"[FINGERPRINT] Lookup error: {e}")
        return None
            

def get_user_data_once(sender_id: str) -> dict:
    """
    Single sheet lookup - returns ALL user data + row_num
    Uses fingerprint as PRIMARY identifier, phone as FALLBACK
    """
    try:
        client = get_sheets_client()
        
        GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')
        sheet = client.open(GOOGLE_SHEET_NAME).worksheet('Profiles')
        
        # ✅ UNIFIED: Generate fingerprint ONCE
        WHATSAPP_MODE_LOCAL = os.getenv('WHATSAPP_MODE', 'PROD').upper()
        country_code_temp, phone_temp = format_phone_number(sender_id)
        temp_fingerprint = generate_user_fingerprint(country_code_temp, phone_temp, "", WHATSAPP_MODE_LOCAL)

        # ✅ PRIMARY: Lookup by fingerprint
        row_num = sheets_operation_with_retry(
            lambda: find_user_row_by_fingerprint(sheet, temp_fingerprint, fingerprint_column=COLUMN_FINGERPRINT)
        )

        # ✅ FALLBACK: Phone lookup (migration support)
        if not row_num:
            normalized_phone = normalize_phone_number(sender_id)
            row_num = sheets_operation_with_retry(
                lambda: find_user_row_exact(sheet, normalized_phone, raw_id_column=COLUMN_RAW_ID)
            )
            if row_num:
                safe_log_warning("[MIGRATION] Found user by phone, will update fingerprint")

        # ✅ Fetch data if found
        if row_num:
            row_values = sheets_operation_with_retry(lambda: sheet.row_values(row_num))
            safe_log_debug(f"[SINGLE_LOOKUP] Found user data at row {row_num}")
            
            return {
                'row_num': row_num,
                'city': row_values[6] if len(row_values) > 6 else 'Not Mentioned',
                'email': row_values[5] if len(row_values) > 5 else 'Not Provided',
                'name': row_values[1] if len(row_values) > 1 else 'Unknown User',
                'interest': row_values[4] if len(row_values) > 4 else 'Not Specified',
                'found': True
            }
        else:
            safe_log_debug(f"[SINGLE_LOOKUP] New user")
            return {
                'row_num': None,
                'city': 'Not Mentioned',
                'email': 'Not Provided',
                'name': 'Unknown User',
                'interest': 'Not Specified',
                'found': False
            }
    
    except Exception as e:
        safe_log_error(f"[SINGLE_LOOKUP] Error: {e}")
        return {
            'row_num': None,
            'city': 'Not Mentioned',
            'email': 'Not Provided',
            'name': 'Unknown User',
            'interest': 'Not Specified',
            'found': False
        }
    
def get_user_resume_context(sender_id: str) -> dict:
    """
    Get full context for resuming old user conversations
    Uses fingerprint-based lookup with phone fallback
    """
    try:
        client = get_sheets_client()
        GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')
        sheet = client.open(GOOGLE_SHEET_NAME).worksheet('Profiles')
        
        # ✅ UNIFIED: Generate fingerprint ONCE
        WHATSAPP_MODE_LOCAL = os.getenv("WHATSAPP_MODE", "PROD").upper()
        country_code_temp, phone_temp = format_phone_number(sender_id)
        temp_fingerprint = generate_user_fingerprint(country_code_temp, phone_temp, "", WHATSAPP_MODE_LOCAL)

        # ✅ PRIMARY: Lookup by fingerprint
        row_num = sheets_operation_with_retry(
            lambda: find_user_row_by_fingerprint(sheet, temp_fingerprint, fingerprint_column=COLUMN_FINGERPRINT)
        )

        # ✅ FALLBACK: Phone lookup (migration)
        if not row_num:
            normalized_phone = normalize_phone_number(sender_id)
            row_num = sheets_operation_with_retry(
                lambda: find_user_row_exact(sheet, normalized_phone, raw_id_column=COLUMN_RAW_ID)
            )

        if not row_num:
            return {
                'is_old_user': False,
                'summary': '',
                'last_updated': '',
                'days_inactive': 0,
                'missing_fields': [],
                'user_data': {}
            }
        
        row_values = sheets_operation_with_retry(lambda: sheet.row_values(row_num))
        
        # (rest of extraction logic remains unchanged)
        name = row_values[1] if len(row_values) > 1 else 'Unknown User'
        city = row_values[6] if len(row_values) > 6 else 'Not Mentioned'
        email = row_values[5] if len(row_values) > 5 else 'Not Provided'
        interest = row_values[4] if len(row_values) > 4 else 'Not Specified'
        budget = row_values[13] if len(row_values) > 13 else 'Not Specified'
        summary = row_values[12] if len(row_values) > 12 else ''
        last_updated = row_values[7] if len(row_values) > 7 else ''
        
        days_inactive = 0
        if last_updated:
            try:
                last_time = datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S')
                days_inactive = (datetime.now() - last_time).total_seconds() / 86400
            except:
                pass
        
        missing = []
        if city == 'Not Mentioned':
            missing.append('city')
        if interest == 'Not Specified':
            missing.append('interest')
        if budget == 'Not Specified':
            missing.append('budget')
        if email == 'Not Provided':
            missing.append('email')
        
        return {
            'is_old_user': True,
            'summary': summary,
            'last_updated': last_updated,
            'days_inactive': days_inactive,
            'missing_fields': missing,
            'user_data': {
                'name': name,
                'city': city,
                'email': email,
                'interest': interest,
                'budget': budget
            }
        }
        
    except Exception as e:
        safe_log_error(f"[RESUME_CONTEXT] Error: {e}")
        return {
            'is_old_user': False,
            'summary': '',
            'last_updated': '',
            'days_inactive': 0,
            'missing_fields': [],
            'user_data': {}
        } 

# ============================================================================
# CRM CLASSES (UNCHANGED)
# ============================================================================

class LeadScoringSystem:
    """Lead scoring system"""
    def __init__(self):
        self.lock = threading.Lock()
        self.scored_actions: Dict[str, Dict[str, bool]] = defaultdict(dict)
        self.SCORE_VALUES = {
            'city_selected': 10,
            'interest_selected': 10,
            'email_provided': 20,
            'photo_requested': 10,
            'contact_consent': 30,
            'message_engagement': 5,
            'budget_specified': 15
        }
        self.MAX_ENGAGEMENT_SCORE = 20

    def calculate_score_update(self, user_id: str, user_city: str, user_interest: str, 
                               user_email: str, message: str, message_count: int,
                               user_budget: str = "Not Specified") -> Dict[str, int]:
        with self.lock:
            score_changes = {}

            if user_id not in self.scored_actions:
                self.scored_actions[user_id] = {}

            user_actions = self.scored_actions[user_id]

            if user_city != "Not Mentioned":
                if 'city_selected' not in user_actions:
                    score_changes['city_selected'] = self.SCORE_VALUES['city_selected']
                    user_actions['city_selected'] = True

            if user_interest != "Not Specified":
                if 'interest_selected' not in user_actions:
                    score_changes['interest_selected'] = self.SCORE_VALUES['interest_selected']
                    user_actions['interest_selected'] = True

            if user_email != "Not Provided":
                if 'email_provided' not in user_actions:
                    score_changes['email_provided'] = self.SCORE_VALUES['email_provided']
                    user_actions['email_provided'] = True

            if user_budget != "Not Specified":
                if 'budget_specified' not in user_actions:
                    score_changes['budget_specified'] = self.SCORE_VALUES['budget_specified']
                    user_actions['budget_specified'] = True

            photo_keywords = ['photo', 'picture', 'image', 'show me', 'send', 'listing']
            if any(keyword in message.lower() for keyword in photo_keywords):
                if 'photo_requested' not in user_actions:
                    score_changes['photo_requested'] = self.SCORE_VALUES['photo_requested']
                    user_actions['photo_requested'] = True

            consent_keywords = ['contact me', 'call me', 'reach out', 'schedule viewing']
            if any(keyword in message.lower() for keyword in consent_keywords):
                if 'contact_consent' not in user_actions:
                    score_changes['contact_consent'] = self.SCORE_VALUES['contact_consent']
                    user_actions['contact_consent'] = True

            engagement_key = f"message_engagement_total"
            current_engagement_score = user_actions.get(engagement_key, 0)
            if current_engagement_score < self.MAX_ENGAGEMENT_SCORE:
                if message_count % 2 == 0 and message_count > 0:
                    points_to_add = min(self.SCORE_VALUES['message_engagement'], 
                                       self.MAX_ENGAGEMENT_SCORE - current_engagement_score)
                    if points_to_add > 0:
                        score_changes[engagement_key] = points_to_add
                        user_actions[engagement_key] = current_engagement_score + points_to_add

            total_increase = sum(score_changes.values())
            return {"total_increase": total_increase, "breakdown": score_changes}

    def get_lead_score_category(self, score: int) -> str:
        if score >= 70:
            return "Hot"
        elif score >= 40:
            return "Warm"
        else:
            return "Cold"

leadscoring = LeadScoringSystem()

class FollowUpManager:
    """Follow-up manager"""
    def __init__(self):
        self.lock = threading.Lock()
        self.last_message_time: Dict[str, datetime] = {}
        self.FOLLOWUP_WINDOW_HOURS = 24

    def update_last_message_time(self, user_id: str):
        with self.lock:
            self.last_message_time[user_id] = datetime.now()

    def calculate_lead_status(self, user_id: str, has_email: bool, has_city: bool, has_interest: bool) -> tuple:
        with self.lock:
            if not has_email:
                return ("New", None)

            last_activity = self.last_message_time.get(user_id)
            if last_activity:
                time_since_last = datetime.now() - last_activity
                hours_inactive = time_since_last.total_seconds() / 3600

                if hours_inactive >= self.FOLLOWUP_WINDOW_HOURS:
                    followup_due = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
                    return ("Pending", followup_due)

            return ("Active", None)

followupmanager = FollowUpManager()

class ConversationSummaryGenerator:
    """Summary generator"""
    def __init__(self):
        self.lock = threading.Lock()
        self.auto_generated_summaries: Set[str] = set()

    def generate_summary(self, user_id: str, user_name: str, user_city: str, 
                        user_interest: str, user_email: str, lead_score: int, 
                        message_count: int) -> str:
        with self.lock:
            parts = []

            score_category = leadscoring.get_lead_score_category(lead_score)
            parts.append(f"📊 {score_category} ({lead_score}pts)")

            if user_city != "Not Mentioned":
                parts.append(f"📍 {user_city}")

            if user_interest != "Not Specified":
                parts.append(f"💰 {user_interest}")

            if user_email != "Not Provided":
                parts.append(f"✉️ {user_email}")

            if message_count >= 6:
                parts.append(f"💬 High ({message_count})")
            elif message_count >= 3:
                parts.append(f"💬 Moderate ({message_count})")

            summary = " | ".join(parts)
            self.auto_generated_summaries.add(user_id)
            return summary

    def should_update_summary(self, user_id: str, existing_summary: str) -> bool:
        with self.lock:
            if not existing_summary or existing_summary == "":
                return True

            if user_id in self.auto_generated_summaries:
                return True

            return False

summarygenerator = ConversationSummaryGenerator()

class BudgetQualifier:
    """Budget qualifier"""
    def __init__(self):
        self.lock = threading.Lock()
        self.BUDGET_RANGES = {
            'Low': (0, 2000000),
            'Medium': (2000000, 5000000),
            'Luxury': (5000000, float('inf'))
        }

    def extract_budget_from_message(self, message: str) -> Tuple[Optional[int], Optional[str]]:
        with self.lock:
            msg_lower = message.lower()

            if any(word in msg_lower for word in ['luxury', 'premium']):
                return (None, 'Luxury')
            if any(word in msg_lower for word in ['affordable', 'budget', 'cheap']):
                return (None, 'Low')
            if any(word in msg_lower for word in ['standard', 'medium']):
                return (None, 'Medium')

            return (None, None)

    def match_properties(self, properties: List[dict], budget_category: str, 
                        user_city: str = None, max_results: int = 3) -> List[dict]:
        with self.lock:
            return []

    def format_property_summary(self, properties: List[dict]) -> str:
        if not properties:
            return "I'll show you some great options!"
        return "Here are some properties matching your criteria."

budgetqualifier = BudgetQualifier()

class AgentHandoverManager:
    """Agent handover manager"""
    def __init__(self):
        self.lock = threading.Lock()
        self.handover_requests: Dict[str, datetime] = {}
        self.HANDOVER_SCORE_THRESHOLD = 80

    def should_handover(self, user_id: str, lead_score: int, has_email: bool, 
                       has_city: bool, has_interest: bool, message: str) -> Tuple[bool, str]:
        with self.lock:
            msg_lower = message.lower()

            agent_keywords = ['speak to agent', 'talk to human', 'contact me', 'call me']
            if any(keyword in msg_lower for keyword in agent_keywords):
                return (True, "Explicit Request")

            if lead_score >= self.HANDOVER_SCORE_THRESHOLD:
                return (True, "High Score")

            if has_email and has_city and has_interest:
                return (True, "Complete Profile")

            return (False, None)

    def record_handover(self, user_id: str):
        with self.lock:
            self.handover_requests[user_id] = datetime.now()

    def is_handed_over(self, user_id: str) -> bool:
        with self.lock:
            return user_id in self.handover_requests

    def get_handover_message(self, reason: str) -> str:
        messages = {
            "Explicit Request": "I'll connect you with our senior consultant. They'll reach out within 24 hours!",
            "High Score": "Based on your interest, our specialist will contact you with personalized recommendations!",
            "Complete Profile": "Perfect! Our consultant will reach out shortly with exclusive listings!"
        }
        return messages.get(reason, messages["Complete Profile"])

handovermanager = AgentHandoverManager()

class DropDetectionManager:
    """Drop detection manager"""
    def __init__(self):
        self.lock = threading.Lock()
        self.dropped_leads: Set[str] = set()
        self.DROP_THRESHOLD_HOURS = 48
        self.CHECK_INTERVAL_SECONDS = 3600
        self.is_running = False
        self.checker_thread = None

    def mark_as_active(self, user_id: str):
        with self.lock:
            if user_id in self.dropped_leads:
                self.dropped_leads.discard(user_id)

    def _generate_summaries_for_dropped_users(self):
        """Generate conversation summaries for inactive users"""
        try:
            try:
                from main import conversation_state
            except ImportError:
                safe_log_warning("[SUMMARY] conversation_state not available")
                return
            
            client = get_sheets_client()
            GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')
            sheet = client.open(GOOGLE_SHEET_NAME).worksheet('Profiles')
            
            # Get all users who need summary
            all_rows = sheet.get_all_values()
            for idx, row in enumerate(all_rows[1:], start=2):  # Skip header
                if len(row) < 13:
                    continue
                
                normalized_phone = row[8] if len(row) > 8 else ""
                existing_summary = row[12] if len(row) > 12 else ""
                last_updated = row[7] if len(row) > 7 else ""
                
                if not normalized_phone or not last_updated:
                    continue
                
                # Check if conversation is old (48+ hours)
                try:
                    last_time = datetime.strptime(last_updated, '%Y-%m-%d %H:%M:%S')
                    hours_inactive = (datetime.now() - last_time).total_seconds() / 3600
                    
                    if hours_inactive >= self.DROP_THRESHOLD_HOURS:
                        # Generate summary if not exists or needs update
                        city = row[6] if len(row) > 6 else "Not Mentioned"
                        interest = row[4] if len(row) > 4 else "Not Specified"
                        email = row[5] if len(row) > 5 else "Not Provided"
                        budget = row[13] if len(row) > 13 else "Not Specified"
                        
                        # Build summary
                        summary_parts = []
                        if interest != "Not Specified":
                            summary_parts.append(f"Interested in {interest}")
                        if city != "Not Mentioned":
                            summary_parts.append(f"in {city}")
                        if budget != "Not Specified":
                            summary_parts.append(f"({budget} budget)")
                        if email != "Not Provided":
                            summary_parts.append(f"Email: {email}")
                        
                        new_summary = " | ".join(summary_parts) if summary_parts else "Inquiry started"
                        
                        # Append to existing summary if present
                        if existing_summary and existing_summary != "":
                            final_summary = f"{existing_summary} → {new_summary}"
                        else:
                            final_summary = new_summary
                        
                        # Update sheet
                        sheet.update_cell(idx, 13, final_summary)  # Column M (Summary)
                        safe_log_info(f"[SUMMARY] Generated for row {idx}")
                except:
                    continue
        except Exception as e:
            safe_log_error(f"[SUMMARY] Error: {e}")            

    def start_background_checker(self):
        """FIX #7: Singleton pattern"""
        with self.lock:
            if self.is_running:
                safe_log_warning("[DROP] Already running")
                return

            def checker_loop():
                while self.is_running:
                    try:
                        import time
                        time.sleep(self.CHECK_INTERVAL_SECONDS)
                        # ✅ NEW: Generate summary for dropped conversations
                        self._generate_summaries_for_dropped_users()
                    except:
                        pass

            self.is_running = True
            self.checker_thread = threading.Thread(target=checker_loop, daemon=True)
            self.checker_thread.start()
            safe_log_info("[DROP] Started")

    def stop_background_checker(self):
        with self.lock:
            self.is_running = False
        if self.checker_thread:
            self.checker_thread.join(timeout=5)

dropdetector = DropDetectionManager()

# ============================================================================
# FIX ISSUE 2: GLOBAL SHEET LOCK (Thread-Safe)
# ============================================================================
GLOBAL_SHEET_LOCK = threading.Lock()  # FIX ISSUE 2: Single global lock for all sheet operations

# ============================================================================
# FIX #3: OPTIMIZED SHEET UPDATE (USES CACHED ROW_NUM)
# ============================================================================

def get_dubai_time():
    """Get Dubai time"""
    try:
        import pytz
        dubai_tz = pytz.timezone('Asia/Dubai')
        return datetime.now(dubai_tz).strftime('%Y-%m-%d %H:%M:%S')
    except:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def update_sheet_with_crm_features_optimized(sender_id, username, email, city, interest, 
                                             message_body, message_count, user_budget="Not Specified",
                                             cached_row_num=None, correlation_id="N/A", user_fingerprint=""):
    """
    FIX #3: Optimized sheet update using cached row_num
    FIX ISSUE 2: Uses GLOBAL_SHEET_LOCK for thread safety
    
    Args:
        cached_row_num: Row number from get_user_data_once() (prevents re-lookup)
    """
    global GLOBAL_SHEET_LOCK  # FIX ISSUE 2: Use global lock

    with GLOBAL_SHEET_LOCK:  # FIX ISSUE 2: Protected by global lock
        try:
            # scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            # creds = Credentials.from_service_account_file('google_key.json', scopes=scope)
            # client = gspread.authorize(creds)

            client = get_sheets_client()   

            GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')
            sheet = client.open(GOOGLE_SHEET_NAME).worksheet('Profiles')

            current_time = get_dubai_time()
            normalized_phone = normalize_phone_number(sender_id)
            country_code, clean_phone = format_phone_number(sender_id)

            score_update = leadscoring.calculate_score_update(
                sender_id, city, interest, email, message_body, message_count, user_budget
            )

            has_email = (email != "Not Provided")
            has_city = (city != "Not Mentioned")
            has_interest = (interest != "Not Specified")

            lead_status, followup_due = followupmanager.calculate_lead_status(
                sender_id, has_email, has_city, has_interest
            )

            should_handover, _ = handovermanager.should_handover(
                sender_id, 0, has_email, has_city, has_interest, message_body
            )

            handover_status = "Ready" if should_handover else "Bot Active"
            if handovermanager.is_handed_over(sender_id):
                handover_status = "Handed Over"

            conversation_status = "Active"
            if sender_id in dropdetector.dropped_leads:
                conversation_status = "Dropped"

            # FIX #3: Use cached row_num (no re-lookup)
            row_num = cached_row_num

            if row_num is None:
                # New user
                new_score = score_update['total_increase']
                new_summary = summarygenerator.generate_summary(
                    sender_id, username, city, interest, email, new_score, message_count
                )

                new_row = [
                    current_time, username, country_code, clean_phone,
                    interest, email, city, current_time, normalized_phone,
                    new_score, lead_status, followup_due or "", new_summary,
                    user_budget, handover_status, conversation_status,
                    user_fingerprint
                ]

                sheets_operation_with_retry(lambda: sheet.append_row(new_row))

            else:
                # Existing user - update
                current_score = 0
                row_values = []  # Crash Proof
                
                # GUARD: Prevent accidental double-read (should never happen with cached_row_num)
                if cached_row_num is None:
                    safe_log_error(f"[CRM] BUG: cached_row_num is None for existing user")
                    return
                
                try:
                    row_values = sheet.row_values(row_num)
                    if len(row_values) >= 10:
                        current_score = int(row_values[9]) if row_values[9].isdigit() else 0
                except Exception as e:
                    safe_log_warning(f"[CRM] Failed to fetch row values for score: {e}")
                    current_score = 0

                new_score = current_score + score_update['total_increase']

                # ✅ FIX 2: Check if fingerprint is missing (Clean & Fast)
                # Note: File ke top par COLUMN_FINGERPRINT = 17 define hona chahiye
                existing_fingerprint = ""
                FINGERPRINT_INDEX = 16  # Column Q is 17th, so index is 16 (0-based)
                
                # Simple IF check is faster than TRY-EXCEPT
                if len(row_values) > FINGERPRINT_INDEX:
                    existing_fingerprint = row_values[FINGERPRINT_INDEX]
                
                # Check if we need to migrate/add fingerprint
                updates_with_fingerprint = False
                if (not existing_fingerprint or existing_fingerprint.strip() == ""):
                    if user_fingerprint and user_fingerprint.strip():
                        safe_log_warning(f"[MIGRATION] Row {row_num} missing fingerprint, adding now")
                        updates_with_fingerprint = True

                # ✅ FIX 3: Construct Updates List
                updates = [
                    {'range': f'H{row_num}', 'values': [[current_time]]},
                    {'range': f'J{row_num}', 'values': [[new_score]]},
                    {'range': f'K{row_num}', 'values': [[lead_status]]},
                    {'range': f'O{row_num}', 'values': [[handover_status]]},
                    {'range': f'P{row_num}', 'values': [[conversation_status]]}
                ]

                # Standard fields update
                if username != "Unknown User":
                    updates.append({'range': f'B{row_num}', 'values': [[username]]})
                if email != "Not Provided":
                    updates.append({'range': f'F{row_num}', 'values': [[email]]})
                if city != "Not Mentioned":
                    updates.append({'range': f'G{row_num}', 'values': [[city]]})
                if interest != "Not Specified":
                    updates.append({'range': f'E{row_num}', 'values': [[interest]]})    
                if user_budget != "Not Specified":
                    updates.append({'range': f'N{row_num}', 'values': [[user_budget]]})

                # ✅ Add Fingerprint to updates if needed
                if updates_with_fingerprint:
                    updates.append({'range': f'Q{row_num}', 'values': [[user_fingerprint]]})

                if updates:
                    sheets_operation_with_retry(lambda: sheet.batch_update(updates))
                    safe_log_debug(f"[CRM] {correlation_id} | ✅ Updated row {row_num}")
                
                # Note: 'try-except' block for the main function handles any batch_update errors

        except Exception as e:
            safe_log_error(f"[CRM] {correlation_id} | Error: {e}")


def record_user_activity(sender_id: str):
    """Record user activity for follow-up tracking"""
    followupmanager.update_last_message_time(sender_id)
    dropdetector.mark_as_active(sender_id)

def log_conversation_to_sheet(sender_id: str, user_name: str, user_message: str, 
                               bot_response: str, reply_type: str, correlation_id: str = "N/A"):
    """Log conversation to Logs sheet"""
    try:
        client = get_sheets_client()
        GOOGLE_SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Dubai Real Estate Leads')
        
        try:
            logs_sheet = client.open(GOOGLE_SHEET_NAME).worksheet('Logs')
        except:
            safe_log_warning("[LOGS] 'Logs' sheet not found, skipping")
            return
        
        timestamp = get_dubai_time()
        normalized_phone = normalize_phone_number(sender_id)
        country_code, clean_phone = format_phone_number(sender_id)
        
        log_row = [
            timestamp,
            user_name,
            country_code,
            clean_phone,
            user_message[:500],
            reply_type,
            bot_response[:500]
        ]

        # ✅ NEW: Detect if sheet is a Table (which blocks append_row)
        try:
            # Test if sheet is a table by checking for data validation
            sheet_metadata = logs_sheet.spreadsheet.fetch_sheet_metadata()
            for sheet_info in sheet_metadata.get('sheets', []):
                if sheet_info['properties']['title'] == 'Logs':
                    if 'dataSourceSheetProperties' in sheet_info:
                        safe_log_error("[LOGS] Sheet is a connected data source/table. Cannot append.")
                        return
                    # Check for banding (table formatting indicator)
                    if 'bandedRanges' in sheet_info:
                        safe_log_warning("[LOGS] Sheet has table formatting. This may cause issues.")
        except Exception as e:
            safe_log_debug(f"[LOGS] Metadata check failed (non-critical): {e}")

        # Original append (now safer)
        logs_sheet.append_row(log_row)
        safe_log_debug(f"[LOGS] {correlation_id} | Logged conversation")
        
    except Exception as e:
        safe_log_error(f"[LOGS] {correlation_id} | Error: {e}")