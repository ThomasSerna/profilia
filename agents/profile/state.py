from typing import TypedDict

from .schemas import ProfileData


class ProfileState(TypedDict):
    pdf_path: str
    raw_text: str
    profile: ProfileData | None