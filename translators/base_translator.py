from abc import ABC, abstractmethod
from typing import Optional
from ..translation_oai_client import OaiClient


class BaseTranslator(ABC):
    def __init__(self, oai_client: OaiClient):
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
        Return translated document bytes (same format).
        """
        ...
