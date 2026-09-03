
from backend.database import engine, Base
# Import all models to ensure they are registered
from backend.database import User, CareerRoadmap

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Tables created.")
