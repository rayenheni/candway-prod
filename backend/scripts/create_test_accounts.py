"""Create test accounts — handles missing tables directly."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt
from sqlalchemy import text

from backend.database import SessionLocal, engine
from backend.models.base import utcnow
from backend.models.evaluation.profile import AdminProfile, RecruiterProfile
from backend.models.foundation.company import Company, CompanyMember
from backend.models.foundation.user import User


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_missing_tables():
    """Create only the tables needed for accounts, skipping FK if target missing."""
    with engine.connect() as conn:
        existing = set(r[0] for r in conn.execute(text("SHOW TABLES")).fetchall())
        needed = {
            "companies",
            "company_members",
            "admin_profiles",
            "recruiter_profiles",
        }
        if needed.issubset(existing):
            return
        print(f"Existing tables: {len(existing)}, creating missing ones...")
        # Create companies
        if "companies" not in existing:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) NOT NULL UNIQUE,
                    domain VARCHAR(255),
                    tier VARCHAR(50) DEFAULT 'free',
                    subscription_status VARCHAR(50) DEFAULT 'active',
                    max_users INTEGER DEFAULT 10,
                    max_jobs INTEGER DEFAULT 50,
                    max_ai_interviews INTEGER DEFAULT 500,
                    logo_url VARCHAR(500),
                    primary_color VARCHAR(7),
                    is_active TINYINT(1) DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    deleted_at DATETIME,
                    INDEX idx_companies_slug (slug),
                    INDEX idx_companies_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            )
            print("  Created: companies")
        # Create company_members
        if "company_members" not in existing:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS company_members (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    company_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(50) DEFAULT 'member',
                    permissions TEXT,
                    invited_at DATETIME,
                    joined_at DATETIME,
                    is_active TINYINT(1) DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_company_member (company_id, user_id),
                    INDEX idx_company_members_role (role),
                    INDEX idx_company_members_user_active (user_id, is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            )
            print("  Created: company_members")
        conn.commit()


def main():
    create_missing_tables()

    db = SessionLocal()

    company = db.query(Company).filter(Company.slug == "candway-demo").first()
    if not company:
        company = Company(
            name="Candway Demo", slug="candway-demo", tier="pro", max_users=100
        )
        db.add(company)
        db.flush()
        print(f"Created company: {company.name} (id={company.id})")
    else:
        print(f"Using existing company: {company.name} (id={company.id})")

    users_data = [
        {
            "email": "admin@candway.dev",
            "password": "admin123",
            "role": "admin",
            "name": "Admin User",
            "super_admin": True,
        },
        {
            "email": "recruiter@candway.dev",
            "password": "recruiter123",
            "role": "recruiter",
            "name": "Recruiter User",
        },
    ]

    for data in users_data:
        existing = db.query(User).filter(User.email == data["email"]).first()
        if existing:
            if not existing.email_verified:
                existing.email_verified = True
                print(f"Verified existing: {data['email']}")
            print(f"User exists: {data['email']} (id={existing.id})")
            continue

        user = User(
            email=data["email"],
            hashed_password=hash_pw(data["password"]),
            role=data["role"],
            name=data["name"],
            tier="pro",
            subscription_status="active",
            subscription_plan="pro",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        print(f"Created user: {data['email']} (id={user.id}, role={data['role']})")

        member = (
            db.query(CompanyMember)
            .filter_by(company_id=company.id, user_id=user.id)
            .first()
        )
        if not member:
            member = CompanyMember(
                company_id=company.id,
                user_id=user.id,
                role="admin" if data["role"] == "admin" else "member",
                joined_at=utcnow(),
            )
            db.add(member)
            db.flush()
            print("  -> added to company")

        if data["role"] == "admin":
            p = db.query(AdminProfile).filter(AdminProfile.user_id == user.id).first()
            if not p:
                db.add(
                    AdminProfile(
                        user_id=user.id,
                        company_id=company.id,
                        is_super_admin=data["super_admin"],
                        permissions='["all"]',
                    )
                )
                print("  -> created AdminProfile")
        elif data["role"] == "recruiter":
            p = (
                db.query(RecruiterProfile)
                .filter(RecruiterProfile.user_id == user.id)
                .first()
            )
            if not p:
                db.add(
                    RecruiterProfile(
                        user_id=user.id,
                        company_id=company.id,
                        company_name="Candway Demo",
                    )
                )
                print("  -> created RecruiterProfile")

    db.commit()
    db.close()
    print(
        "\nDone!\n  admin@candway.dev / admin123\n  recruiter@candway.dev / recruiter123"
    )


if __name__ == "__main__":
    main()
