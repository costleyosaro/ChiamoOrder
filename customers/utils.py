import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.conf import settings


def send_email(to, subject, html_content, plain_text=None):
    """
    Send email using Brevo API (works on Railway!)
    Free: 300 emails/day, no domain verification needed
    """
    api_key = os.getenv('BREVO_API_KEY', '')

    if not api_key:
        print("❌ BREVO_API_KEY not set. Email skipped.")
        return False

    try:
        # Configure API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = api_key
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        # Build email
        sender = {
            "name": "ChiamoOrder",
            "email": os.getenv('SENDER_EMAIL', 'chiamoorder@gmail.com')
        }

        to_list = [{"email": to}] if isinstance(to, str) else [{"email": e} for e in to]

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to_list,
            sender=sender,
            subject=subject,
            html_content=html_content,
            text_content=plain_text or ""
        )

        # Send
        result = api_instance.send_transac_email(send_smtp_email)
        print(f"📩 Email sent to {to} | Message ID: {result.message_id}")
        return True

    except ApiException as e:
        print(f"❌ Brevo email failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    except Exception as e:
        print(f"❌ Email error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False