# translators/__init__.py

from ai_translation_oai_client import OaiClient

from .docx_translator import DocxTranslator
from .pptx_translator import PptxTranslator
from .pdf_translator import PdfTranslator


def get_translators(oai_client: OaiClient):
    """
    Factory to create all translator instances for a given OaiClient.

    Each translator implements:
      - can_handle(filename: str) -> bool
      - translate_document(filename, content_bytes, target_language, target_dialect) -> bytes
    """
    return [
        DocxTranslator(oai_client),
        PptxTranslator(oai_client),
        PdfTranslator(oai_client),
    ]
