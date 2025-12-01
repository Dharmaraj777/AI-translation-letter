import io
import uuid
from typing import List, Dict, Optional

from docx import Document  # python-docx

from .base_translator import BaseTranslator
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions


class DocxTranslator(BaseTranslator):
    """
    DOCX translator.
    Translates text at paragraph/table-cell level.

    NOTE:
    - Replaces paragraph/cell text as a whole.
    - Run-level formatting (bold/italic on specific words) may be simplified,
      but overall document layout, styles, margins, etc. remain.
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".docx"

    def _collect_segments(self, doc: Document) -> List[Dict[str, str]]:
        segments: List[Dict[str, str]] = []

        # Normal paragraphs
        for p_idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue
            seg_id = f"p_{p_idx}_{uuid.uuid4().hex[:8]}"
            segments.append({"id": seg_id, "text": text})

        # Tables (cells)
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                for c_idx, cell in enumerate(row.cells):
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue
                    seg_id = f"t_{t_idx}_r_{r_idx}_c_{c_idx}_{uuid.uuid4().hex[:8]}"
                    segments.append({"id": seg_id, "text": cell_text})

        return segments

    def _apply_translations(
        self,
        doc: Document,
        segments: List[Dict[str, str]],
        id_to_translation: Dict[str, str],
    ) -> None:
        # We rely on the same discovery order: paragraphs then tables.
        ordered_ids: List[str] = [s["id"] for s in segments]
        id_iter = iter(ordered_ids)

        # Paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            seg_id = next(id_iter, None)
            if seg_id is None:
                break
            translated_text = id_to_translation.get(seg_id, text)
            para.text = translated_text

        # Tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue
                    seg_id = next(id_iter, None)
                    if seg_id is None:
                        return
                    translated_text = id_to_translation.get(seg_id, cell_text)
                    cell.text = translated_text

    def translate_document(
        self,
        filename: str,
        content_bytes: bytes,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> bytes:
        logger.info(f"Translating DOCX document: {filename}")
        doc_stream = io.BytesIO(content_bytes)
        doc = Document(doc_stream)

        # 1) Collect segments
        segments = self._collect_segments(doc)
        if not segments:
            logger.info("No text segments found in DOCX, returning original document.")
            return content_bytes

        # 2) Call OpenAI to translate
        id_to_translation = self.oai_client.translate_segments(
            segments,
            target_language=target_language,
            target_dialect=target_dialect,
        )

        # 3) Apply translations
        self._apply_translations(doc, segments, id_to_translation)

        # 4) Save to bytes
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream.read()
