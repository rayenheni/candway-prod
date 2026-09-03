"""
Password validation utilities for security compliance
Implements NIST password guidelines
"""

import re

from fastapi import HTTPException

# Common passwords to reject (top 100)
COMMON_PASSWORDS = [
    "password",
    "123456",
    "123456789",
    "12345678",
    "12345",
    "1234567",
    "password1",
    "12345678",
    "qwerty",
    "abc123",
    "monkey",
    "1234567890",
    "letmein",
    "trustno1",
    "dragon",
    "baseball",
    "111111",
    "iloveyou",
    "master",
    "sunshine",
    "ashley",
    "bailey",
    "passw0rd",
    "shadow",
    "123123",
    "654321",
    "superman",
    "qazwsx",
    "michael",
    "football",
    "welcome",
    "jesus",
    "ninja",
    "mustang",
    "password123",
    "admin",
    "root",
    "toor",
    "pass",
    "test",
    "guest",
    "info",
    "adm",
    "mysql",
    "user",
    "administrator",
    "oracle",
    "ftp",
    "pi",
    "puppet",
    "ansible",
    "ec2-user",
    "vagrant",
    "azureuser",
    "admin123",
    "root123",
    "pass123",
    "demo",
    "test123",
]


# Hard limit of the bcrypt scheme (backend/dependencies.py pwd_context):
# bcrypt only processes the first 72 BYTES and, since the bcrypt>=4.1
# release line, RAISES ValueError on longer input instead of truncating.
# Byte-based on purpose: multibyte passwords can exceed the limit while
# looking short in characters.
MAX_PASSWORD_BYTES = 72


def validate_password(password: str) -> None:
    """
    Validate password strength according to security best practices.

    Requirements:
    - Minimum 8 characters
    - Maximum 72 bytes (UTF-8 encoded; bcrypt hard limit)
    - Not in common password list

    Raises:
        HTTPException: If password doesn't meet requirements (400)
    """

    # Check minimum length
    if len(password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters long"
        )

    # Check maximum size against the bcrypt hard limit. Oversized passwords
    # are REJECTED here so every password-set endpoint fails with a clean
    # 400 before reaching pwd_context.hash(); they are never truncated.
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Password too long (maximum {MAX_PASSWORD_BYTES} bytes)",
        )

    # Check against common passwords
    if password.lower() in COMMON_PASSWORDS:
        raise HTTPException(
            status_code=400,
            detail="Password is too common. Please choose a stronger password.",
        )

    # Under pure NIST SP 800-63B guidelines, arbitrary complexity requirements
    # (requiring uppercase, lowercase, special characters) are strongly discouraged
    # because they promote less secure, predictable passwords.
    # Therefore, we only enforce length and check against compromised/common lists.


def validate_email(email: str) -> None:
    """
    Validate email format.

    Raises:
        HTTPException: If email is invalid
    """
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_pattern, email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Check for disposable email domains
    disposable_domains = [
        "tempmail.com",
        "throwaway.email",
        "guerrillamail.com",
        "10minutemail.com",
        "mailinator.com",
        "trashmail.com",
        "fakeinbox.com",
        "yopmail.com",
    ]

    domain = email.split("@")[1].lower()
    if domain in disposable_domains:
        raise HTTPException(
            status_code=400, detail="Disposable email addresses are not allowed"
        )
