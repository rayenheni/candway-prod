
import smtplib
import socket
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

Base = declarative_base()

class SystemConfig(Base):
    __tablename__ = "system_config"
    key = Column(String(100), primary_key=True)
    value = Column(Text)

def verify_smtp():
    # Load .env from backend directory
    backend_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env')
    load_dotenv(backend_env)
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not found in .env")
        return

    try:
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        db = Session()
        
        # Pull SMTP Config
        username = db.query(SystemConfig).filter(SystemConfig.key == "smtp_username").first()
        password = db.query(SystemConfig).filter(SystemConfig.key == "smtp_password").first()
        host = db.query(SystemConfig).filter(SystemConfig.key == "smtp_host").first()
        port = db.query(SystemConfig).filter(SystemConfig.key == "smtp_port").first()
        
        config = {
            "username": username.value if username else None,
            "password": password.value if password else None,
            "server": host.value if host else "smtp.gmail.com",
            "port": int(port.value) if port else 587
        }
        
        db.close()
        
        print(f"SMTP Configuration found:")
        print(f"Host: {config['server']}")
        print(f"Port: {config['port']}")
        print(f"User: {config['username']}")
        
        if not config["username"] or not config["password"]:
            print("WARNING: SMTP Username or Password missing in database. Emails will be MOCKED.")
            return

        print("\nTesting connection...")
        try:
            server = smtplib.SMTP(config["server"], config["port"], timeout=10)
            server.set_debuglevel(1)
            server.starttls()
            server.login(config["username"], config["password"])
            print("SUCCESS: SMTP Login successful!")
            server.quit()
        except smtplib.SMTPAuthenticationError:
            print("ERROR: Authentication failed. Check username/password/App Password.")
        except socket.timeout:
            print("ERROR: Connection timed out. Check firewall or server address.")
        except Exception as e:
            print(f"ERROR: SMTP Connection failed: {e}")

    except Exception as e:
        print(f"ERROR: Database connection failed during SMTP verification: {e}")

if __name__ == "__main__":
    verify_smtp()
