"""
Email Service — Gmail SMTP
Sends notifications to property dealers when:
1. A lead enquires about an unavailable property type
2. A meeting is scheduled / deal is closed
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _get_smtp_connection():
    """Create Gmail SMTP connection"""
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')  # App password, not login password

    if not gmail_user or not gmail_password:
        logger.error("[EMAIL] GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
        return None, None

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        return server, gmail_user
    except Exception as e:
        logger.error(f"[EMAIL] SMTP connection failed: {e}")
        return None, None


def send_villa_enquiry_notification(
    dealer_email: str,
    client_name: str,
    client_phone: str,
    client_email: str,
    requested_type: str,
    city: str,
    budget: str
):
    """
    Send email to dealer when client enquires about unavailable property type.
    Bot will notify: "A client is looking for a Villa — we don't have one currently."
    """
    server, gmail_user = _get_smtp_connection()
    if not server:
        return False

    try:
        subject = f"🏠 New Enquiry — {requested_type} in {city}"

        html_body = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #2c3e50;">New Property Enquiry</h2>
            <p>A potential client is looking for a <strong>{requested_type}</strong> in <strong>{city}</strong>.</p>
            
            <table style="width:100%; border-collapse: collapse; margin-top: 16px;">
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Client Name</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_name}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Phone</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_phone}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Email</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_email}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Property Type</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{requested_type}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>City</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{city}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Budget</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{budget}</td>
                </tr>
            </table>

            <p style="margin-top:20px; color:#666;">
                This client was informed that we currently don't have {requested_type} listings available.
                Their contact details have been saved — please follow up when a {requested_type} becomes available.
            </p>
            <p style="color:#999; font-size:12px;">Sent by your WhatsApp Property Bot</p>
        </div>
        </body></html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = gmail_user
        msg['To'] = dealer_email
        msg.attach(MIMEText(html_body, 'html'))

        server.sendmail(gmail_user, dealer_email, msg.as_string())
        server.quit()

        logger.info(f"[EMAIL] ✅ Villa enquiry notification sent to {dealer_email}")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] ❌ Failed to send villa enquiry email: {e}")
        return False


def send_meeting_confirmation(
    dealer_email: str,
    client_name: str,
    client_phone: str,
    client_email: str,
    property_name: str,
    property_type: str,
    city: str,
    meeting_date: str,
    meeting_time: str,
    budget: str,
    calendar_link: str = None
):
    """
    Send meeting confirmation email to dealer when deal is closed.
    """
    server, gmail_user = _get_smtp_connection()
    if not server:
        return False

    try:
        subject = f"🎉 Meeting Scheduled — {client_name} | {property_name}"

        calendar_section = ""
        if calendar_link:
            calendar_section = f"""
            <p style="margin-top:16px;">
                <a href="{calendar_link}" style="background:#4285f4; color:white; padding:10px 20px; 
                border-radius:4px; text-decoration:none;">📅 Add to Google Calendar</a>
            </p>
            """

        html_body = f"""
        <html><body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #27ae60;">✅ Meeting Confirmed!</h2>
            <p>A client has shown strong interest and a meeting has been scheduled.</p>

            <h3 style="color:#2c3e50; margin-top:20px;">📋 Meeting Details</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Date</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{meeting_date}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Time</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{meeting_time}</td>
                </tr>
            </table>

            <h3 style="color:#2c3e50; margin-top:20px;">👤 Client Details</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Name</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_name}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Phone</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_phone}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Email</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{client_email}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Budget</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{budget}</td>
                </tr>
            </table>

            <h3 style="color:#2c3e50; margin-top:20px;">🏠 Property Details</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Property</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{property_name}</td>
                </tr>
                <tr>
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>Type</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{property_type}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border:1px solid #dee2e6;"><strong>City</strong></td>
                    <td style="padding:10px; border:1px solid #dee2e6;">{city}</td>
                </tr>
            </table>

            {calendar_section}

            <p style="margin-top:20px; color:#666;">Please be prepared for the meeting and follow up with the client if needed.</p>
            <p style="color:#999; font-size:12px;">Sent by your WhatsApp Property Bot</p>
        </div>
        </body></html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = gmail_user
        msg['To'] = dealer_email
        msg.attach(MIMEText(html_body, 'html'))

        server.sendmail(gmail_user, dealer_email, msg.as_string())
        server.quit()

        logger.info(f"[EMAIL] ✅ Meeting confirmation sent to {dealer_email}")
        return True

    except Exception as e:
        logger.error(f"[EMAIL] ❌ Failed to send meeting email: {e}")
        return False