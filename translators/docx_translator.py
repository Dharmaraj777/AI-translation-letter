import io
from typing import List, Dict, Optional

from docx import Document  # python-docx

from .base_translator import BaseTranslator
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions


class DocxTranslator(BaseTranslator):
    """
    DOCX translator.

    Key points:
    - We translate at RUN level (paragraph.runs / cell.paragraphs[].runs).
    - This preserves font, size, color, bold/italic, and inline images,
      because we never replace the whole paragraph or cell.
    - Each run with non-empty text becomes a 'segment' with a deterministic ID.
    - After translation, we walk the same structure and update run.text
      based on the ID->translation mapping.
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".docx"

    # ------------------------------------------------------------------
    # Segment collection
    # ------------------------------------------------------------------
    def _collect_segments(self, doc: Document) -> List[Dict[str, str]]:
        """
        Collect text segments at RUN level from:
          - Top-level paragraphs
          - Tables -> cells -> paragraphs -> runs
        Each segment has:
          { "id": <segment_id>, "text": <original_text> }
        """
        segments: List[Dict[str, str]] = []

        # Top-level paragraphs
        for p_idx, para in enumerate(doc.paragraphs):
            for r_idx, run in enumerate(para.runs):
                text = run.text
                if text and text.strip():
                    seg_id = f"p-{p_idx}-r-{r_idx}"
                    segments.append({"id": seg_id, "text": text})

        # Tables (cells)
        for t_idx, table in enumerate(doc.tables):
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell in enumerate(row.cells):
                    for p_idx, para in enumerate(cell.paragraphs):
                        for r_idx, run in enumerate(para.runs):
                            text = run.text
                            if text and text.strip():
                                seg_id = (
                                    f"tbl-{t_idx}-row-{row_idx}-col-{col_idx}-"
                                    f"p-{p_idx}-r-{r_idx}"
                                )
                                segments.append({"id": seg_id, "text": text})

        return segments

    # ------------------------------------------------------------------
    # Apply translations back to the document
    # ------------------------------------------------------------------
    def _apply_translations(
        self,
        doc: Document,
        id_to_translation: Dict[str, str],
    ) -> None:
        """
        Walk the document structure again and update run.text
        where we have a translation for that run's ID.
        """

        # Top-level paragraphs
        for p_idx, para in enumerate(doc.paragraphs):
            for r_idx, run in enumerate(para.runs):
                text = run.text
                if not text or not text.strip():
                    continue
                seg_id = f"p-{p_idx}-r-{r_idx}"
                if seg_id in id_to_translation:
                    run.text = id_to_translation[seg_id]

        # Tables (cells)
        for t_idx, table in enumerate(doc.tables):
            for row_idx, row in enumerate(table.rows):
                for col_idx, cell in enumerate(row.cells):
                    for p_idx, para in enumerate(cell.paragraphs):
                        for r_idx, run in enumerate(para.runs):
                            text = run.text
                            if not text or not text.strip():
                                continue
                            seg_id = (
                                f"tbl-{t_idx}-row-{row_idx}-col-{col_idx}-"
                                f"p-{p_idx}-r-{r_idx}"
                            )
                            if seg_id in id_to_translation:
                                run.text = id_to_translation[seg_id]

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
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

        # 1) Collect run-level segments
        segments = self._collect_segments(doc)
        if not segments:
            logger.info("No text segments found in DOCX, returning original document.")
            return content_bytes

        # 2) Call Azure OpenAI to translate
        id_to_translation = self.oai_client.translate_segments(
            segments,
            target_language=target_language,
            target_dialect=target_dialect,
        )

        # 3) Apply translations back to the runs
        self._apply_translations(doc, id_to_translation)

        # 4) Save to bytes
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream.read()
