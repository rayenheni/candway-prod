
import sqlalchemy
from sqlalchemy import create_engine
from backend.database import init_db, DATABASE_URL, Base

def reset_database():
    # Parse DB Name from URL
    db_name = DATABASE_URL.split("/")[-1]
    server_url = DATABASE_URL.rsplit("/", 1)[0]
    
    print(f"Connecting to: {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    
    print("Dropping all tables (Schema Update)...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Tables dropped.")
    except Exception as e:
        print(f"Drop failed (might be empty): {e}")

    print("Initializing Tables (with Categories)...")
    init_db()
    print("Tables created successfully.")
    
    # Optional: Seed some categories
    from sqlalchemy.orm import sessionmaker
    from backend.database import Category
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    if session.query(Category).count() == 0:
        print("Seeding default categories...")
        # Jobs
        eng = Category(name="Engineering", type="job", slug="engineering")
        session.add(eng)
        session.commit()
        
        session.add(Category(name="Backend", type="job", parent_id=eng.id, slug="backend"))
        session.add(Category(name="Frontend", type="job", parent_id=eng.id, slug="frontend"))
        
        # Courses
        tech = Category(name="Technology", type="course", slug="technology")
        session.add(tech)
        session.commit()
        
        session.add(Category(name="Python", type="course", parent_id=tech.id, slug="python"))
        session.add(Category(name="React", type="course", parent_id=tech.id, slug="react"))
        
        session.commit()
        print("Seeded.")
    
    session.close()

if __name__ == "__main__":
    reset_database()
