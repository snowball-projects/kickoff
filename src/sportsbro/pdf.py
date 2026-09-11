from __future__ import annotations

from io import BytesIO


def _reader_from_bytes(content: bytes):
    from pypdf import PdfReader
    from pypdf.errors import DependencyError

    try:
        return PdfReader(BytesIO(content))
    except DependencyError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError(
            "PDF extraction requires cryptography support for encrypted official schedule documents."
        ) from exc


def extract_pdf_lines(content: bytes) -> list[str]:
    reader = _reader_from_bytes(content)
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            normalized = " ".join(line.split())
            if normalized:
                lines.append(normalized)
    return lines
