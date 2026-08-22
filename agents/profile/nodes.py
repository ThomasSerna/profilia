from .pdf_reader import extract_text_from_pdf
from .state import ProfileState
from .schemas import ProfileData
from .llm import llm


def extract_pdf_node(state: ProfileState):
    pdf_path = state["pdf_path"]

    with open(pdf_path, "rb") as pdf_file:
        text = extract_text_from_pdf(pdf_file)

    return {
        "raw_text": text
    }


def extract_profile_node(state: ProfileState):
    structured_llm = llm.with_structured_output(ProfileData)

    prompt = f"""
    Extrae la informacion profesional de la siguiente hoja de vida.

    Reglas:
    - No inventes informacion.
    - Si un dato no aparece, dejalo vacio o como null.
    - Extrae solamente información explicitamente presente en el CV.
    - Conserva experiencia, educacion y habilidades relevantes.

    HOJA DE VIDA:
    {state["raw_text"]}
    """

    profile = structured_llm.invoke(prompt)

    return {
        "profile": profile
    }