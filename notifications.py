import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests


def _resend_config():
    return {
        "api_key": os.getenv("RESEND_API_KEY", ""),
        "from_email": os.getenv("RESEND_FROM_EMAIL", ""),
        "timeout": float(os.getenv("RESEND_TIMEOUT", "10")),
    }

def _brevo_config():
    return {
        "api_key": os.getenv("BREVO_API_KEY", ""),
        "from_email": os.getenv("BREVO_FROM_EMAIL", ""),
        "from_name": os.getenv("BREVO_FROM_NAME", ""),
        "timeout": float(os.getenv("BREVO_TIMEOUT", "10")),
    }


def _smtp_config():
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASS", ""),
        "from_email": os.getenv("FROM_EMAIL", os.getenv("SMTP_USER", "")),
        "timeout": float(os.getenv("SMTP_TIMEOUT", "10")),
    }


def send_email(to_email, subject, body, enabled=True):
    if not enabled:
        return False

    brevo_cfg = _brevo_config()
    if brevo_cfg["api_key"] and brevo_cfg["from_email"] and to_email:
        try:
            sender = {"email": brevo_cfg["from_email"]}
            if brevo_cfg["from_name"]:
                sender["name"] = brevo_cfg["from_name"]
            res = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "api-key": brevo_cfg["api_key"],
                    "content-type": "application/json",
                },
                json={
                    "sender": sender,
                    "to": [{"email": to_email}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=brevo_cfg["timeout"],
            )
            if os.getenv("NOTIFY_DEBUG") == "1":
                print(f"Brevo response {res.status_code}: {res.text[:200]}")
            return 200 <= res.status_code < 300
        except Exception as exc:
            if os.getenv("NOTIFY_DEBUG") == "1":
                print(f"Brevo send failed: {exc}")
            return False

    resend_cfg = _resend_config()
    if resend_cfg["api_key"] and resend_cfg["from_email"] and to_email:
        try:
            res = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": resend_cfg["from_email"],
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=resend_cfg["timeout"],
            )
            if os.getenv("NOTIFY_DEBUG") == "1":
                print(f"Resend response {res.status_code}: {res.text[:200]}")
            return 200 <= res.status_code < 300
        except Exception as exc:
            if os.getenv("NOTIFY_DEBUG") == "1":
                print(f"Resend send failed: {exc}")
            return False

    cfg = _smtp_config()
    if not cfg["host"] or not cfg["user"] or not cfg["password"] or not to_email:
        if os.getenv("NOTIFY_DEBUG") == "1":
            print("Email not sent: missing SMTP config or recipient.")
        return False

    msg = MIMEMultipart()
    msg["From"] = cfg["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        # Port 465 expects implicit TLS, while 587 uses STARTTLS.
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=cfg["timeout"]) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], to_email, msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=cfg["timeout"]) as server:
                server.starttls()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], to_email, msg.as_string())
        if os.getenv("NOTIFY_DEBUG") == "1":
            print(f"Email sent to {to_email}")
        return True
    except Exception as exc:
        if os.getenv("NOTIFY_DEBUG") == "1":
            print(f"Email send failed: {exc}")
        return False


def send_sms(phone, message, enabled=True):
    if not enabled:
        return False

    api_key = os.getenv("TERMII_API_KEY", "")
    sender_id = os.getenv("TERMII_SENDER_ID", "")
    if not api_key or not sender_id or not phone:
        if os.getenv("NOTIFY_DEBUG") == "1":
            print("SMS not sent: missing Termii config or phone.")
        return False

    payload = {
        "to": phone,
        "from": sender_id,
        "sms": message,
        "type": "plain",
        "channel": "generic",
        "api_key": api_key,
    }
    try:
        res = requests.post("https://api.ng.termii.com/api/sms/send", json=payload, timeout=20)
        if os.getenv("NOTIFY_DEBUG") == "1":
            print(f"SMS response {res.status_code}: {res.text[:200]}")
        return res.status_code == 200
    except Exception as exc:
        if os.getenv("NOTIFY_DEBUG") == "1":
            print(f"SMS send failed: {exc}")
        return False


def notify_user(user, subject, email_body, sms_body):
    if not user:
        return False

    email_ok = send_email(user.email, subject, email_body, enabled=user.notify_email)
    sms_ok = send_sms(user.phone, sms_body, enabled=user.notify_sms)
    return email_ok or sms_ok
