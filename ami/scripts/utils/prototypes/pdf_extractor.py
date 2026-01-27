#!/usr/bin/env python3
"""
PDF Extractor Utility
Extracts text and images from a PDF file.

Usage:
    python pdf_extractor.py input.pdf output_directory [--start_page N] [--end_page N]

Requirements:
    pymupdf (fitz)
"""

import argparse
from pathlib import Path

import fitz


def extract_pdf_content(
    pdf_path: str, output_dir: str, start_page: int = 1, end_page: int | None = None
) -> None:
    """
    Extracts text and images from a PDF into the specified directory.

    Args:
        pdf_path: Path to the input PDF.
        output_dir: Directory to save extracted content.
        start_page: First page to process (1-based index).
        end_page: Last page to process (1-based index). If None, process until the end.
    """
    path_pdf = Path(pdf_path)
    path_output = Path(output_dir)
    images_dir = path_output / "images"

    if not path_pdf.exists():
        print(f"Error: Input file '{path_pdf}' not found.")
        return

    # Create directories
    path_output.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"Opening {path_pdf}...")
    try:
        doc = fitz.open(path_pdf)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return

    total_pages = doc.page_count
    print(f"Document has {total_pages} pages.")

    # Validate page range
    start_idx = max(0, start_page - 1)
    end_idx = total_pages if end_page is None else min(total_pages, end_page)

    if start_idx >= total_pages:
        print(f"Start page {start_page} is beyond the document end.")
        return

    print(f"Processing pages {start_idx + 1} to {end_idx}...")

    for i in range(start_idx, end_idx):
        page_num = i + 1
        page = doc[i]

        # 1. Extract Text
        text_filename = path_output / f"page_{page_num}.txt"
        text = page.get_text("text", sort=True)

        with open(text_filename, "w", encoding="utf-8") as f:
            f.write(text)

        # 2. Extract Images
        image_list = page.get_images(full=True)

        if image_list:
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    image_filename = (
                        images_dir / f"page_{page_num}_img_{img_index + 1}.{image_ext}"
                    )

                    with open(image_filename, "wb") as f:
                        f.write(image_bytes)
                except Exception as e:
                    img_num = img_index + 1
                    print(f"  [Warning] Image {img_num} on page {page_num}: {e}")

    print(f"Extraction complete. Results saved in '{path_output}'.")
    doc.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text and images from a PDF.")
    parser.add_argument("pdf_path", help="Path to the source PDF file")
    parser.add_argument("output_dir", help="Directory to save extracted content")
    parser.add_argument(
        "--start_page",
        type=int,
        default=1,
        help="Page number to start from (1-based, default: 1)",
    )
    parser.add_argument(
        "--end_page",
        type=int,
        default=None,
        help="Page number to end at (1-based, default: end)",
    )

    args = parser.parse_args()

    extract_pdf_content(args.pdf_path, args.output_dir, args.start_page, args.end_page)
