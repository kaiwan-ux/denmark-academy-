from dataclasses import dataclass

from denmark_academy.ingestion.pdf import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    section_title: str | None
    token_count: int


def chunk_pages(
    pages: list[ExtractedPage],
    target_tokens: int = 750,
    overlap_tokens: int = 100,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    current_tokens: list[str] = []
    page_start: int | None = None
    section_title: str | None = None

    for page in pages:
        tokens = page.text.split()
        if not tokens:
            continue
        if page_start is None:
            page_start = page.page_number
            section_title = _guess_section_title(page.text)
        current_tokens.extend(tokens)
        if len(current_tokens) >= target_tokens:
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    text=" ".join(current_tokens),
                    page_start=page_start,
                    page_end=page.page_number,
                    section_title=section_title,
                    token_count=len(current_tokens),
                )
            )
            current_tokens = current_tokens[-overlap_tokens:] if overlap_tokens else []
            page_start = page.page_number if current_tokens else None
            section_title = _guess_section_title(page.text)

    if current_tokens and page_start is not None:
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                text=" ".join(current_tokens),
                page_start=page_start,
                page_end=pages[-1].page_number,
                section_title=section_title,
                token_count=len(current_tokens),
            )
        )
    return chunks


def _guess_section_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if 6 <= len(stripped) <= 90 and stripped.upper() == stripped:
            return stripped
    return None

