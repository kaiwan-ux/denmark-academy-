from dataclasses import dataclass
from pathlib import Path

import pdfplumber


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    extraction_method: str = "text"
    extraction_confidence: float = 0.99


def extract_pdf_pages(path: Path) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ExtractedPage(page_number=index, text=_normalize_text(text)))
    return pages


def _normalize_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.replace("\x00", "").splitlines() if line.strip())

