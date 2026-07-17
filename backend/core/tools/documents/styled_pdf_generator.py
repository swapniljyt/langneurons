"""
core/tools/documents/styled_pdf_generator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Styled PDF Generator — converts Markdown into a beautifully
designed PDF using HTML + CSS rendered by WeasyPrint.

Supports three built-in themes:
  - "professional"  : Dark navy header, clean two-tone layout (best for resumes)
  - "modern"        : Gradient header, accent sidebar line, card-style sections
  - "minimal"       : Ultra-clean white + grey, perfect for reports/documents

The agent should call generate_styled_pdf_from_md when the user asks for
a "beautiful", "styled", "formatted", or "professional-looking" PDF.
"""

from langchain_core.tools import tool
import os
import re
import markdown as md_lib

# ── Sandbox path resolution (same contract as write_file) ────────────────────
from ..filesystem.read_write import SANDBOX_DIR

def _resolve_output_path(output_path: str) -> str:
    if os.path.isabs(output_path) and output_path.startswith(SANDBOX_DIR):
        return output_path
    clean = output_path.lstrip("/")
    resolved = os.path.abspath(os.path.join(SANDBOX_DIR, clean))
    if not resolved.startswith(SANDBOX_DIR):
        raise ValueError(f"Path '{output_path}' resolves outside the sandbox.")
    return resolved


# ─────────────────────────────────────────────────────────────────────────────
# CSS Theme Definitions
# ─────────────────────────────────────────────────────────────────────────────

_THEMES: dict[str, str] = {

    "professional": """
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', 'DejaVu Sans', Arial, sans-serif;
            font-size: 10.5pt;
            color: #1a1a2e;
            line-height: 1.55;
            background: #ffffff;
        }
        .page-wrapper { padding: 0; }

        /* ── Header ── */
        .header {
            background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
            color: #ffffff;
            padding: 30px 40px 24px 40px;
        }
        .header h1 {
            font-size: 26pt;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 4px;
            color: #ffffff;
        }
        .header .subtitle {
            font-size: 11pt;
            color: #a8d8ea;
            font-weight: 300;
            margin-bottom: 10px;
        }
        .header .contact-row {
            font-size: 9pt;
            color: #c8e6f5;
            margin-top: 8px;
        }
        .header .contact-row a { color: #7ecef4; text-decoration: none; }

        /* ── Body ── */
        .body { padding: 28px 40px 30px 40px; }

        /* ── Section headings ── */
        h2 {
            font-size: 12pt;
            font-weight: 700;
            color: #0f3460;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            border-bottom: 2px solid #0f3460;
            padding-bottom: 4px;
            margin-top: 22px;
            margin-bottom: 10px;
        }
        h3 {
            font-size: 10.5pt;
            font-weight: 600;
            color: #16213e;
            margin-top: 12px;
            margin-bottom: 2px;
        }
        p { margin-bottom: 6px; }

        /* ── Lists ── */
        ul { padding-left: 18px; margin-bottom: 8px; }
        ul li {
            margin-bottom: 4px;
            position: relative;
        }
        ul li::marker { color: #e94560; }

        /* ── Horizontal rule ── */
        hr { display: none; }

        /* ── Inline bold / emphasis ── */
        strong { font-weight: 600; color: #0f3460; }
        em { font-style: italic; color: #555; }

        /* ── Skills pill-like styling via table-ish spans ── */
        .skills-block p { margin-bottom: 4px; }
    """,

    "modern": """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'DejaVu Sans', 'Helvetica Neue', Arial, sans-serif;
            font-size: 10pt;
            color: #2d2d2d;
            line-height: 1.6;
        }
        .page-wrapper { padding: 0; }

        /* ── Header ── */
        .header {
            background: #1b4f72;
            color: white;
            padding: 32px 40px 26px 40px;
            border-bottom: 5px solid #e67e22;
        }
        .header h1 {
            font-size: 24pt;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }
        .header .subtitle { font-size: 11pt; color: #aed6f1; margin-bottom: 8px; }
        .header .contact-row { font-size: 9pt; color: #d6eaf8; }
        .header .contact-row a { color: #f39c12; }

        /* ── Body ── */
        .body { padding: 26px 40px; border-left: 5px solid #e67e22; margin-left: 0; }

        h2 {
            font-size: 11.5pt;
            font-weight: 700;
            color: #1b4f72;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 20px;
            margin-bottom: 8px;
            padding-bottom: 3px;
            border-bottom: 1.5px solid #e67e22;
        }
        h3 {
            font-size: 10.5pt;
            font-weight: 600;
            color: #1b4f72;
            margin-top: 10px;
            margin-bottom: 2px;
        }
        p { margin-bottom: 5px; }
        ul { padding-left: 16px; margin-bottom: 8px; }
        ul li { margin-bottom: 3px; }
        ul li::marker { color: #e67e22; }
        strong { font-weight: 700; color: #1b4f72; }
        hr { display: none; }
    """,

    "minimal": """
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'DejaVu Sans', 'Georgia', serif;
            font-size: 10.5pt;
            color: #333333;
            line-height: 1.6;
        }
        .page-wrapper { padding: 0; }

        .header {
            padding: 36px 48px 20px 48px;
            border-bottom: 3px solid #333333;
        }
        .header h1 {
            font-size: 28pt;
            font-weight: 700;
            color: #111111;
            letter-spacing: 0.5px;
        }
        .header .subtitle { font-size: 11pt; color: #666; margin-top: 4px; }
        .header .contact-row { font-size: 9pt; color: #888; margin-top: 8px; }
        .header .contact-row a { color: #555; text-decoration: underline; }

        .body { padding: 24px 48px 36px 48px; }

        h2 {
            font-size: 11pt;
            font-weight: 700;
            color: #111111;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin-top: 24px;
            margin-bottom: 8px;
        }
        h3 {
            font-size: 10.5pt;
            font-weight: 600;
            color: #222;
            margin-top: 10px;
            margin-bottom: 2px;
        }
        p { margin-bottom: 6px; color: #444; }
        ul { padding-left: 20px; margin-bottom: 8px; }
        ul li { margin-bottom: 4px; color: #444; }
        strong { font-weight: 700; color: #111; }
        hr { border: none; border-top: 1px solid #ddd; margin: 12px 0; }
    """,
}


# ─────────────────────────────────────────────────────────────────────────────
# HTML Template Builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_html(md_content: str, theme: str) -> str:
    """
    Convert Markdown to a full styled HTML document using the chosen theme.

    The first H1 heading and the lines immediately after it (up to the first
    H2) are treated as the document header block (name + contact info).
    Everything else is rendered inside the styled body.
    """
    css = _THEMES.get(theme, _THEMES["professional"])

    # ── Extract header block (H1 + contact lines before first H2) ───────────
    lines = md_content.strip().split("\n")
    header_name = ""
    header_extra: list[str] = []
    body_lines: list[str] = []
    in_header = True

    for line in lines:
        s = line.strip()
        if in_header:
            if s.startswith("# ") and not s.startswith("## "):
                header_name = s[2:].strip()
            elif s.startswith("## "):
                in_header = False
                body_lines.append(line)
            elif s:
                header_extra.append(s)
        else:
            body_lines.append(line)

    # Build header HTML
    contact_html = " &nbsp;|&nbsp; ".join(
        f'<a href="{p}">{p}</a>' if p.startswith("http") else p
        for p in header_extra
        if p not in ("---", "")
    )

    header_html = f"""
    <div class="header">
        <h1>{header_name}</h1>
        <div class="contact-row">{contact_html}</div>
    </div>
    """

    # ── Convert remaining body Markdown → HTML ───────────────────────────────
    body_md = "\n".join(body_lines)
    body_html = md_lib.markdown(body_md, extensions=["extra", "nl2br"])

    # ── Assemble full HTML document ───────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
@page {{
    size: A4;
    margin: 0;
}}
{css}
</style>
</head>
<body>
<div class="page-wrapper">
    {header_html}
    <div class="body">
        {body_html}
    </div>
</div>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────────────────────
# LangChain Tool
# ─────────────────────────────────────────────────────────────────────────────

@tool
def generate_styled_pdf_from_md(
    md_content: str,
    output_path: str,
    theme: str = "professional",
) -> str:
    """
    Convert Markdown content into a BEAUTIFUL, professionally styled PDF using
    HTML + CSS rendering via WeasyPrint.

    Use this tool when the user asks for a 'beautiful', 'styled', 'formatted',
    'professional', or 'visually appealing' resume or document.

    HOW TO USE THIS TOOL:
      1. Prepare the full Markdown text of the resume or document.
      2. Choose a theme (optional):
           - "professional" → Dark navy header, red accent bullets. Best for resumes.
           - "modern"       → Blue + orange accent sidebar. Bold and eye-catching.
           - "minimal"      → Ultra-clean black & white. Great for reports.
         Default theme is "professional" if not specified.
      3. Provide the output file path (e.g. 'output/resume_styled.pdf').
      4. The tool returns a success message with the saved path, or an error.

    WHEN TO USE vs generate_pdf_from_md:
      - Use THIS tool when the user wants a visually polished, beautiful PDF.
      - Use generate_pdf_from_md for plain, simple PDF output.

    Args:
        md_content (str): Full Markdown-formatted text of the resume or document.
        output_path (str): Relative or absolute path for the output PDF.
                           Example: 'output/resume_styled.pdf'
        theme (str): Visual theme — 'professional', 'modern', or 'minimal'.
                     Defaults to 'professional'.

    Returns:
        str: '✅ Styled PDF saved to <path>' on success, or '❌ Error: <details>'.
    """
    try:
        from weasyprint import HTML as WP_HTML

        html = _build_html(md_content, theme)

        # Resolve into sandbox — same contract as write_file
        abs_path = _resolve_output_path(output_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        WP_HTML(string=html).write_pdf(abs_path)

        size_kb = round(os.path.getsize(abs_path) / 1024, 1)
        return (
            f"✅ Styled PDF ({theme} theme) saved to {abs_path} "
            f"({size_kb} KB)"
        )
    except ImportError:
        return (
            "❌ WeasyPrint is not installed. "
            "Run: pip install weasyprint"
        )
    except Exception as e:
        return f"❌ Error generating styled PDF: {e}"
