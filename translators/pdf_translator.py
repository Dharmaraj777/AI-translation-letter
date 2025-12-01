from typing import Optional

from .base_translator import BaseTranslator
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions


class PdfTranslator(BaseTranslator):
    """
    Placeholder PDF translator.
    For now just logs a message and returns original bytes.
    You can later implement:
      - PDF -> DOCX converter
      - Run DocxTranslator
      - DOCX -> PDF converter
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".pdf"

    def translate_document(
        self,
        filename: str,
        content_bytes: bytes,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> bytes:
        logger.warning(
            f"PDF translation not implemented yet for: {filename}. Returning original content."
        )
        return content_bytes
