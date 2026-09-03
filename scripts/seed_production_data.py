
import os
import sys
from datetime import datetime, timedelta

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Category, BlogPost, Opportunity, User, Job, Course, Announcement, Section, Lesson
from sqlalchemy.orm import Session

def seed_production_data():
    db = SessionLocal()
    try:
        print("Seeding production-grade data...")

        # 1. Categories
        print("[*] Seeding Categories...")
        course_categories = ["Artificial Intelligence", "Web Development", "UI/UX Design", "Digital Marketing", "Soft Skills"]
        job_categories = ["Engineering", "Product Management", "Data Science", "Sales & Marketing", "Human Resources"]
        
        cat_map = {}
        for name in course_categories:
            slug = name.lower().replace(" ", "-")
            cat = db.query(Category).filter(Category.name == name, Category.type == "course").first()
            if not cat:
                cat = Category(name=name, type="course", slug=slug)
                db.add(cat)
                db.flush()
            cat_map[f"course_{name}"] = cat.id

        for name in job_categories:
            slug = name.lower().replace(" ", "-")
            cat = db.query(Category).filter(Category.name == name, Category.type == "job").first()
            if not cat:
                cat = Category(name=name, type="job", slug=slug)
                db.add(cat)
                db.flush()
            cat_map[f"job_{name}"] = cat.id

        # 2. Sample Admin/Mentor
        print("[*] Ensuring Mentor/Admin exists...")
        mentor = db.query(User).filter(User.role == "mentor").first()
        if not mentor:
            mentor = User(
                email="mentor@candway.com",
                name="Prof. Ahmed Ben Salah",
                role="mentor",
                headline="Expert AI Researcher & Educator",
                bio="Passionate about bridging the gap between academia and industry in North Africa.",
                tier="pro"
            )
            db.add(mentor)
            db.flush()

        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            admin = User(
                email="admin@candway.com",
                name="Candway Admin",
                role="admin",
                tier="pro"
            )
            db.add(admin)
            db.flush()

        # 3. Blog Posts
        print("[*] Seeding Blog Posts...")
        blogs = [
            {
                "title": "The Future of AI Recruitment in Tunisia",
                "slug": "future-ai-recruitment-tunisia",
                "content": "<p>Artificial intelligence is transforming how companies in Tunisia find and hire talent. By using automated screening and skill assessment, platforms like Candway are reducing bias and improving hiring efficiency.</p><p>We are seeing a shift towards evidence-based hiring where skills matter more than credentials.</p>",
                "author_id": admin.id,
                "tags": "AI,Recruitment,Tunisia",
                "image_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&q=80&w=800"
            },
            {
                "title": "5 Tips to Ace Your Next AI Interview",
                "slug": "5-tips-ace-ai-interview",
                "content": "<p>AI interviews can be intimidating. Here are 5 tips to help you succeed: 1. Speak clearly and concisely. 2. Focus on specific achievements. 3. Use the STAR method. 4. Maintain good eye contact with the camera. 5. Practice with simulated environments.</p>",
                "author_id": mentor.id,
                "tags": "Career,Interview,Success",
                "image_url": "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&q=80&w=800"
            },
            {
                "title": "Remote Work Trends for MENA Startups",
                "slug": "remote-work-trends-mena",
                "content": "<p>Startups in the MENA region are increasingly adopting remote-first or hybrid models. This allows them to tap into a wider talent pool across different countries while reducing overhead costs.</p>",
                "author_id": admin.id,
                "tags": "Remote,Startup,Trends",
                "image_url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&q=80&w=800"
            }
        ]
        for b in blogs:
            if not db.query(BlogPost).filter(BlogPost.slug == b["slug"]).first():
                db.add(BlogPost(**b))

        # 4. Opportunities
        print("[*] Seeding Opportunities...")
        opps = [
            {
                "title": "DeepMind Scholarship 2026",
                "type": "scholarship",
                "description": "Full funding for Masters or PhD students in AI and Machine Learning from African universities.",
                "link": "https://deepmind.google/scholarships",
                "image_url": "https://images.unsplash.com/photo-1523050335392-9bef867a4975?auto=format&fit=crop&q=80&w=800",
                "is_active": True
            },
            {
                "title": "Microsoft MENA Hackathon",
                "type": "event",
                "description": "Join developers across MENA to build innovative solutions for sustainability using Azure AI.",
                "link": "https://microsoft.com/mena-hackathon",
                "image_url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?auto=format&fit=crop&q=80&w=800",
                "is_active": True
            },
            {
                "title": "Startup Tunisia Founders Grant",
                "type": "grant",
                "description": "Financial support for early-stage startups in the Fintech and EdTech sectors in Tunisia.",
                "link": "https://startuptunisia.tn/grants",
                "image_url": "https://images.unsplash.com/photo-1559136555-9303baea8ebd?auto=format&fit=crop&q=80&w=800",
                "is_active": True
            }
        ]
        for o in opps:
            if not db.query(Opportunity).filter(Opportunity.title == o["title"]).first():
                db.add(Opportunity(**o))

        # 5. Announcements
        print("[*] Seeding Announcements...")
        if not db.query(Announcement).first():
            announcement = Announcement(
                title="Platform Maintenance: April 30th",
                message="We will be performing scheduled maintenance on April 30th at 2:00 AM UTC. Expect brief downtime.",
                type="info",
                target_role="all",
                is_active=True,
                created_by=admin.id
            )
            db.add(announcement)

        # 6. Link existing Jobs and Courses to Categories
        print("[*] Updating existing listings...")
        jobs = db.query(Job).filter(Job.category_id == None).all()
        for j in jobs:
            j.category_id = cat_map.get("job_Engineering")
        
        courses = db.query(Course).filter(Course.category_id == None).all()
        for c in courses:
            c.category_id = cat_map.get("course_Artificial Intelligence")
            if not c.mentor_id:
                c.mentor_id = mentor.id
            
            # Add a default section and lesson if none exist
            if not db.query(Section).filter(Section.course_id == c.id).first():
                section = Section(
                    course_id=c.id,
                    title="Introduction & Fundamentals",
                    order=1
                )
                db.add(section)
                db.flush()
                
                lesson = Lesson(
                    section_id=section.id,
                    title=f"Welcome to {c.title}",
                    content_type="video",
                    duration=300, # 5 min
                    order=1
                )
                db.add(lesson)

        db.commit()
        print("Production data seeding complete!")
        
    except Exception as e:
        print(f"Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_production_data()
