"""
AI Prompts & Message Templates
================================
All bot responses in ONE place. Edit here without touching main.py or flow.

Templates use Python format strings: {variable_name}
"""

# ============================================================================
# GREETING (MSG 1)
# ============================================================================
GREETING_TEMPLATE = (
    "Hi {name}! 👋 I'm Selvora, your property consultant.\n\n"
    "Which city interests you for your property search? 🏙️"
)

# ============================================================================
# CITY HANDLING
# ============================================================================
CITY_RECEIVED_TEMPLATE = (
    "Great choice! {city} offers fantastic opportunities. ✨\n\n"
    "Is this purchase for *investment* or *personal use*?"
)

INVALID_CITY_TEMPLATE = (
    "I'd love to help! Could you mention which city you're interested in?\n"
    "We have great options in: {cities} 🌆"
)

# ============================================================================
# PURPOSE HANDLING
# ============================================================================
PURPOSE_RECEIVED_TEMPLATE = (
    "Excellent! {purpose} is a great choice.\n\n"
    "What type of property are you looking for? We have:\n"
    "*{types}*"
)

INVALID_PURPOSE_TEMPLATE = (
    "Could you let me know if this is for *investment* or *personal use*? 🤔\n"
    "Just reply with one of those options!"
)

# ============================================================================
# PROPERTY TYPE HANDLING
# ============================================================================
TYPE_AVAILABLE_TEMPLATE = (
    "Perfect! {prop_type}s are an excellent choice. 🏡\n\n"
    "What budget range are you working with? Please share in AED.\n"
    "(e.g., 100,000 AED or 200,000 AED) 💰"
)

TYPE_UNAVAILABLE_TEMPLATE = (
    "I completely understand — {requested}s are an excellent choice! 👍\n\n"
    "However, I want to be upfront with you: at the moment, our portfolio "
    "doesn't include {requested}s. We currently specialize in:\n"
    "*{available_types}*\n\n"
    "These offer a similar luxury lifestyle and strong ROI. "
    "Would you be open to exploring one of these? "
    "Just reply with your preferred type!"
)

INVALID_TYPE_TEMPLATE = (
    "Could you please specify the type? We have these options:\n"
    "*{types}*\n\n"
    "Which one interests you? 🏠"
)

# ============================================================================
# BUDGET HANDLING
# ============================================================================
BUDGET_RECEIVED_TEMPLATE = (
    "Thank you for sharing your budget of AED {budget}! 💰\n\n"
    "Where should I send you the detailed brochures? "
    "Please share your email address. 📧"
)

INVALID_BUDGET_TEMPLATE = (
    "Could you share your budget in AED? For example:\n"
    "• 100,000 AED\n"
    "• 250,000 AED\n"
    "• 1.5 million AED 💰"
)

# ============================================================================
# EMAIL HANDLING
# ============================================================================
EMAIL_RECEIVED_TEMPLATE = (
    "Thank you! I've noted your email. 📧\n\n"
    "Based on your budget of AED {budget}, here's a fantastic property that "
    "matches your criteria perfectly. Take a look! 👇"
)

INVALID_EMAIL_TEMPLATE = (
    "That doesn't look like a valid email. Could you please share it again?\n"
    "Example: yourname@example.com 📧"
)

# ============================================================================
# FEEDBACK HANDLING (After property shown)
# ============================================================================
LIKED_PROPERTY_TEMPLATE = (
    "Wonderful, {title}! 🎉\n\n"
    "Let's schedule a quick 15-minute call with our specialist to discuss "
    "this property in detail.\n\n"
    "Please share your preferred date and time in this format:\n"
    "📅 *Date:* DD-MM-YYYY (e.g., 05-05-2026)\n"
    "⏰ *Time:* HH:MM AM/PM (e.g., 06:00 PM)\n\n"
    "Example: '05-05-2026 at 06:00 PM'"
)

DISLIKED_PROPERTY_TEMPLATE = (
    "No problem! Let me find you better options. 🔍\n\n"
    "Here are some alternatives within your budget range "
    "(AED {budget_min} - AED {budget_max}):\n\n"
    "{alternatives}\n"
    "Which one would you like to see in detail? "
    "Reply with the number (1, 2, or 3) 😊"
)

UNCLEAR_FEEDBACK_TEMPLATE = (
    "Could you let me know if you're interested in this property?\n\n"
    "• Reply *yes* to schedule a viewing\n"
    "• Reply *no* to see other options"
)

# ============================================================================
# MEETING DATE/TIME HANDLING
# ============================================================================
MEETING_CONFIRMED_TEMPLATE = (
    "Perfect! ✅ Meeting confirmed for *{date} at {time}* 📅\n\n"
    "You'll receive a calendar invite at your email shortly.\n"
    "See you then! 😊"
)

INVALID_DATETIME_TEMPLATE = (
    "I want to make sure I get your meeting time exactly right! 😊\n\n"
    "Could you please share in this format?\n"
    "📅 *Date:* DD-MM-YYYY (e.g., 05-05-2026)\n"
    "⏰ *Time:* HH:MM AM/PM (e.g., 06:00 PM)\n\n"
    "Example: '05-05-2026 at 06:00 PM'"
)

YEAR_CONFIRMATION_TEMPLATE = (
    "Just to confirm — you mean *{date}*? 📅\n"
    "Could you share the full date in DD-MM-YYYY format to be sure?\n\n"
    "Example: '05-05-2026 at 06:00 PM'"
)