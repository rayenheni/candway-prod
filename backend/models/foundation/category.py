"""SQLAlchemy model definitions."""

from sqlalchemy import Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from backend.models.base import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index("idx_categories_parent", "parent_id"),
        Index("idx_categories_slug", "slug"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    type = Column(String(50))  # 'job' or 'course'
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    slug = Column(String(255))  # Simple slug for URLs

    parent = relationship("Category", remote_side=[id], backref="subcategories")
