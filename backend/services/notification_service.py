import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from core.config import settings
from services.whatsapp_service import WhatsAppService
from models.lead import Lead  # ✅ Add this import
from models.booking import Booking  # ✅ Add this import

logger = logging.getLogger(__name__)

async def send_lead_notification(lead: Lead):  # ✅ Accept Lead object, not dict
    """Send lead notification to owner"""
    try:
        # ✅ Convert Lead object to dict if needed
        lead_data = lead.dict() if hasattr(lead, 'dict') else lead
        
        # Send Email
        if settings.OWNER_EMAIL:
            await send_email(
                to=settings.OWNER_EMAIL,
                subject=f"🔔 New Lead: {lead_data.get('name')}",
                body=f"""
                New Lead Details:
                
                Name: {lead_data.get('name')}
                Phone: {lead_data.get('phone')}
                Email: {lead_data.get('email') or 'Not provided'}
                Service Interest: {lead_data.get('service_interest')}
                Source: {lead_data.get('source')}
                Created: {lead_data.get('created_at')}
                
                Summary: {lead_data.get('conversation_summary')}
                """
            )
        
        # Send WhatsApp
        if settings.OWNER_PHONE:
            whatsapp = WhatsAppService()
            message = f"🔔 New Lead!\n\nName: {lead_data.get('name')}\nPhone: {lead_data.get('phone')}\nInterest: {lead_data.get('service_interest')}"
            await whatsapp.send_message(settings.OWNER_PHONE, message)
        
        logger.info(f"Lead notification sent for {lead_data.get('name')}")
        
    except Exception as e:
        logger.error(f"Error sending lead notification: {str(e)}")

async def send_booking_notification(booking_data: Dict[str, Any]):
    """Send booking notification to owner"""
    try:
        message = f"""
        📅 New Booking Confirmed!
        
        Customer: {booking_data.get('customer_name')}
        Phone: {booking_data.get('whatsapp_number')}
        Service: {booking_data.get('service_type')}
        Date: {booking_data.get('preferred_date')}
        Time: {booking_data.get('preferred_time')}
        Mode: {booking_data.get('mode')}
        Reason: {booking_data.get('reason', 'Not specified')}
        """
        
        # Send Email
        if settings.OWNER_EMAIL:
            await send_email(
                to=settings.OWNER_EMAIL,
                subject=f"📅 New Booking: {booking_data.get('customer_name')}",
                body=message
            )
        
        # Send WhatsApp
        if settings.OWNER_PHONE:
            whatsapp = WhatsAppService()
            await whatsapp.send_message(settings.OWNER_PHONE, message[:4096])  # WhatsApp limit
        
        logger.info(f"Booking notification sent for {booking_data.get('customer_name')}")
        
    except Exception as e:
        logger.error(f"Error sending booking notification: {str(e)}")

async def send_handoff_notification(chat_id: str, conversation: Dict):
    """Send human handoff notification to owner"""
    try:
        context = conversation.get("context", {})
        message = f"""
        🤝 Human Handoff Requested!
        
        Chat ID: {chat_id}
        User: {context.get('name', 'Unknown')}
        Phone: {context.get('phone', 'Unknown')}
        Phase: {conversation.get('phase')}
        
        Please check the conversation and respond.
        """
        
        if settings.OWNER_EMAIL:
            await send_email(
                to=settings.OWNER_EMAIL,
                subject=f"🤝 Handoff Request from {context.get('name', 'Unknown')}",
                body=message
            )
        
        if settings.OWNER_PHONE:
            whatsapp = WhatsAppService()
            await whatsapp.send_message(
                settings.OWNER_PHONE,
                f"🤝 Handoff Request from {context.get('name', 'Unknown')}. Please check your email."
            )
        
        logger.info(f"Handoff notification sent for {chat_id}")
        
    except Exception as e:
        logger.error(f"Error sending handoff notification: {str(e)}")

async def send_email(to: str, subject: str, body: str):
    """Send email using SMTP"""
    try:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured")
            return
        
        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_SENDER or settings.SMTP_USER
        msg['To'] = to
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent to {to}")
        
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise