"""PDF 文本抽取（pdfplumber）。"""

from __future__ import annotations

from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path: str | Path) -> str:
    """用 pdfplumber 抽取 PDF 全文。

    pdfplumber 基于 pdfminer.six，中文友好，按页抽取后用空行拼接。
    """
    pdf_path = Path(pdf_path)
    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n\n".join(pages)
