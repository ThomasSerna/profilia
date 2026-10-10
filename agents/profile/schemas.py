from pydantic import BaseModel, Field, ValidationError


PROFESSIONAL_FIELDS = ("education", "experience", "skills", "languages")


class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProfileData(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None

    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


def has_professional_information(data: ProfileData | dict) -> bool:
    try:
        profile = ProfileData.model_validate(data)
    except ValidationError:
        return False
    if any(value.strip() for value in profile.skills + profile.languages):
        return True
    for item in profile.experience:
        if any(value and value.strip() for value in (item.company, item.role, item.description)):
            return True
        if any(value.strip() for value in item.technologies):
            return True
    return any(any(value and value.strip() for value in (item.institution, item.degree, item.field))
               for item in profile.education)
