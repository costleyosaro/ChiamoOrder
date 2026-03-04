import resend
import os
from django.conf import settings


def send_email(to, subject, html_content, plain_text=None):
    """
    Send email using Resend API (works on Railway!)
    """
    api_key = getattr(settings, 'RESEND_API_KEY', '') or os.getenv('RESEND_API_KEY', '')

    if not api_key:
        print("❌ RESEND_API_KEY not set. Email skipped.")
        return False

    try:
        resend.api_key = api_key

        params = {
            "from": getattr(settings, 'DEFAULT_FROM_EMAIL', 'ChiamoOrder <onboarding@resend.dev>'),
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html_content,
        }

        if plain_text:
            params["text"] = plain_text

        result = resend.Emails.send(params)
        print(f"📩 Email sent to {to} | ID: {result.get('id', 'unknown')}")
        return True

    except Exception as e:
        print(f"❌ Resend email failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False