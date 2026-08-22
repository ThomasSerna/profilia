from pypdf import PdfReader

# Extraer texto de un pdf
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text

if __name__ == "__main__":

    test_name = "cv_prueba.pdf"
    with open(test_name, "rb") as file:
        text = extract_text_from_pdf(file)

    print(text)