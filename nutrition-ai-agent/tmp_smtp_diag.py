from app.config import get_settings
import smtplib

s = get_settings()
password = s.smtp_password or ""
print("username:", repr(s.smtp_username))
print("from_email:", repr(s.smtp_from_email))
print("password_length:", len(password))
print("password_has_double_quote:", '"' in password)
print("password_has_single_quote:", "'" in password)
print("password_is_16_alnum:", len(password) == 16 and password.isalnum())

try:
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as server:
        server.ehlo()
        if s.smtp_use_tls:
            server.starttls()
            server.ehlo()
        server.login(s.smtp_username, s.smtp_password)
    print("LOGIN_OK")
except Exception as exc:
    print("LOGIN_ERROR:", type(exc).__name__, repr(exc))
