from .pdf_reader import extract_text_from_pdf
from .state import ProfileState


def extract_pdf_node(state: ProfileState):
    pdf_path = state["pdf_path"]

    with open(pdf_path, "rb") as pdf_file:
        text = extract_text_from_pdf(pdf_file)

    return {
        "raw_text": text
    }