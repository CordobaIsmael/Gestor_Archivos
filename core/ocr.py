import fitz
from pathlib import Path

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extracts raw text from a PDF file. Since the PDFs have embedded text,
    this uses PyMuPDF to extract text from all pages.
    """
    text_content = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text_content.append(page.get_text())
    except Exception as e:
        print(f"Error extracting text from PDF {pdf_path}: {e}")
        
    return "\n".join(text_content)
