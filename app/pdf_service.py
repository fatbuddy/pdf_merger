from __future__ import annotations

import shutil
from pathlib import Path

import fitz
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError

from app.models import PageItem

THUMB_MAX_WIDTH = 140
THUMB_MAX_HEIGHT = 180
LARGE_PDF_THRESHOLD_BYTES = 10 * 1024 * 1024
COMPRESS_JPEG_QUALITY = 75


class PdfError(Exception):
    """User-facing PDF load/merge error."""


def format_file_size(size_bytes: int) -> str:
    """Return a short human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def load_pages(path: Path) -> list[PageItem]:
    """Return one PageItem per page in the PDF, or raise PdfError."""
    path = Path(path)
    if not path.is_file():
        raise PdfError(f"File not found: {path}")

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 — surface as PdfError
        raise PdfError(f"Could not open '{path.name}': {exc}") from exc

    if reader.is_encrypted:
        try:
            # Empty password unlocks some "owner-password only" files.
            if reader.decrypt("") == 0:
                raise PdfError(
                    f"'{path.name}' is password-protected and cannot be opened."
                )
        except FileNotDecryptedError as exc:
            raise PdfError(
                f"'{path.name}' is password-protected and cannot be opened."
            ) from exc

    try:
        count = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not read pages from '{path.name}': {exc}") from exc

    if count == 0:
        raise PdfError(f"'{path.name}' has no pages.")

    return [PageItem(path=path, page_index=i) for i in range(count)]


def render_thumbnail(path: Path, page_index: int) -> Image.Image:
    """Render a single page to a PIL RGB image suitable for thumbnails."""
    path = Path(path)
    try:
        doc = fitz.open(str(path))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not preview '{path.name}': {exc}") from exc

    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise PdfError(
                f"Page {page_index + 1} out of range in '{path.name}'."
            )
        page = doc.load_page(page_index)
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            scale = 1.0
        else:
            scale = min(
                THUMB_MAX_WIDTH / rect.width,
                THUMB_MAX_HEIGHT / rect.height,
                2.0,
            )
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return image
    finally:
        doc.close()


def merge_pages(pages: list[PageItem], out_path: Path) -> None:
    """Write pages in order to out_path."""
    if not pages:
        raise PdfError("No pages to merge.")

    out_path = Path(out_path)
    writer = PdfWriter()
    readers: dict[str, PdfReader] = {}

    try:
        for item in pages:
            key = str(item.path.resolve())
            if key not in readers:
                try:
                    reader = PdfReader(str(item.path))
                except Exception as exc:  # noqa: BLE001
                    raise PdfError(
                        f"Could not open '{item.path.name}' while merging: {exc}"
                    ) from exc
                if reader.is_encrypted:
                    try:
                        if reader.decrypt("") == 0:
                            raise PdfError(
                                f"'{item.path.name}' is password-protected."
                            )
                    except FileNotDecryptedError as exc:
                        raise PdfError(
                            f"'{item.path.name}' is password-protected."
                        ) from exc
                readers[key] = reader

            reader = readers[key]
            if item.page_index < 0 or item.page_index >= len(reader.pages):
                raise PdfError(
                    f"Invalid page {item.page_index + 1} in '{item.path.name}'."
                )
            writer.add_page(reader.pages[item.page_index])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as fh:
            writer.write(fh)
    finally:
        for reader in readers.values():
            if hasattr(reader, "close"):
                reader.close()
        writer.close()


def compress_pdf(
    src: Path,
    dst: Path,
    *,
    jpeg_quality: int = COMPRESS_JPEG_QUALITY,
) -> None:
    """Write a smaller copy of src to dst using PyMuPDF."""
    src = Path(src)
    dst = Path(dst)
    try:
        doc = fitz.open(str(src))
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not open merged PDF for compression: {exc}") from exc

    try:
        if hasattr(doc, "rewrite_images"):
            doc.rewrite_images(quality=jpeg_quality)
        dst.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(dst), garbage=4, deflate=True, clean=True)
    except Exception as exc:  # noqa: BLE001
        raise PdfError(f"Could not compress PDF: {exc}") from exc
    finally:
        doc.close()


def write_merged_pdf(src: Path, dst: Path) -> int:
    """Copy merged PDF bytes to dst and return the final file size."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst.stat().st_size
