"""
core/tools/documents
─────────────────────
Document parsing tools. Let agents ingest real PDF and DOCX files
provided by the user at the terminal — no file paths hardcoded in prompts.

Public exports:
  upload_document   — prompts the user in the terminal to provide a file path,
                      then parses and returns the text (PDF or DOCX auto-detected)
  parse_pdf         — parse a specific PDF file at a known path
  parse_docx        — parse a specific DOCX file at a known path
  parse_text_file   — read a plain .txt file
"""

from .parser_tools import upload_document, parse_pdf, parse_docx, parse_text_file

__all__ = ["upload_document", "parse_pdf", "parse_docx", "parse_text_file"]
