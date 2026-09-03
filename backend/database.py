"""SQLAlchemy model definitions — all classes re-exported from backend.models.

This module is a backward-compatibility layer. All model classes are now
defined in domain-specific modules under backend/models/.

Usage::

    from backend.database import User, Job, SessionLocal, get_db
"""

# Re-export all model classes and utilities from the modular package
from backend.encryption import EncryptedText  # noqa: F401
from backend.models import *  # noqa: F401, F403, E402

# Preserve explicit re-exports for clarity
from backend.models.base import (  # noqa: F401, F401, F401, F401, F401, F401, F401
    DATABASE_URL,
    Base,
    SessionLocal,
    TenantMixin,
    engine,
    get_db,
    utcnow,
)
