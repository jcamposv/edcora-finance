#!/usr/bin/env python3
"""
Script para probar la configuración de Twilio WhatsApp
"""
import os
from app.services.whatsapp_service import WhatsAppService

def test_twilio_config():
    """Test Twilio configuration and send a test message."""
    print("🔍 Testing Twilio Configuration...")
    print("=" * 50)
    
    # Check environment variables
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN") 
    whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    
    print(f"📋 TWILIO_ACCOUNT_SID: {'✅ Set' if account_sid else '❌ Missing'}")
    print(f"🔑 TWILIO_AUTH_TOKEN: {'✅ Set' if auth_token else '❌ Missing'}")
    print(f"📞 TWILIO_WHATSAPP_NUMBER: {whatsapp_number}")
    
    if account_sid:
        print(f"📋 Account SID (first 8 chars): {account_sid[:8]}...")
    
    if auth_token:
        print(f"🔑 Auth Token (first 8 chars): {auth_token[:8]}...")
    
    print("\n" + "=" * 50)
    
    # Test WhatsApp service
    whatsapp_service = WhatsAppService()
    
    if not whatsapp_service.client:
        print("❌ WhatsApp service not properly configured!")
        return False
    
    print("✅ WhatsApp service configured successfully!")
    
    # Ask for test number
    test_number = input("\n📱 Enter a test phone number (format: +50612345678): ").strip()
    
    if not test_number:
        print("❌ No test number provided")
        return False
    
    test_message = """🧪 Test message from Edcora Finanzas

This is a test message to verify Twilio WhatsApp integration is working correctly.

If you receive this, the system is working! 🎉"""
    
    print(f"\n📤 Sending test message to {test_number}...")
    
    result = whatsapp_service.send_message(test_number, test_message)
    
    if result:
        print("✅ Test message sent successfully!")
        print("📱 Check the target phone to confirm receipt")
    else:
        print("❌ Failed to send test message")
        print("💡 Check the logs above for error details")
    
    return result

if __name__ == "__main__":
    test_twilio_config()