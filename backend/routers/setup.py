"""
Setup Wizard API
Provides endpoints for initial platform configuration
"""

import datetime
import os
import re
import secrets
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.logger import logger
from backend.models.evaluation.profile import AdminProfile

router = APIRouter(prefix="/setup", tags=["Setup"])


# Pydantic models for setup steps
class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    database: str
    username: str
    password: str

    @field_validator("database")
    @classmethod
    def validate_database_name(cls, v):
        if not v or len(v) < 3:
            raise ValueError("Database name must be at least 3 characters")
        return v


class AdminUser(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    test_email: Optional[str] = None


class APIKeysConfig(BaseModel):
    groq_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


class SetupComplete(BaseModel):
    database: DatabaseConfig
    admin: AdminUser
    email: Optional[EmailConfig] = None
    api_keys: Optional[APIKeysConfig] = None


def is_setup_needed() -> bool:
    """Check if setup is needed"""
    env_path = Path(".env")

    # Setup needed if .env doesn't exist
    if not env_path.exists():
        return True

    # Check if SETUP_COMPLETE flag exists
    try:
        with open(env_path, "r") as f:
            content = f.read()
            if "SETUP_COMPLETE=true" in content:
                return False
    except Exception:
        pass

    return True


def ensure_setup_access(request: Request) -> None:
    """
    Guard setup actions so they cannot be executed remotely after deployment.
    - Setup must still be incomplete.
    - If SETUP_TOKEN is set, requests must provide X-Setup-Token.
    - Without token, only localhost may access setup actions.
    """
    if not is_setup_needed():
        raise HTTPException(status_code=403, detail="Setup has already been completed")

    setup_token = os.getenv("SETUP_TOKEN")
    provided_token = request.headers.get("X-Setup-Token", "")

    if setup_token:
        if not secrets.compare_digest(provided_token, setup_token):
            raise HTTPException(status_code=403, detail="Invalid setup token")
        return

    client_ip = request.client.host if request.client else ""
    if client_ip not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(
            status_code=403,
            detail="Setup endpoints are local-only unless SETUP_TOKEN is configured.",
        )


@router.get("/status")
async def get_setup_status():
    """Check if setup wizard is needed"""
    return {
        "setup_needed": is_setup_needed(),
        "message": "Setup required" if is_setup_needed() else "Setup already completed",
    }


@router.post("/test-database")
async def test_database_connection(config: DatabaseConfig, request: Request):
    """Test database connection"""
    ensure_setup_access(request)
    try:
        # Build connection string
        connection_string = f"mysql+pymysql://{config.username}:{config.password}@{config.host}:{config.port}/{config.database}"

        # Try to connect
        engine = create_engine(connection_string, pool_pre_ping=True)

        with engine.connect() as conn:
            # Test query
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        engine.dispose()

        return {"success": True, "message": "Database connection successful!"}

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages
        if "Access denied" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Access denied. Please check your username and password.",
            )
        elif "Unknown database" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Database '{config.database}' does not exist. Please create it first or use a different name.",
            )
        elif "Can't connect" in error_msg or "Connection refused" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to MySQL server at {config.host}:{config.port}. Please check if MySQL is running.",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Database connection failed. Please check your configuration.",
            )


@router.post("/test-email")
async def test_email_configuration(config: EmailConfig, request: Request):
    """Test email/SMTP configuration"""
    ensure_setup_access(request)
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create test message
        msg = MIMEMultipart()
        msg["From"] = config.smtp_username
        msg["To"] = config.test_email or config.smtp_username
        msg["Subject"] = "Candway Setup - Test Email"

        body = """
        Congratulations!

        Your email configuration is working correctly.

        This is a test email from the Candway Intelligence Platform setup wizard.

        Best regards,
        Candway Team
        """
        msg.attach(MIMEText(body, "plain"))

        # Connect and send
        server = smtplib.SMTP(config.smtp_host, config.smtp_port)
        server.starttls()
        server.login(config.smtp_username, config.smtp_password)
        server.sendmail(
            config.smtp_username,
            config.test_email or config.smtp_username,
            msg.as_string(),
        )
        server.quit()

        return {
            "success": True,
            "message": f"Test email sent successfully to {config.test_email or config.smtp_username}!",
        }

    except Exception as e:
        error_msg = str(e)

        if (
            "Authentication failed" in error_msg
            or "Username and Password not accepted" in error_msg
        ):
            raise HTTPException(
                status_code=400,
                detail="Authentication failed. Please check your email and password/app password.",
            )
        elif "Connection refused" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot connect to SMTP server at {config.smtp_host}:{config.smtp_port}",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Email test failed. Please check your configuration.",
            )


@router.post("/complete")
async def complete_setup(setup: SetupComplete, request: Request):
    """Complete setup and create configuration files"""
    ensure_setup_access(request)

    try:
        # 1. Generate SECRET_KEY
        secret_key = secrets.token_urlsafe(32)

        # 2. Build .env content
        env_content = f"""# Candway Intelligence Platform Configuration
# Generated by Setup Wizard on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Application
APP_NAME=Candway Intelligence
DEBUG=false
SETUP_COMPLETE=false

# Security
SECRET_KEY={secret_key}

# Database
DATABASE_URL=mysql+pymysql://{setup.database.username}:{setup.database.password}@{setup.database.host}:{setup.database.port}/{setup.database.database}

# Admin User (for reference)
ADMIN_EMAIL={setup.admin.email}
ADMIN_NAME={setup.admin.name}
"""

        # 3. Add email configuration if provided
        if setup.email:
            env_content += f"""
# Email/SMTP Configuration
SMTP_HOST={setup.email.smtp_host}
SMTP_PORT={setup.email.smtp_port}
SMTP_USERNAME={setup.email.smtp_username}
SMTP_PASSWORD={setup.email.smtp_password}
"""

        # 4. Add API keys if provided
        if setup.api_keys:
            env_content += "\n# API Keys\n"
            if setup.api_keys.groq_api_key:
                env_content += f"GROQ_API_KEY={setup.api_keys.groq_api_key}\n"
            if setup.api_keys.deepseek_api_key:
                env_content += f"DEEPSEEK_API_KEY={setup.api_keys.deepseek_api_key}\n"
            if setup.api_keys.gemini_api_key:
                env_content += f"GEMINI_API_KEY={setup.api_keys.gemini_api_key}\n"

        # 5. Write .env file
        env_path = Path(".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

        logger.info("✅ .env file created successfully")

        # 6. Initialize database and create admin user
        try:
            from passlib.context import CryptContext

            from backend.database import Base, Company, User

            connection_string = f"mysql+pymysql://{setup.database.username}:{setup.database.password}@{setup.database.host}:{setup.database.port}/{setup.database.database}"
            setup_engine = create_engine(connection_string, pool_pre_ping=True)

            # Create all tables in target database
            Base.metadata.create_all(bind=setup_engine)
            logger.info("✅ Database tables created")

            # Create admin user using the same hashing scheme as login auth
            pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
            SetupSession = sessionmaker(
                autocommit=False, autoflush=False, bind=setup_engine
            )
            db = SetupSession()

            try:
                existing_admin = (
                    db.query(User).filter(User.email == setup.admin.email).first()
                )
                if existing_admin:
                    raise HTTPException(
                        status_code=400, detail="Admin email already exists"
                    )

                admin_user = User(
                    email=setup.admin.email,
                    name=setup.admin.name,
                    hashed_password=pwd_context.hash(setup.admin.password),
                    role="admin",
                    email_verified=True,
                    admin_permissions="all",
                    is_super_admin=True,
                )

                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)

                company = Company(
                    name=f"{setup.admin.name}'s Organization",
                    slug=f"platform-{admin_user.id}",
                    tier="enterprise",
                    subscription_status="active",
                    is_active=True,
                )
                db.add(company)
                db.commit()
                db.refresh(company)

                admin_user.company_id = company.id
                db.commit()

                admin_profile = AdminProfile(
                    user_id=admin_user.id,
                    company_id=company.id,
                    is_super_admin=True,
                    permissions="all",
                )
                db.add(admin_profile)
                db.commit()
            finally:
                db.close()
                setup_engine.dispose()

            logger.info(f"✅ Admin user created: {setup.admin.email}")

        except HTTPException:
            raise
        except Exception as db_error:
            logger.error(f"Database initialization error: {db_error}")
            raise HTTPException(
                status_code=500, detail="Setup failed during database initialization"
            )

        # Mark setup complete only after successful DB/admin setup
        with open(env_path, "r", encoding="utf-8") as f:
            finalized_content = f.read().replace(
                "SETUP_COMPLETE=false", "SETUP_COMPLETE=true", 1
            )
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(finalized_content)

        return {
            "success": True,
            "message": "Setup completed successfully! The platform is ready to use.",
            "admin_email": setup.admin.email,
            "next_step": "Please restart the application and log in with your admin credentials.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Setup completion error: {e}")
        raise HTTPException(
            status_code=500, detail="Setup failed. Check server logs for details."
        )


@router.post("/create-database")
async def create_database(config: DatabaseConfig, request: Request):
    """Attempt to create the database if it doesn't exist"""
    ensure_setup_access(request)
    try:
        # Connect without specifying database
        connection_string = f"mysql+pymysql://{config.username}:{config.password}@{config.host}:{config.port}"
        engine = create_engine(connection_string)

        if not re.match(r"^[a-zA-Z0-9_]+$", config.database):
            raise HTTPException(
                status_code=400,
                detail="Invalid database name: only alphanumeric characters and underscores allowed",
            )
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{config.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()

        engine.dispose()

        return {
            "success": True,
            "message": f"Database '{config.database}' created successfully!",
        }

    except Exception as e:
        logger.error(f"Failed to create database: {e}")
        raise HTTPException(
            status_code=400,
            detail="Failed to create database. Please check your configuration.",
        )
