"""Smoke test: create samples, reorder, merge, verify."""

from pathlib import Path

import fitz
from pypdf import PdfReader

from app.pdf_service import (
    compress_pdf,
    format_file_size,
    load_pages,
    merge_pages,
    render_thumbnail,
)

samples = Path("samples")
samples.mkdir(exist_ok=True)
out = Path("samples/merged_test.pdf")

for name, pages in [("a.pdf", ["A1", "A2"]), ("b.pdf", ["B1", "B2", "B3"])]:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page(width=300, height=400)
        page.insert_text((50, 80), text, fontsize=36)
    doc.save(samples / name)
    doc.close()

pages_a = load_pages(samples / "a.pdf")
pages_b = load_pages(samples / "b.pdf")
assert len(pages_a) == 2 and len(pages_b) == 3

ordered = [pages_b[1], pages_a[0], pages_b[0], pages_a[1]]
img = render_thumbnail(ordered[0].path, ordered[0].page_index)
assert img.size[0] > 0 and img.size[1] > 0

merge_pages(ordered, out)
assert out.stat().st_size > 0
assert format_file_size(out.stat().st_size).endswith(("B", "KB", "MB"))

compressed = Path("samples/merged_test_compressed.pdf")
compress_pdf(out, compressed)
assert compressed.stat().st_size > 0
reader = PdfReader(str(out))
assert len(reader.pages) == 4

doc = fitz.open(str(out))
texts = [doc.load_page(i).get_text().strip() for i in range(doc.page_count)]
doc.close()
assert texts == ["B2", "A1", "B1", "A2"], texts
print("merge/reorder/thumbnail OK:", texts)
print("output:", out.resolve())
