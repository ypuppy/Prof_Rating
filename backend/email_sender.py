"""
Sends login codes by email.

EMAIL_BACKEND=console  prints the code to the server terminal (default, no setup)
EMAIL_BACKEND=smtp     sends a real email via any SMTP server (Gmail, SES, Resend, ...)
"""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("uvicorn.error")


def send_login_code(to_email: str, code: str, ttl_minutes: int) -> None:
    backend = os.getenv("EMAIL_BACKEND", "console")
    if backend == "console":
        logger.warning("Login code for %s: %s (expires in %d min)", to_email, code, ttl_minutes)
        return
    if backend == "smtp":
        _send_smtp(to_email, code, ttl_minutes)
        return
    raise RuntimeError(f"Unknown EMAIL_BACKEND: {backend!r}")


def _send_smtp(to_email: str, code: str, ttl_minutes: int) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.getenv("SMTP_FROM") or user

    msg = EmailMessage()
    msg["Subject"] = f"Your ProfRating login code: {code}"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(
        f"Your ProfRating login code is {code}\n\n"
        f"It expires in {ttl_minutes} minutes. If you didn't try to log in, you can ignore this email."
    )

    # Port 587 + STARTTLS works for Gmail, Amazon SES and Resend
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
