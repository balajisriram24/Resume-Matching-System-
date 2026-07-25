import os
import pdfplumber
from docx import Document


def extract_text(file_path: str, file_type: str) -> str:
    lower_type = (file_type or "").lower()
    if lower_type == "pdf":
        return extract_pdf_text(file_path)
    if lower_type == "docx":
        return extract_docx_text(file_path)
    raise ValueError("Unsupported file type")


def extract_pdf_text(file_path: str) -> str:
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text_parts.append(text)
    return "\n".join(text_parts)


def extract_docx_text(file_path: str) -> str:
    document = Document(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)
