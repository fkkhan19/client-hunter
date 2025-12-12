# app/sender/whatsapp_sender.py

import time

def send_whatsapp(phone, message):
    """
    phone: string (phone number)
    message: string (text to send)
    """
    if not phone:
        print("❌ WhatsApp send failed: no phone number provided")
        return False

    try:
        # TODO: integrate your actual WhatsApp API here
        # This is placeholder logging so scheduler doesn’t crash
        print(f"📤 (SIMULATED) WhatsApp message to {phone}: {message[:40]}...")
        time.sleep(1)
        return True

    except Exception as e:
        print("❌ WhatsApp send error:", e)
        return False
