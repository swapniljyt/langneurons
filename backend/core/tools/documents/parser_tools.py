"""
core/tools/documents/parser_tools.py
──────────────────────────────────────
Document parsing tools for agents that need to ingest real files.

Design principle: agents should NEVER hardcode file paths.
Instead, use upload_document() which prompts the user at the terminal
to provide a file path — making the interaction natural and path-agnostic.

Available tools:
  upload_document   — prompt user for a file path, auto-detect type, return extracted text
  parse_pdf         — parse a PDF from a known absolute/relative path
  parse_docx        — parse a DOCX from a known absolute/relative path
  parse_text_file   — read a plain .txt file from a known path

Dependencies (auto-installed in venv):
  pypdf        — pip install pypdf        (primary PDF parser)
  pdfplumber   — pip install pdfplumber   (fallback, layout-aware)
  python-docx  — pip install python-docx  (DOCX support)
"""

import os
from langchain_core.tools import tool


_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_RESET  = "\033[0m"


def _extract_text_from_path(filepath: str) -> str:
    """
    Internal helper: detects file type from extension and dispatches
    to the correct parser. Returns extracted plain text.
    """
    if not os.path.exists(filepath):
        return f"❌ File not found: {filepath}"

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return _parse_pdf_raw(filepath)
    elif ext in (".docx", ".doc"):
        return _parse_docx_raw(filepath)
    elif ext == ".txt":
        return _parse_txt_raw(filepath)
    else:
        # Attempt plain text for unknown extensions
        return _parse_txt_raw(filepath)


def _parse_pdf_raw(filepath: str) -> str:
    """
    Parse PDF using a 3-layer fallback chain:
      1. pypdf  (modern, actively maintained)
      2. pdfplumber  (layout-aware, better for tables/columns)
      3. Raw byte extraction  (last resort for corrupted/encrypted PDFs)
    Never raises ImportError — always tries the next method.
    """
    # ── Layer 1: pypdf ────────────────────────────────────────────────────────
    try:
        from pypdf import PdfReader
        reader = PdfReader(filepath)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"--- Page {i+1} ---\n{text.strip()}")
        if pages:
            return "\n\n".join(pages)
        # Pages found but no text — fall through to pdfplumber
    except ImportError:
        pass  # Fall through to next layer
    except Exception as e:
        pass  # Corrupted or encrypted — try next layer

    # ── Layer 2: pdfplumber ───────────────────────────────────────────────────
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(filepath) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"--- Page {i+1} ---\n{text.strip()}")
        if pages:
            return "\n\n".join(pages)
    except ImportError:
        pass  # Fall through to raw extraction
    except Exception:
        pass

    # ── Layer 3: PyPDF2 legacy (if installed) ─────────────────────────────────
    try:
        import PyPDF2
        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                text += f"\n--- Page {i+1} ---\n{page_text}"
        if text.strip():
            return text.strip()
    except ImportError:
        pass
    except Exception:
        pass

    # ── Layer 4: Raw byte scan (last resort) ──────────────────────────────────
    try:
        with open(filepath, "rb") as f:
            raw = f.read()
        # Extract printable ASCII sequences from raw PDF bytes
        import re
        chunks = re.findall(rb"[A-Za-z0-9 ,.\-:;!?\"'()\[\]{}\n\r\t]{4,}", raw)
        text = " ".join(c.decode("latin-1", errors="ignore") for c in chunks)
        if len(text.strip()) > 50:
            return f"[Raw extraction — formatting may be imperfect]\n\n{text.strip()}"
    except Exception as e:
        return f"❌ All PDF parsing methods failed. Last error: {str(e)}"

    return "⚠️ PDF contained no extractable text (may be image-only or encrypted)."



def _parse_docx_raw(filepath: str) -> str:
    try:
        from docx import Document
        doc  = Document(filepath)
        text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
        return text if text else "⚠️ DOCX contained no extractable text."
    except ImportError:
        return (
            "❌ python-docx is not installed. Run: pip install python-docx\n"
            "   Then try again."
        )
    except Exception as e:
        return f"❌ Error reading DOCX: {str(e)}"


def _parse_txt_raw(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="latin-1") as f:
                return f.read()
        except Exception as e:
            return f"❌ Error reading text file: {str(e)}"
    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


# ── Public LangChain tools ────────────────────────────────────────────────────

@tool
def upload_document(
    prompt_message: str = "Please provide the path to your resume document (PDF, DOCX, or TXT):",
    file_path: str = "",
) -> str:
    """
    Ingest a document (PDF, DOCX, or TXT) and return its full extracted text.

    TWO MODES:
      1. Direct mode  — if file_path is provided and the file exists, parse it immediately
                        without any dialog or user prompt. Use this when the task instructions
                        already contain the resume file path.
      2. Prompt mode  — if file_path is empty, open a file picker dialog (or ask for manual
                        input) so the candidate can provide their document live.

    Args:
        prompt_message: Message shown to the user when prompting for a file (mode 2 only).
        file_path:      Absolute path to the document. If provided and valid, skips dialog.

    Returns:
        The full extracted text content of the document.

    When to use:
        - ResumeParserAgent: call with file_path if the resume path is in your task instructions.
        - Otherwise call without file_path to prompt the candidate to upload their resume.
    """
    # ── Mode 1: Direct path provided — skip dialog completely ────────────────
    if file_path and file_path.strip():
        fp = file_path.strip().strip("'\"")
        if os.path.exists(fp):
            print(f"\n{_BOLD}{_CYAN}📎 Resume Loading:{_RESET}")
            print(f"  {_DIM}Using provided path: {fp}{_RESET}")
            print(f"  {_DIM}📖 Reading {os.path.basename(fp)}...{_RESET}\n")
            extracted_text = _extract_text_from_path(fp)
            if not extracted_text.startswith("❌"):
                char_count = len(extracted_text)
                print(f"{_GREEN}  ✔ Document parsed successfully ({char_count:,} characters extracted).{_RESET}\n")
                return f"[DOCUMENT: {os.path.basename(fp)}]\n\n{extracted_text}"
            return extracted_text
        else:
            print(f"\n{_YELLOW}  ⚠ Provided path not found: {fp} — falling back to dialog.{_RESET}\n")

    # ── Mode 2: No path provided — prompt user ────────────────────────────────
    print(f"\n{_BOLD}{_CYAN}📎 Document Upload Requested:{_RESET}")
    print(f"  {_YELLOW}{prompt_message}{_RESET}")
    print(f"{_DIM}  Supported formats: PDF, DOCX, TXT{_RESET}")

    filepath = None
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.attributes('-topmost', True)
        root.withdraw()

        print(f"{_DIM}  Opening file dialog... Please select a file from your computer.{_RESET}")

        filepath = filedialog.askopenfilename(
            parent=root,
            title=prompt_message,
            filetypes=[
                ("Documents", "*.pdf *.doc *.docx *.txt"),
                ("PDF Files", "*.pdf"),
                ("Word Documents", "*.doc *.docx"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )
        root.destroy()

        if filepath:
            print(f"{_GREEN}  Selected: {filepath}{_RESET}\n")

    except Exception:
        pass

    if not filepath:
        print(f"{_DIM}  You can drag-and-drop the file into the terminal to auto-fill the path.{_RESET}\n")
        filepath = input(f"{_GREEN}  File path: {_RESET}").strip().strip("'\"")

    if not filepath:
        return "❌ No file path provided. The document could not be uploaded."

    print(f"{_DIM}  📖 Reading {os.path.basename(filepath)}...{_RESET}\n")
    extracted_text = _extract_text_from_path(filepath)

    if extracted_text.startswith("❌"):
        return extracted_text

    char_count = len(extracted_text)
    print(f"{_GREEN}  ✔ Document parsed successfully ({char_count:,} characters extracted).{_RESET}\n")
    return f"[DOCUMENT: {os.path.basename(filepath)}]\n\n{extracted_text}"



@tool
def parse_pdf(filepath: str) -> str:
    """
    parse_pdf(filepath: str) -> str
    
    Parse a PDF file and return its full text content.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this tool ONLY when you need to extract text from a binary .pdf file.
    2. You MUST know the exact absolute or relative file path to the PDF.
    3. Do NOT use this tool for user-provided files where the path is unknown; use upload_document() instead.
    
    Args:
        filepath (str): Absolute or relative path to the PDF file.

    Returns:
        str: Extracted raw text from all pages of the PDF.
    """
    return _parse_pdf_raw(filepath)


@tool
def parse_docx(filepath: str) -> str:
    """
    parse_docx(filepath: str) -> str
    
    Parse a Microsoft Word DOCX file and return its full text content.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this tool ONLY when you need to extract text from a binary .docx or .doc file.
    2. You MUST know the exact absolute or relative file path to the document.
    3. Do NOT use this tool for user-provided files where the path is unknown; use upload_document() instead.

    Args:
        filepath (str): Absolute or relative path to the DOCX file.

    Returns:
        str: Extracted raw text from all paragraphs of the document.
    """
    return _parse_docx_raw(filepath)


@tool
def parse_text_file(filepath: str) -> str:
    """
    parse_text_file(filepath: str) -> str
    
    Read and return the contents of a plain text (.txt) file.
    
    IMPORTANT RULES FOR USING THIS TOOL:
    1. Use this tool to read a plain text file if you know the exact path.
    2. Usually, read_file() is preferred for sandbox files. Use this specifically when parsing external text documents.

    Args:
        filepath (str): Absolute or relative path to the .txt file.

    Returns:
        str: Full text content of the file.
    """
    return _parse_txt_raw(filepath)
