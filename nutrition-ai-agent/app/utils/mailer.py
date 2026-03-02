import smtplib
from email.message import EmailMessage

from app.config import get_settings


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
	settings = get_settings()
	if not settings.smtp_host or not settings.smtp_from_email:
		raise RuntimeError("SMTP is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
	has_username = bool(settings.smtp_username)
	has_password = bool(settings.smtp_password)
	if has_username != has_password:
		raise RuntimeError("SMTP authentication is partially configured. Set both SMTP_USERNAME and SMTP_PASSWORD.")

	message = EmailMessage()
	message["Subject"] = subject
	message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>" if settings.smtp_from_name else settings.smtp_from_email
	message["To"] = to_email
	message.set_content(text_body)
	if html_body:
		message.add_alternative(html_body, subtype="html")

	if settings.smtp_use_ssl:
		with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as server:
			if has_username:
				server.login(settings.smtp_username, settings.smtp_password)
			server.send_message(message)
		return

	with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
		server.ehlo()
		if settings.smtp_use_tls:
			server.starttls()
			server.ehlo()
		if has_username:
			server.login(settings.smtp_username, settings.smtp_password)
		server.send_message(message)
