"""Text extraction and source-aware chunking. No OCR or silent empty-page deletion."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 100
MAX_CHARS = 500_000
MAX_CHUNKS = 1000


@dataclass
class Segment:
    page: int
    section: str
    text: str


def extract(raw: bytes, filename: str):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Provide a nonempty file no larger than 10 MiB.")
    suffix = Path(filename).suffix.lower()
    warnings = []
    segments = []
    if suffix == ".pdf":
        try:
            reader = PdfReader(BytesIO(raw), strict=False)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported. Upload an unencrypted copy.")
            if len(reader.pages) > MAX_PAGES:
                raise ValueError("PDFs may contain at most 100 pages.")
            for i, page in enumerate(reader.pages, 1):
                content = page.extract_text() or ""
                if content.strip():
                    segments.append(Segment(i, f"Page {i}", content))
                else:
                    warnings.append(f"Page {i} has no extractable text; OCR is not included.")
                if sum(len(s.text) for s in segments) > MAX_CHARS:
                    raise ValueError("Extracted text exceeds 500,000 characters.")
            page_count = len(reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not read PDF. Upload a valid text-based PDF.") from exc
    elif suffix in {".txt", ".md"}:
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text and Markdown files must use UTF-8 encoding.") from exc
        if "\x00" in content:
            raise ValueError("Binary content is not supported as text.")
        section, lines = "Document", []
        for line in content.splitlines():
            match = re.match(r"^#{1,6}\s+(.+)$", line)
            if suffix == ".md" and match:
                if "\n".join(lines).strip():
                    segments.append(Segment(1, section, "\n".join(lines)))
                section, lines = match.group(1).strip(), []
            else:
                lines.append(line)
        if "\n".join(lines).strip():
            segments.append(Segment(1, section, "\n".join(lines)))
        page_count = 1
    else:
        raise ValueError("Supported formats: .pdf, .md, .txt.")
    if not segments or not any(s.text.strip() for s in segments):
        raise ValueError("No extractable text found. Scanned PDFs need OCR before upload.")
    if sum(len(s.text) for s in segments) > MAX_CHARS:
        raise ValueError("Extracted text exceeds 500,000 characters.")
    return segments, page_count, warnings


def chunk_segments(segments, chunk_size=150, overlap=25, strategy="section"):
    if chunk_size < 40 or not 0 <= overlap < chunk_size:
        raise ValueError("Chunk size must be >=40 words and overlap smaller than chunk size.")
    if strategy not in {"section", "fixed"}:
        raise ValueError("Unknown chunking strategy")
    if strategy == "fixed":
        # Preserve page attribution even in fixed-window comparison mode.
        by_page = {}
        for segment in segments:
            by_page.setdefault(segment.page, []).append(segment.text)
        segments = [Segment(p, "Fixed window", "\n".join(parts)) for p, parts in by_page.items()]
    chunks = []
    for segment in segments:
        words = segment.text.split()
        for start in range(0, len(words), chunk_size - overlap):
            end = min(start + chunk_size, len(words))
            if start >= end:
                break
            chunks.append(
                {
                    "ordinal": len(chunks),
                    "page": segment.page,
                    "section": segment.section,
                    "text": " ".join(words[start:end]),
                    "word_start": start,
                    "word_end": end,
                }
            )
            if end == len(words):
                break
    if len(chunks) > MAX_CHUNKS:
        raise ValueError("Document produces too many chunks (maximum 1,000).")
    return chunks
