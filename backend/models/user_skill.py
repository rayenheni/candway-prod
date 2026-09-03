from sqlalchemy import Boolean, Column, Integer, String

from backend.models.base import Base


class UserSkill(Base):
    __tablename__ = "user_skills"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    category = Column(String(100), nullable=False)
    skill_name = Column(String(255), nullable=False)
    level = Column(Integer, default=0)
    trend = Column(String(10), default="+0")
    verified = Column(Boolean, default=False)
