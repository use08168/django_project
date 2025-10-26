def pdf_bytes_to_markdown(data: bytes) -> str:
    """PDF → Markdown using PyMuPDF(fitz).
    - Uses page.get_text("markdown") for good heading/list/table fidelity when possible.
    - Falls back to simple text join with minimal formatting when PyMuPDF is unavailable.
    """
    try:
        import fitz  # PyMuPDF
        import io
        md_pages: list[str] = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                try:
                    # 'markdown' yields MD-like content including headings/lists/links.
                    md = page.get_text("markdown") or ""
                except Exception:
                    # fallback to plain text if markdown extractor fails on a page
                    md = page.get_text("text") or ""
                md_pages.append(md.strip())
        merged = "\n\n---\n\n".join([m for m in md_pages if m])
        if merged.strip():
            return merged
    except Exception:
        pass

    # Fallback – minimal note when extraction fails
    return (
        "# PDF Extract Summary\n\n"
        "PyMuPDF를 사용한 텍스트 추출에 실패했습니다. 운영 환경에서 라이브러리 설치 및 PDF 호환성을 확인해 주세요."
    )
