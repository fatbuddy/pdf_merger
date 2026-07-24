from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


@dataclass
class PageItem:
    """One page from a source PDF, tracked for reorder and merge."""

    path: Path
    page_index: int  # 0-based
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def label(self) -> str:
        return f"{self.filename} · p.{self.page_index + 1}"
