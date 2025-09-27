import os
import smtplib
import ssl
import asyncio
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

class MailerService:
    @staticmethod
    async def send_email(to: str, subject: str, body: str):
        mail_server = os.getenv("MAIL_SERVER", "smtp.gmail.com")
        mail_port = int(os.getenv("MAIL_PORT", 587))
        mail_username = os.getenv("MAIL_USERNAME")
        mail_password = os.getenv("MAIL_PASSWORD")
        mail_sender = os.getenv("MAIL_DEFAULT_SENDER", mail_username)

        msg = EmailMessage()
        msg["From"] = mail_sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        context = ssl.create_default_context()

        def _send():
            with smtplib.SMTP(mail_server, mail_port) as server:
                if os.getenv("MAIL_USE_TLS", "false").lower() == "true":
                    server.starttls(context=context)
                server.login(mail_username, mail_password)
                server.send_message(msg)

        try:
            await asyncio.to_thread(_send)
        except Exception as e:
            raise RuntimeError(f"Email sending failed: {str(e)}")
