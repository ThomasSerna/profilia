from typing import TypedDict

from .schemas import ProfileData

# Respuesta final del agente
class ProfileState(TypedDict):
    pdf_path: str
    raw_text: str
    profile: ProfileData | None