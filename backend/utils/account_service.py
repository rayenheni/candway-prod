import logging
import secrets
import string

from sqlalchemy.orm import Session

from backend.database import User
from backend.dependencies import pwd_context

logger = logging.getLogger("candway_app")


def generate_random_password(length: int = 10) -> str:
    """Generate a secure random password for candidates."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_candidate_account(
    db: Session, email: str, name: str = "Candidate"
) -> tuple[User, str]:
    """
    Ensures a candidate user account exists.
    If new, generates a temporary password.
    Returns (User, plain_password or None).
    """
    # Search for user (including legacy soft-deleted ones that weren't renamed)
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if user:
        if user.deleted_at:
            # Reclaim legacy deleted user
            user.deleted_at = None
            temp_pass = secrets.token_urlsafe(10)
            user.hashed_password = pwd_context.hash(temp_pass)
            user.temp_password = temp_pass
            db.commit()
            return user, temp_pass

        # Active user exists. Check if they have a password (might be a shadow user).
        if not user.hashed_password:
            # Shadow user without password - generate one
            password = generate_random_password()
            user.hashed_password = pwd_context.hash(password)
            user.temp_password = password  # Persist for recruiter visibility
            db.commit()
            return user, password

        # If a temp_password is still stored, the user was created by the batch
        # worker and has never signed in yet — treat them as a new invite and
        # surface the existing temp password so the email includes credentials.
        if user.temp_password:
            return user, user.temp_password

        return user, None  # Already has a real (self-set) password

    # Create new user
    password = generate_random_password()
    new_user = User(
        email=email,
        name=name,
        role="candidate",
        hashed_password=pwd_context.hash(password),
        temp_password=password,  # Persist for recruiter visibility
        email_verified=True,  # Pre-verified since it's an invite
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Created new candidate account for {email} with generated password.")
    return new_user, password
