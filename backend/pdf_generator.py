"""
Converts the LLM-generated Markdown documentation into a downloadable PDF.

Uses markdown + xhtml2pdf, both pure-Python packages — no system
dependencies (like wkhtmltopdf or Cairo/Pango) required, so this works the
same on macOS, Windows, and Linux with just `pip install`.
"""
import io

import markdown
from xhtml2pdf import pisa

_PDF_CSS = """
<style>
    body { font-family: Helvetica, Arial, sans-serif; font-size: 11px; color: #222; }
    h1 { font-size: 20px; margin-bottom: 4px; }
    h2 { font-size: 15px; margin-top: 18px; margin-bottom: 6px; color: #2f5fd6; }
    p, li { line-height: 1.5; }
    pre {
        background: #f0f0f0;
        padding: 8px;
        font-family: Courier, monospace;
        font-size: 9px;
        white-space: pre-wrap;
        border-radius: 4px;
    }
    code { font-family: Courier, monospace; background: #f0f0f0; padding: 1px 3px; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0; }
    td, th { border: 1px solid #ccc; padding: 4px 8px; font-size: 10px; }
</style>
"""


def markdown_to_pdf_bytes(markdown_text):
    """Returns raw PDF bytes for the given Markdown documentation string."""
    html_body = markdown.markdown(
        markdown_text or "", extensions=["fenced_code", "tables"]
    )
    full_html = f"<html><head>{_PDF_CSS}</head><body>{html_body}</body></html>"

    buffer = io.BytesIO()
    pisa.CreatePDF(src=full_html, dest=buffer)
    return buffer.getvalue()