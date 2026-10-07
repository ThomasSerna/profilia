from pypdf import PdfReader

class EmptyPDFTextError(ValueError):
    pass


def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():
        raise EmptyPDFTextError(
            "No fue posible extraer texto del PDF. "
            "Usa un PDF con texto seleccionable."
        )

    return text