import os
import sys
from datetime import datetime

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, EmailTemplate
from sqlalchemy.orm import Session

def seed_defaults():
    db = SessionLocal()
    try:
        print("🌱 Seeding default content...")
        
        # 1. Default Email Templates
        templates = [
            {
                "name": "Interview Invitation",
                "subject": "Interview Invitation: {{JOB_TITLE}} at {{COMPANY_NAME}}",
                "body_html": """
                <div style="font-family: sans-serif; color: #1e293b; max-width: 600px;">
                    <h2 style="color: #4f46e5;">Great News!</h2>
                    <p>Hello,</p>
                    <p>We've reviewed your application for the <strong>{{JOB_TITLE}}</strong> position and we're impressed by your profile.</p>
                    <p>We'd like to invite you to our AI-powered screening interview. This will help us learn more about your technical skills at your own convenience.</p>
                    <div style="margin: 30px 0;">
                        {{INTERVIEW_LINK}}
                    </div>
                    <p>Best regards,<br>The Recruitment Team</p>
                </div>
                """,
                "is_default": True
            },
            {
                "name": "Application Receipt",
                "subject": "We've received your application for {{JOB_TITLE}}",
                "body_html": """
                <p>Hello,</p>
                <p>Thank you for applying to {{COMPANY_NAME}}. Your application for <strong>{{JOB_TITLE}}</strong> is now under review.</p>
                <p>Our AI agents are currently analyzing your profile relative to the role requirements. We'll be in touch soon!</p>
                <p>Best,<br>Hiring Team</p>
                """,
                "is_default": True
            }
        ]

        for t in templates:
            existing = db.query(EmailTemplate).filter(EmailTemplate.name == t["name"]).first()
            if not existing:
                db.add(EmailTemplate(**t))
                print(f"✅ Added template: {t['name']}")
            else:
                print(f"⏩ Template '{t['name']}' already exists.")

        db.commit()
        print("🎉 Seeding complete!")
        
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_defaults()
