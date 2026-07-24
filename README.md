# PDF Merger

Windows desktop app to merge multiple PDFs into one file, with a thumbnail grid to reorder or remove pages before saving.

## Download (Windows)

Grab the latest release from [Releases](https://github.com/fatbuddy/pdf_merger/releases):

1. Download `PDFMerger-windows.zip`
2. Unzip the folder
3. Run `PDFMerger.exe`

No Python install is required. Some antivirus tools may flag unsigned PyInstaller binaries; that is a common false positive for this packaging method.

## Features

- Add multiple PDFs (file picker or drag-and-drop onto the window)
- Preview every page as a thumbnail
- Drag thumbnails to rearrange page order
- Remove individual pages or clear all
- Save the result as a single PDF

## Usage

1. Click **Add PDFs** (or drop `.pdf` files onto the window).
2. Drag page thumbnails to set the order; use **✕** to drop a page.
3. Click **Save Merged PDF** and choose the output path.

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

Output: `dist\PDFMerger\PDFMerger.exe`
