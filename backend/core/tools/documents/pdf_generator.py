from langchain_core.tools import tool
import os
import re
from fpdf import FPDF

# ── Sandbox path resolution (same contract as write_file) ────────────────────
from ..filesystem.read_write import SANDBOX_DIR

def _resolve_output_path(output_path: str) -> str:
    """
    Resolve output_path relative to SANDBOX_DIR, identical to how write_file
    resolves paths. If output_path is already absolute and inside SANDBOX_DIR,
    it is returned as-is.
    """
    if os.path.isabs(output_path) and output_path.startswith(SANDBOX_DIR):
        return output_path
    clean = output_path.lstrip("/")
    resolved = os.path.abspath(os.path.join(SANDBOX_DIR, clean))
    if not resolved.startswith(SANDBOX_DIR):
        raise ValueError(f"Path '{output_path}' resolves outside the sandbox.")
    return resolved


def _md_to_pdf(md_content: str, output_path: str) -> str:
    """
    Core Markdown → PDF renderer using fpdf2 with DejaVu Unicode fonts.

    Renders headings (##, ###), bold (**text**), horizontal rules (---),
    and plain paragraphs/bullet points. DejaVu supports the full Unicode
    range so special characters like em-dashes (—) and bullets (•) work.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # System DejaVu fonts — support full Unicode range (em-dashes, bullets, etc.)
    FONT_DIR = "/usr/share/fonts/truetype/dejavu"
    pdf.add_font("DejaVu", style="",  fname=f"{FONT_DIR}/DejaVuSans.ttf")
    pdf.add_font("DejaVu", style="B", fname=f"{FONT_DIR}/DejaVuSans-Bold.ttf")

    def set_normal(size=10):
        pdf.set_font("DejaVu", size=size)

    def set_bold(size=10):
        pdf.set_font("DejaVu", style="B", size=size)

    def strip_bold(text: str) -> str:
        """Remove **bold** markers and return plain text."""
        return re.sub(r"\*\*(.+?)\*\*", r"\1", text)

    def write_mixed_line(line: str, size: int = 10):
        """Write a line that may contain **bold** segments inline."""
        pdf.set_x(pdf.get_x())
        parts = re.split(r"(\*\*.+?\*\*)", line)
        for part in parts:
            if part.startswith("**") and part.endswith("**"):
                set_bold(size)
                pdf.write(6, part[2:-2])
            else:
                set_normal(size)
                pdf.write(6, part)
        pdf.ln(7)

    lines = md_content.split("\n")
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # H1
        if stripped.startswith("# ") and not stripped.startswith("##"):
            set_bold(16)
            pdf.ln(2)
            pdf.cell(0, 10, strip_bold(stripped[2:]), ln=True)
            pdf.ln(1)

        # H2
        elif stripped.startswith("## "):
            set_bold(13)
            pdf.ln(3)
            pdf.cell(0, 8, strip_bold(stripped[3:]), ln=True)
            # underline via thin rule
            pdf.set_draw_color(100, 100, 100)
            pdf.set_line_width(0.3)
            x, y = pdf.get_x(), pdf.get_y()
            pdf.line(x, y, x + 170, y)
            pdf.ln(3)

        # H3
        elif stripped.startswith("### "):
            set_bold(11)
            pdf.ln(2)
            pdf.cell(0, 7, strip_bold(stripped[4:]), ln=True)

        # Horizontal rule
        elif stripped == "---":
            pdf.ln(2)
            pdf.set_draw_color(180, 180, 180)
            pdf.set_line_width(0.2)
            x, y = pdf.get_x(), pdf.get_y()
            pdf.line(x, y, x + 170, y)
            pdf.ln(4)

        # Bullet points (- or *)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:]
            set_normal(10)
            pdf.set_x(pdf.get_x() + 5)
            # bullet character
            pdf.write(6, "\u2022  ")
            write_mixed_line(content, size=10)

        # Empty line → small gap
        elif stripped == "":
            pdf.ln(3)

        # Regular paragraph / italic / bold lines
        else:
            set_normal(10)
            write_mixed_line(stripped, size=10)

        i += 1

    abs_path = _resolve_output_path(output_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    pdf.output(abs_path)
    return f"✅ PDF saved to {abs_path}"


@tool
def generate_pdf_from_md(md_content: str, output_path: str) -> str:
    """
    Convert Markdown text into a PLAIN PDF file and save it to disk.

    ⚠️  USE generate_styled_pdf_from_md INSTEAD when the user asks for
         'beautiful', 'styled', 'professional-looking', 'formatted', or
         'visually appealing' output. This tool produces plain, unformatted
         PDFs only and does NOT apply any CSS styling or themes.

    HOW TO USE THIS TOOL:
      - Call this tool AFTER you have the final Markdown resume content ready.
      - Pass the raw Markdown string as `md_content`.
      - Pass the destination file path as `output_path` (e.g. 'output/resume.pdf').
      - The tool creates any missing parent directories automatically.
      - The PDF uses Unicode-safe DejaVu fonts.

    WHEN TO USE:
      - Use this ONLY for quick, plain-text PDF output.
      - For styled/beautiful PDFs → use generate_styled_pdf_from_md.

    Args:
        md_content (str): Complete Markdown-formatted resume or document text.
        output_path (str): Relative or absolute path for the output PDF file.
                           Example: 'output/resume.pdf'

    Returns:
        str: '✅ PDF saved to <path>' on success, or '❌ Error: <details>' on failure.
    """
    try:
        abs_path = _resolve_output_path(output_path)
        return _md_to_pdf(md_content, abs_path)
    except Exception as e:
        return f"❌ Error generating PDF: {e}"
