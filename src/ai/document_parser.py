from pathlib import Path


def parse_document(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from a document file.

    Supported formats: .txt, .docx, .pdf
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        return file_bytes.decode("utf-8", errors="replace")

    if suffix == ".docx":
        return _parse_docx(file_bytes)

    if suffix == ".pdf":
        return _parse_pdf(file_bytes)

    raise ValueError(f"Unsupported file format: {suffix}")


def _parse_docx(file_bytes: bytes) -> str:
    import io

    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_pdf(file_bytes: bytes) -> str:
    import fitz  # pymupdf

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)
