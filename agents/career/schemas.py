from pydantic import BaseModel, Field

class RoleProfile(BaseModel):
    name: str

    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_areas: list[str] = Field(default_factory=list)

