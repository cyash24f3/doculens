from io import BytesIO
import pytest
from reportlab.pdfgen import canvas
from pypdf import PdfWriter
from doculens.ingest import extract, chunk_segments, Segment, MAX_BYTES


def test_markdown_preserves_sections():
    raw = (
        b"# Guide\n\nIntroduction.\n## Limits\n\nMaximum upload size is 10 MiB.\n## Security\n\nUse a token."
    )
    segments, pages, warnings = extract(raw, "guide.md")
    assert pages == 1 and warnings == []
    chunks = chunk_segments(segments)
    assert [c["section"] for c in chunks] == ["Guide", "Limits", "Security"]
    assert chunks[1]["text"] == "Maximum upload size is 10 MiB."


def test_pdf_keeps_real_page_numbers_and_empty_warning():
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(50, 750, "Page one evidence: latency is 800 milliseconds.")
    c.showPage()
    c.showPage()
    c.drawString(50, 750, "Page three evidence: retries occur after 1 minute.")
    c.save()
    segments, pages, warnings = extract(buffer.getvalue(), "reference.pdf")
    assert pages == 3
    assert [s.page for s in segments] == [1, 3]
    assert "Page 2" in warnings[0]
    assert chunk_segments(segments)[1]["page"] == 3


@pytest.mark.parametrize(
    "raw,filename",
    [
        (b"", "empty.txt"),
        (b"hello", "bad.exe"),
        (b"\xff\xfe", "bad.txt"),
        (b"\x00hello", "binary.txt"),
        (b"not PDF", "bad.pdf"),
    ],
)
def test_invalid_inputs_rejected(raw, filename):
    with pytest.raises(ValueError):
        extract(raw, filename)


def test_size_limit():
    with pytest.raises(ValueError, match="10 MiB"):
        extract(b"a" * (MAX_BYTES + 1), "large.txt")


def test_scanned_blank_and_encrypted_pdf_rejected():
    w = PdfWriter()
    w.add_blank_page(width=100, height=100)
    out = BytesIO()
    w.write(out)
    with pytest.raises(ValueError, match="No extractable"):
        extract(out.getvalue(), "blank.pdf")
    w.encrypt("secret")
    out = BytesIO()
    w.write(out)
    with pytest.raises(ValueError, match="Encrypted"):
        extract(out.getvalue(), "protected.pdf")


def test_chunk_windows_cover_all_words_and_overlap():
    words = [f"w{i}" for i in range(137)]
    chunks = chunk_segments([Segment(2, "Section", " ".join(words))], 50, 10)
    assert [c["word_start"] for c in chunks] == [0, 40, 80, 120]
    assert chunks[-1]["word_end"] == 137
    assert chunks[0]["text"].split()[-10:] == chunks[1]["text"].split()[:10]
    assert all(c["page"] == 2 for c in chunks)


def test_fixed_strategy_does_not_merge_pdf_pages():
    chunks = chunk_segments(
        [
            Segment(1, "A", "First section."),
            Segment(1, "B", "Second section."),
            Segment(2, "C", "Other page."),
        ],
        strategy="fixed",
    )
    assert len(chunks) == 2
    assert chunks[0]["text"] == "First section. Second section."
    assert chunks[1]["page"] == 2
