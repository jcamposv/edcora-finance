import random
import string
from datetime import datetime, timedelta
from typing import Optional, Dict

class OTPService:
    def __init__(self):
        # In production, this should be a proper cache like Redis
        self.otp_storage: Dict[str, Dict] = {}
    
    def generate_otp(self, phone_number: str) -> str:
        """Generate a 6-digit OTP for phone number."""
        otp = ''.join(random.choices(string.digits, k=6))
        
        # Store OTP with expiration time (5 minutes)
        self.otp_storage[phone_number] = {
            'code': otp,
            'expires_at': datetime.now() + timedelta(minutes=5),
            'attempts': 0
        }
        
        return otp
    
    def verify_otp(self, phone_number: str, provided_otp: str) -> bool:
        """Verify OTP for phone number."""
        if phone_number not in self.otp_storage:
            return False
        
        otp_data = self.otp_storage[phone_number]
        
        # Check if OTP has expired
        if datetime.now() > otp_data['expires_at']:
            del self.otp_storage[phone_number]
            return False
        
        # Check attempts limit (max 3 attempts)
        if otp_data['attempts'] >= 3:
            del self.otp_storage[phone_number]
            return False
        
        # Increment attempts
        otp_data['attempts'] += 1
        
        # Verify OTP
        if otp_data['code'] == provided_otp:
            # OTP is correct, remove from storage
            del self.otp_storage[phone_number]
            return True
        
        return False
    
    def cleanup_expired_otps(self):
        """Remove expired OTPs from storage."""
        current_time = datetime.now()
        expired_numbers = []
        
        for phone_number, otp_data in self.otp_storage.items():
            if current_time > otp_data['expires_at']:
                expired_numbers.append(phone_number)
        
        for phone_number in expired_numbers:
            del self.otp_storage[phone_number]