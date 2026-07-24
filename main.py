"""PDF Merger — Windows desktop entry point."""

from __future__ import annotations

import customtkinter as ctk

from app.ui import MergerApp


def main() -> None:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MergerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
