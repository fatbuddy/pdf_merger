# PDF Merger

Windows desktop app to merge multiple PDFs into one file, with a thumbnail grid to reorder or remove pages before saving.

## Download (Windows)

Grab the latest release from [Releases](https://github.com/fatbuddy/pdf_merger/releases):

1. Download `PDFMerger-windows.zip`
2. Unzip the archive
3. Run `PDFMerger.exe` (single portable file — no install or extra folders)

No Python install is required. Some antivirus tools may flag unsigned PyInstaller binaries; that is a common false positive for this packaging method.

## Features

- Add multiple PDFs (file picker or drag-and-drop onto the window)
- Preview every page as a thumbnail
- Drag thumbnails to rearrange page order
- Remove individual pages or clear all
- Save the result as a single PDF
- Shows the saved file size; for large outputs (over 10 MB), offers optional compression before saving

## Usage

1. Click **Add PDFs** (or drop `.pdf` files onto the window).
2. Drag page thumbnails to set the order; use **✕** to drop a page.
3. Click **Save Merged PDF** — the app merges your pages and shows the file size before you pick where to save.
4. For large outputs (over 10 MB), choose **Save original** or **Save compressed**.

## Run from source

Requires Python 3.10+ on Windows.

```bat
python -m pip install -r requirements.txt
python main.py
```

## Build a standalone .exe

```bat
build.bat
```

Output: `dist\PDFMerger.exe` (single portable executable)
