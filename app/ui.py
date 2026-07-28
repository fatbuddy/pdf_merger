from __future__ import annotations

import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk
from PIL import Image
from tkinterdnd2 import DND_FILES, TkinterDnD

from app.models import PageItem
from app.pdf_service import (
    PdfError,
    compress_pdf,
    format_file_size,
    load_pages,
    merge_pages,
    render_thumbnail,
    write_merged_pdf,
)

THUMB_W = 140
THUMB_H = 180
CARD_PAD = 8
COLS = 4


class ThumbnailCard(ctk.CTkFrame):
    """One page thumbnail with label and remove button."""

    def __init__(
        self,
        master: tk.Misc,
        item: PageItem,
        index: int,
        on_remove: Callable[[str], None],
        on_drag_start: Callable[[str, int], None],
        on_drag_motion: Callable[[int, int], None],
        on_drag_end: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, width=THUMB_W + 20, height=THUMB_H + 56, **kwargs)
        self.item = item
        self.index = index
        self._on_remove = on_remove
        self._on_drag_start = on_drag_start
        self._on_drag_motion = on_drag_motion
        self._on_drag_end = on_drag_end
        self._ctk_image: ctk.CTkImage | None = None
        self._dragging = False

        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)

        self.img_label = ctk.CTkLabel(
            self, text="…", width=THUMB_W, height=THUMB_H, corner_radius=6
        )
        self.img_label.grid(row=0, column=0, padx=6, pady=(6, 2), sticky="n")

        self.caption = ctk.CTkLabel(
            self,
            text=item.label,
            font=ctk.CTkFont(size=11),
            wraplength=THUMB_W,
            justify="center",
        )
        self.caption.grid(row=1, column=0, padx=4, pady=(0, 2), sticky="ew")

        self.remove_btn = ctk.CTkButton(
            self,
            text="✕",
            width=28,
            height=24,
            fg_color="transparent",
            hover_color=("#e57373", "#c62828"),
            command=lambda: self._on_remove(item.id),
        )
        self.remove_btn.grid(row=2, column=0, pady=(0, 4))

        for widget in (self, self.img_label, self.caption):
            widget.bind("<ButtonPress-1>", self._press)
            widget.bind("<B1-Motion>", self._motion)
            widget.bind("<ButtonRelease-1>", self._release)

    def set_image(self, image: Image.Image) -> None:
        fitted = image.copy()
        fitted.thumbnail((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)
        size = fitted.size
        self._ctk_image = ctk.CTkImage(
            light_image=fitted, dark_image=fitted, size=size
        )
        self.img_label.configure(image=self._ctk_image, text="")

    def set_placeholder(self, message: str = "Preview\nunavailable") -> None:
        self._ctk_image = None
        self.img_label.configure(image=None, text=message)

    def set_highlight(self, active: bool) -> None:
        if active:
            self.configure(border_width=2, border_color=("#1f6aa5", "#3a9ef0"))
        else:
            self.configure(border_width=0)

    def _press(self, _event: tk.Event) -> None:
        self._dragging = True
        self.set_highlight(True)
        self._on_drag_start(self.item.id, self.index)

    def _motion(self, event: tk.Event) -> None:
        if not self._dragging:
            return
        self._on_drag_motion(event.x_root, event.y_root)

    def _release(self, _event: tk.Event) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.set_highlight(False)
        self._on_drag_end()


class MergerApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Merger")
        self.geometry("920x640")
        self.minsize(720, 480)

        self.pages: list[PageItem] = []
        self._cards: dict[str, ThumbnailCard] = {}
        self._thumb_cache: dict[tuple[str, int], Image.Image] = {}
        self._thumb_job = 0
        self._drag_id: str | None = None
        self._drag_from: int | None = None
        self._drop_target: int | None = None
        self._busy = False
        self._file_drop_enabled = False
        self._preview_job = 0
        self._preview_merged: Path | None = None
        self._preview_compressed: Path | None = None
        self._preview_signature: tuple[tuple[str, int], ...] | None = None
        self._merged_size: int | None = None
        self._compressed_size: int | None = None
        self._compress_var = ctk.BooleanVar(value=False)

        self._build_chrome()
        self._hook_file_drop()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_chrome(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(4, weight=1)

        ctk.CTkButton(toolbar, text="Add PDFs", command=self.add_pdfs).grid(
            row=0, column=0, padx=(12, 6), pady=10
        )
        ctk.CTkButton(
            toolbar, text="Clear", command=self.clear_pages, fg_color="gray40"
        ).grid(row=0, column=1, padx=6, pady=10)

        self.preview_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        self.preview_frame.grid(row=0, column=2, padx=(6, 6))

        self.merged_size_label = ctk.CTkLabel(
            self.preview_frame,
            text="Merged: —",
            font=ctk.CTkFont(size=13),
        )
        self.merged_size_label.grid(row=0, column=0, padx=(0, 10))

        self.compress_check = ctk.CTkCheckBox(
            self.preview_frame,
            text="Compress",
            variable=self._compress_var,
            state="disabled",
        )
        self.compress_check.grid(row=0, column=1, padx=(0, 6))

        self.compressed_size_label = ctk.CTkLabel(
            self.preview_frame,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray65"),
        )
        self.compressed_size_label.grid(row=0, column=2)

        self.save_btn = ctk.CTkButton(
            toolbar,
            text="Save Merged PDF",
            command=self.save_merged,
            state="disabled",
        )
        self.save_btn.grid(row=0, column=3, padx=6, pady=10)

        self.status = ctk.CTkLabel(toolbar, text="No pages", anchor="e")
        self.status.grid(row=0, column=4, padx=12, pady=10, sticky="e")

        outer = ctk.CTkFrame(self)
        outer.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(
            outer, label_text="Pages (drag to reorder)"
        )
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        for col in range(COLS):
            self.scroll.grid_columnconfigure(col, weight=1, uniform="thumbs")

        hint = ctk.CTkLabel(
            self,
            text="Tip: Add PDFs with the button or drag files onto this window.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray65"),
        )
        hint.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

    def _hook_file_drop(self) -> None:
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self._register_file_drop_targets(self)
            self._file_drop_enabled = True
        except Exception:
            pass

    def _register_widget_drop(self, widget: tk.Misc) -> None:
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_files_dropped)
        except (tk.TclError, AttributeError):
            pass

    def _register_file_drop_targets(self, widget: tk.Misc) -> None:
        self._register_widget_drop(widget)
        for child in widget.winfo_children():
            self._register_file_drop_targets(child)

    def _on_files_dropped(self, event: tk.Event) -> None:
        try:
            paths = [Path(p) for p in self.tk.splitlist(event.data)]
        except tk.TclError:
            return
        decoded = [path for path in paths if path.suffix.lower() == ".pdf"]
        if decoded:
            self._ingest_paths(decoded)

    def _pages_signature(self) -> tuple[tuple[str, int], ...]:
        return tuple((str(page.path.resolve()), page.page_index) for page in self.pages)

    def _clear_preview_files(self) -> None:
        for path in (self._preview_merged, self._preview_compressed):
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._preview_merged = None
        self._preview_compressed = None
        self._preview_signature = None
        self._merged_size = None
        self._compressed_size = None

    def _update_preview_labels(self) -> None:
        if not self.pages:
            self.merged_size_label.configure(text="Merged: —")
            self.compressed_size_label.configure(text="")
            self.compress_check.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            return

        if self._merged_size is None:
            self.merged_size_label.configure(text="Merged: …")
            self.compressed_size_label.configure(text="")
            self.compress_check.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            return

        self.merged_size_label.configure(
            text=f"Merged: {format_file_size(self._merged_size)}"
        )
        self.compress_check.configure(state="normal")
        self.save_btn.configure(state="normal")

        if self._compressed_size is None:
            self.compressed_size_label.configure(text="(estimating…)")
        elif self._compressed_size < self._merged_size:
            self.compressed_size_label.configure(
                text=f"→ {format_file_size(self._compressed_size)}"
            )
        else:
            self.compressed_size_label.configure(text="(little reduction)")

    def _schedule_preview(self) -> None:
        self._preview_job += 1
        self._clear_preview_files()
        self._update_preview_labels()
        if not self.pages:
            return
        self._start_preview_job()

    def _start_preview_job(self) -> None:
        job = self._preview_job
        pages_snapshot = list(self.pages)
        signature = self._pages_signature()

        def worker() -> None:
            temp_merged: Path | None = None
            temp_compressed: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
                    temp_merged = Path(handle.name)
                merge_pages(pages_snapshot, temp_merged)
                merged_size = temp_merged.stat().st_size

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
                    temp_compressed = Path(handle.name)
                compress_pdf(temp_merged, temp_compressed)
                compressed_size = temp_compressed.stat().st_size
            except Exception:
                self.after(0, lambda: self._preview_failed(job))
                self._cleanup_temp_files(temp_merged, temp_compressed)
                return

            def apply() -> None:
                if job != self._preview_job:
                    self._cleanup_temp_files(temp_merged, temp_compressed)
                    return
                self._preview_merged = temp_merged
                self._preview_compressed = temp_compressed
                self._preview_signature = signature
                self._merged_size = merged_size
                self._compressed_size = compressed_size
                self._update_preview_labels()

            self.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _preview_failed(self, job: int) -> None:
        if job != self._preview_job:
            return
        self._clear_preview_files()
        self.merged_size_label.configure(text="Merged: unavailable")
        self.compressed_size_label.configure(text="")
        self.compress_check.configure(state="disabled")
        self.save_btn.configure(state="disabled")

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        if message is not None:
            self.status.configure(text=message)

    def _update_status(self) -> None:
        if not self._busy:
            n = len(self.pages)
            self.status.configure(
                text=f"{n} page{'s' if n != 1 else ''}" if n else "No pages"
            )

    def add_pdfs(self) -> None:
        if self._busy:
            return
        paths = filedialog.askopenfilenames(
            title="Select PDF files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if paths:
            self._ingest_paths([Path(p) for p in paths])

    def _ingest_paths(self, paths: list[Path]) -> None:
        if self._busy:
            return
        errors: list[str] = []
        new_items: list[PageItem] = []
        for path in paths:
            try:
                new_items.extend(load_pages(path))
            except PdfError as exc:
                errors.append(str(exc))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Could not open '{path.name}': {exc}")

        if new_items:
            self.pages.extend(new_items)
            self._rebuild_grid()
            self._start_thumb_job()
            self._schedule_preview()

        if errors:
            messagebox.showerror(
                "Could not open some PDFs",
                "\n".join(errors[:8])
                + (f"\n… and {len(errors) - 8} more" if len(errors) > 8 else ""),
            )
        self._update_status()

    def clear_pages(self) -> None:
        if self._busy:
            return
        if not self.pages:
            return
        if not messagebox.askyesno("Clear", "Remove all pages from the list?"):
            return
        self.pages.clear()
        self._thumb_cache.clear()
        self._thumb_job += 1
        self._rebuild_grid()
        self._schedule_preview()
        self._update_status()

    def remove_page(self, page_id: str) -> None:
        if self._busy or self._drag_id is not None:
            return
        self.pages = [p for p in self.pages if p.id != page_id]
        self._rebuild_grid()
        self._apply_cached_thumbs()
        self._start_thumb_job()
        self._schedule_preview()
        self._update_status()

    def save_merged(self) -> None:
        if self._busy:
            return
        if not self.pages:
            messagebox.showinfo("Nothing to save", "Add at least one PDF page first.")
            return
        if (
            self._preview_signature != self._pages_signature()
            or self._preview_merged is None
            or self._merged_size is None
        ):
            messagebox.showinfo(
                "Please wait",
                "The merge preview is still updating. Try again in a moment.",
            )
            return

        use_compression = self._compress_var.get()
        if use_compression:
            if self._preview_compressed is None or self._compressed_size is None:
                messagebox.showinfo(
                    "Please wait",
                    "The compression estimate is still updating. Try again in a moment.",
                )
                return
            source = self._preview_compressed
            final_size = self._compressed_size
        else:
            source = self._preview_merged
            final_size = self._merged_size

        out = filedialog.asksaveasfilename(
            title="Save merged PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="merged.pdf",
        )
        if not out:
            return

        out_path = Path(out)
        self._set_busy(True, f"Saving {format_file_size(final_size)}…")
        try:
            write_merged_pdf(source, out_path)
        except PdfError as exc:
            self._save_failed(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._save_failed(str(exc))
        else:
            self._save_ok(out_path, final_size)
        finally:
            self._set_busy(False)
            self._update_status()

    @staticmethod
    def _cleanup_temp_files(*paths: Path | None) -> None:
        for path in paths:
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def _save_ok(self, path: Path, size_bytes: int) -> None:
        messagebox.showinfo(
            "Saved",
            f"Merged PDF saved to:\n{path}\n\nSize: {format_file_size(size_bytes)}",
        )

    def _save_failed(self, message: str) -> None:
        self._set_busy(False)
        self._update_status()
        messagebox.showerror("Save failed", message)

    def _rebuild_grid(self) -> None:
        for child in self.scroll.winfo_children():
            child.destroy()
        self._cards.clear()

        for i, item in enumerate(self.pages):
            row, col = divmod(i, COLS)
            card = ThumbnailCard(
                self.scroll,
                item=item,
                index=i,
                on_remove=self.remove_page,
                on_drag_start=self._drag_start,
                on_drag_motion=self._drag_motion,
                on_drag_end=self._drag_end,
            )
            card.grid(row=row, column=col, padx=CARD_PAD, pady=CARD_PAD, sticky="n")
            self._cards[item.id] = card
            if self._file_drop_enabled:
                self._register_file_drop_targets(card)

        self._apply_cached_thumbs()

    def _cache_key(self, item: PageItem) -> tuple[str, int]:
        return (str(item.path.resolve()), item.page_index)

    def _apply_cached_thumbs(self) -> None:
        for item in self.pages:
            image = self._thumb_cache.get(self._cache_key(item))
            card = self._cards.get(item.id)
            if image is not None and card is not None:
                card.set_image(image)

    def _start_thumb_job(self) -> None:
        self._thumb_job += 1
        job = self._thumb_job
        snapshot = [
            (p.id, p.path, p.page_index, self._cache_key(p)) for p in self.pages
        ]
        missing = [s for s in snapshot if s[3] not in self._thumb_cache]
        if not missing:
            self._set_busy(False)
            self._update_status()
            return

        total = len(missing)
        self._set_busy(True, f"Rendering previews… 0/{total}")

        def worker() -> None:
            for n, (page_id, path, page_index, key) in enumerate(missing, start=1):
                if job != self._thumb_job:
                    return
                try:
                    image = render_thumbnail(path, page_index)
                    err = None
                except Exception as exc:  # noqa: BLE001
                    image = None
                    err = str(exc)

                def apply(
                    pid: str = page_id,
                    cache_key: tuple[str, int] = key,
                    img: Image.Image | None = image,
                    done: int = n,
                    tot: int = total,
                ) -> None:
                    if job != self._thumb_job:
                        return
                    if img is not None:
                        self._thumb_cache[cache_key] = img
                    card = self._cards.get(pid)
                    if card is not None:
                        if img is not None:
                            card.set_image(img)
                        else:
                            card.set_placeholder("Preview\nunavailable")
                    if done < tot:
                        self.status.configure(
                            text=f"Rendering previews… {done}/{tot}"
                        )
                    else:
                        self._set_busy(False)
                        self._update_status()

                self.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _drag_start(self, page_id: str, index: int) -> None:
        self._drag_id = page_id
        self._drag_from = index
        self._drop_target = index

    def _drag_motion(self, x_root: int, y_root: int) -> None:
        if self._drag_id is None or self._drag_from is None:
            return
        target = self._index_at(x_root, y_root)
        if target is None:
            return
        if target == self._drop_target:
            return
        self._drop_target = target
        for i, item in enumerate(self.pages):
            card = self._cards.get(item.id)
            if card is None:
                continue
            card.set_highlight(item.id == self._drag_id or i == target)

    def _drag_end(self) -> None:
        if (
            self._drag_id is not None
            and self._drag_from is not None
            and self._drop_target is not None
            and self._drop_target != self._drag_from
        ):
            item = self.pages.pop(self._drag_from)
            self.pages.insert(self._drop_target, item)
            self._rebuild_grid()
            self._schedule_preview()

        self._drag_id = None
        self._drag_from = None
        self._drop_target = None
        for card in self._cards.values():
            card.set_highlight(False)

    def _index_at(self, x_root: int, y_root: int) -> int | None:
        for i, item in enumerate(self.pages):
            card = self._cards.get(item.id)
            if card is None:
                continue
            try:
                x1 = card.winfo_rootx()
                y1 = card.winfo_rooty()
                x2 = x1 + card.winfo_width()
                y2 = y1 + card.winfo_height()
            except tk.TclError:
                continue
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return i
        return None
