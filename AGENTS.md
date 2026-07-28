# AGENTS.md

## Cursor Cloud specific instructions

PDF Merger is a single Python desktop GUI app (`customtkinter`/Tkinter) that merges PDFs
with a thumbnail grid to reorder/remove pages. There is no backend, database, or web
service. Standard setup/run/build commands live in `README.md` and `build.bat`; this
section only captures non-obvious caveats for running it in the cloud VM.

- Dependencies are installed into a virtualenv at `.venv` (the update script maintains it).
  Run tooling via `.venv/bin/python`.
- The GUI requires a display (the cloud VM provides `DISPLAY=:1`) and the system Tk
  bindings (`python3-tk`, baked into the environment snapshot). Launch the app with
  `PYTHONPATH=. .venv/bin/python main.py`.
- `PYTHONPATH=.` (repo root) is required when running `main.py` and `scripts/*.py`, because
  they import the top-level `app` package; running `python scripts/smoke_test.py` without it
  raises `ModuleNotFoundError: No module named 'app'`.
- Headless core-logic check (load/render/merge, no GUI): `PYTHONPATH=. .venv/bin/python scripts/smoke_test.py`.
  It writes sample PDFs under `samples/` (git-ignored) and asserts merge/reorder output.
- Drag-and-drop uses `windnd`, which is Windows-only; on Linux it silently no-ops (the code
  swallows the import error). Use the "Add PDFs" button to add files instead of dragging.
- There is no lint config (flake8/ruff/mypy) and no `pytest` suite in the repo; the only
  automated check is `scripts/smoke_test.py`.
- `build.bat` (PyInstaller) produces a Windows `.exe` and is not needed for development on Linux.
