from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LevelDescriptor(BaseModel):
    score_threshold: int = Field(..., ge=0, le=100)
    description: str
    keywords: List[str] = Field(default_factory=list)
    sort_order: int = 0


class SkillDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    keywords: List[str] = Field(default_factory=list)
    levels: Dict[str, List[LevelDescriptor]] = Field(
        default_factory=lambda: {"junior": [], "mid": [], "senior": []}
    )
    weight: float = 1.0
    is_required: bool = False


class SubcategoryDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    weight: float = 1.0
    skills: List[SkillDefinition] = Field(default_factory=list)


class CategoryDefinition(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    weight: float = 1.0
    evaluation_criteria: List[str] = Field(default_factory=list)
    interview_methods: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    subcategories: List[SubcategoryDefinition] = Field(default_factory=list)


class JobRubric(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: int
    version: int = 1
    seniority: str = "mid"
    categories: List[CategoryDefinition] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    is_current: bool = True

    def build_lookup(self) -> Dict[str, SkillDefinition]:
        lookup = {}
        for cat in self.categories:
            for sub in cat.subcategories:
                for skill in sub.skills:
                    lookup[skill.name.lower()] = skill
        return lookup

    def get_category(self, name: str) -> Optional[CategoryDefinition]:
        for cat in self.categories:
            if cat.name.lower() == name.lower():
                return cat
        return None

    def get_subcategory(self, name: str) -> Optional[SubcategoryDefinition]:
        for cat in self.categories:
            for sub in cat.subcategories:
                if sub.name.lower() == name.lower():
                    return sub
        return None

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        return self.build_lookup().get(name.lower())
