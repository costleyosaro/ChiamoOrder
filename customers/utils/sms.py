# utils/sms.py
import requests
from django.conf import settings

def send_sms(to, message):
    """
    Sends an SMS using Termii API.
    :param to: Recipient phone number (e.g., +2348012345678)
    :param message: SMS message string
    """
    url = settings.TERMII_BASE_URL
    payload = {
        "to": to,
        "from": settings.TERMII_SENDER_ID,  # Can also use "Termii" if Sender ID not approved yet
        "sms": message,
        "type": "plain",  # plain, unicode, flash
        "channel": "generic",  # dnd, whatsapp, generic
        "api_key": settings.TERMII_API_KEY
    }

    response = requests.post(url, json=payload)

    try:
        response_data = response.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON response from Termii"}

    if response.status_code == 200 and response_data.get("message") == "Successfully Sent":
        return {"status": "success", "detail": response_data}
    else:
        return {"status": "error", "detail": response_data}
