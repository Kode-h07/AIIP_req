from io import BytesIO
from pypdf import PdfReader


def extract_pdf_text_first_pages(pdf_bytes: bytes, max_pages: int = 2) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        out = []
        for i, page in enumerate(reader.pages[:max_pages]):
            txt = page.extract_text() or ""
            out.append(txt)
        text = "\n".join(out)
        # normalize
        return " ".join(text.split())[:4000]
    except Exception:
        return ""
