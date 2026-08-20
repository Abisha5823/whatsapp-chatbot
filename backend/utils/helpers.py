import re
from typing import Tuple, Optional
import emoji
import unicodedata

def detect_language(text: str) -> str:
    """Detect if text is Tamil, Tanglish, or English"""
    # Check for Tamil script
    if any('\u0B80' <= char <= '\u0BFF' for char in text):
        return "ta"  # Tamil
    
    # Check for Tanglish (Tamil words in English script)
    tamil_words = [
        "unga", "nan", "nee", "avan", "aval", 
        "solar", "battery", "inverter", "installation",
        "sol", "batt", "inv", "instal"
    ]
    text_lower = text.lower()
    if any(word in text_lower for word in tamil_words):
        # Likely Tanglish
        return "ta"  # Tamil/Tanglish
    
    return "en"  # English

def format_response_for_language(response: str, language: str) -> str:
    """Format response for the detected language"""
    if language == "ta":
        # Add Tamil-specific formatting
        response = response.replace(":", " : ")
        # Ensure proper script if needed
    return response

def validate_phone_number(phone: str) -> bool:
    """Validate Indian phone number"""
    # Remove any non-digit characters
    phone = re.sub(r'\D', '', phone)
    
    # Check if it's a valid Indian number
    if len(phone) == 10:
        return True
    elif len(phone) == 12 and phone.startswith("91"):
        return True
    
    return False

def validate_email(email: str) -> bool:
    """Validate email address"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def extract_name_from_message(text: str) -> Optional[str]:
    """Extract name from message"""
    # Look for patterns like "My name is X" or "I'm X"
    patterns = [
        r'(?:my\s+name\s+is\s+)(\w+)',
        r'(?:i\s+am\s+)(\w+)',
        r'(?:i\'m\s+)(\w+)',
        r'(?:this\s+is\s+)(\w+)',
        r'^(\w+)\s*$',  # Single word message
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            return match.group(1).capitalize()
    
    return None

def extract_phone_from_message(text: str) -> Optional[str]:
    """Extract phone number from message"""
    # Look for 10-digit or 12-digit (with country code) numbers
    pattern = r'(\+?\d{10,12})'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def extract_email_from_message(text: str) -> Optional[str]:
    """Extract email from message"""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def sanitize_input(text: str) -> str:
    """Sanitize user input"""
    # Remove emojis (for processing)
    text = emoji.replace_emoji(text, '')
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    # Remove special characters (keep alphanumeric, spaces, common punctuation)
    text = re.sub(r'[^\w\s.,!?@-]', '', text)
    
    return text

def format_currency(amount: float, currency: str = "₹") -> str:
    """Format currency amount"""
    return f"{currency} {amount:,.2f}"

def calculate_solar_system(load_kwh: float, peak_sun_hours: float = 6.0) -> dict:
    """Calculate solar system requirements"""
    system_kw = load_kwh / peak_sun_hours
    panels_needed = system_kw / 0.5  # Assuming 500W panels
    estimated_cost = system_kw * 60000  # ₹60,000 per kW
    
    return {
        "system_kw": round(system_kw, 2),
        "panels_needed": round(panels_needed, 2),
        "estimated_cost": round(estimated_cost, 2),
        "recommendation": f"Recommended: {round(system_kw, 2)} kW system"
    }

def calculate_battery(load_w: float, backup_hours: float, voltage: float = 12) -> dict:
    """Calculate battery requirements"""
    ah_needed = (load_w * backup_hours) / voltage
    # Add 20% buffer
    ah_with_buffer = ah_needed * 1.2
    
    return {
        "ah_needed": round(ah_needed, 2),
        "ah_with_buffer": round(ah_with_buffer, 2),
        "recommendation": f"Recommended: {round(ah_with_buffer, 2)} Ah battery"
    }

def calculate_eb_bill_savings(current_bill: float, solar_generated_units: float, tariff: float = 6.5) -> dict:
    """Calculate EB bill savings"""
    potential_savings = solar_generated_units * tariff
    new_bill = max(0, current_bill - potential_savings)
    
    return {
        "potential_savings": round(potential_savings, 2),
        "new_bill": round(new_bill, 2),
        "savings_percentage": round((potential_savings / current_bill) * 100, 2) if current_bill > 0 else 0
    }

def get_time_slots(date: str, business_hours: Tuple[str, str] = ("09:00", "18:00")) -> list:
    """Get available time slots for a date"""
    # Simplified - would integrate with calendar in production
    slots = []
    start_hour, start_min = map(int, business_hours[0].split(":"))
    end_hour, end_min = map(int, business_hours[1].split(":"))
    
    current_hour = start_hour
    while current_hour < end_hour:
        slots.append(f"{current_hour}:00")
        current_hour += 1
        if current_hour == 13:  # Skip 1 PM (lunch break)
            current_hour = 14
    
    return slots