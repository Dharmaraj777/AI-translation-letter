# translators/pdf_translator.py

import io
import tempfile
from pathlib import Path
from typing import Optional

from pdf2docx import Converter

from .base_translator import BaseTranslator
from .docx_translator import DocxTranslator
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions


class PdfTranslator(BaseTranslator):
    """
    PDF translator.

    Strategy:
      1) Convert the input PDF bytes to DOCX using pdf2docx.
      2) Run the resulting DOCX through the existing DocxTranslator
         (run-level translation, GPT-4.1 vision for images).
      3) Return the translated DOCX bytes.

    Notes:
      - Output is a DOCX document, not a PDF.
      - This leverages your already-tested DOCX pipeline for consistent behavior.
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".pdf"

    def _pdf_bytes_to_docx_bytes(self, pdf_bytes: bytes) -> bytes:
        """
        Convert PDF bytes -> DOCX bytes via a temporary folder using pdf2docx.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pdf_path = tmpdir_path / "input.pdf"
            docx_path = tmpdir_path / "converted.docx"

            # Write PDF to temp file
            with open(pdf_path, "wb") as f_pdf:
                f_pdf.write(pdf_bytes)

            logger.info(f"[PDF] Converting PDF to DOCX using pdf2docx: {pdf_path}")
            try:
                cv = Converter(str(pdf_path))
                # start=0, end=None -> all pages
                cv.convert(str(docx_path), start=0, end=None)
                cv.close()
            except Exception as e:
                logger.error(f"[PDF] pdf2docx conversion failed: {e}")
                # If conversion fails, just return original PDF bytes
                # Caller can handle this gracefully.
                raise

            # Read DOCX bytes
            with open(docx_path, "rb") as f_docx:
                docx_bytes = f_docx.read()

        return docx_bytes

    def translate_document(
        self,
        filename: str,
        content_bytes: bytes,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> bytes:
        logger.info(f"Translating PDF via PDF→DOCX pipeline: {filename}")

        # 1) Convert PDF -> DOCX
        try:
            docx_bytes = self._pdf_bytes_to_docx_bytes(content_bytes)
        except Exception:
            logger.error(
                f"[PDF] Failed to convert '{filename}' to DOCX. "
                f"Returning original PDF bytes unchanged."
            )
            return content_bytes

        # 2) Use existing DocxTranslator with same OaiClient
        docx_translator = DocxTranslator(self.oai_client)

        # Derive a pseudo DOCX filename (for logging only)
        pseudo_docx_name = UtilityFunctions.replace_extension(filename, ".docx")

        translated_docx_bytes = docx_translator.translate_document(
            pseudo_docx_name,
            docx_bytes,
            target_language=target_language,
            target_dialect=target_dialect,
        )

        # 3) Return DOCX bytes (caller should name the output with .docx)
        return translated_docx_bytes
