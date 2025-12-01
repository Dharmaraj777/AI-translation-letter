from abc import ABC, abstractmethod
from typing import Optional, Any


class BaseTranslator(ABC):
    def __init__(self, oai_client: Any):
        """
        oai_client: instance of OaiClient (from ai_translation_oai_client).
        We keep it typed as Any to avoid circular import / relative-import issues.
        """
        self.oai_client = oai_client

    @abstractmethod
    def can_handle(self, filename: str) -> bool:
        ...

    @abstractmethod
    def translate_document(
        self,
        filename: str,
        content_bytes: bytes,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> bytes:
        """
        Return translated document bytes (same format as input).
        """
        ...
