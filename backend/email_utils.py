from backend.logger import logger


def send_email(to_email: str, subject: str, body: str):
    from backend.email_service import email_service

    try:
        email_service.send_email(to_email, subject, body)
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False
