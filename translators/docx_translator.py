# translators/docx_translator.py

import io
from typing import List, Dict, Optional

from docx import Document  # python-docx
from docx.opc.constants import RELATIONSHIP_TYPE as RT

from .base_translator import BaseTranslator
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions
from ai_translation_image_utils import translate_image_with_ocr_and_gpt


class DocxTranslator(BaseTranslator):
    """
    DOCX translator.

    - Text: translates at RUN level (paragraph.runs / cell.paragraphs[].runs),
      preserving fonts, sizes, colors, and inline images.
    - Images: for each embedded image, runs OCR to detect text; if text is found,
      uses GPT to translate it and overlays translated text on the image.
      The DOCX image part is replaced with the new image bytes.
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".docx"

    # ------------------------------------------------------------------
    # Segment collection (RUN-level)
    # ------------------------------------------------------------------
    def _collect_segments(self, doc: Document) -> List[Dict[str, str]]:
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
    # Apply translations back to runs
    # ------------------------------------------------------------------
    def _apply_text_translations(
        self,
        doc: Document,
        id_to_translation: Dict[str, str],
    ) -> None:
        # Top-level paragraphs
        for p_idx, para in enumerate(doc.paragraphs):
            for r_idx, run in enumerate(para.runs):
                text = run.text
                if not text or not text.strip():
                    continue
                seg_id = f"p-{p_idx}-r-{r_idx}"
                if seg_id in id_to_translation:
                    run.text = id_to_translation[seg_id]

        # Tables
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
    # Image translation
    # ------------------------------------------------------------------
    def _translate_images_in_doc(
        self,
        doc: Document,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> None:
        """
        Iterate over all image relationships in the DOCX, run OCR+GPT on each,
        and replace the image part if we successfully create a translated version.
        """
        rels = doc.part.rels
        for rel_id, rel in rels.items():
            if rel.reltype != RT.IMAGE:
                continue

            image_part = rel.target_part
            original_bytes = image_part.blob

            try:
                new_bytes = translate_image_with_ocr_and_gpt(
                    original_bytes,
                    self.oai_client,
                    target_language=target_language,
                    target_dialect=target_dialect,
                )
            except Exception as e:
                logger.error(f"Error translating image (rel_id={rel_id}): {e}")
                continue

            if new_bytes is not None:
                logger.info(f"Replacing image (rel_id={rel_id}) with translated version.")
                # Updating the underlying blob replaces the image in the DOCX
                image_part._blob = new_bytes

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

        # 1) Collect run-level text segments
        segments = self._collect_segments(doc)
        if segments:
            id_to_translation = self.oai_client.translate_segments(
                segments,
                target_language=target_language,
                target_dialect=target_dialect,
            )
            self._apply_text_translations(doc, id_to_translation)
        else:
            logger.info("No text segments found in DOCX body text.")

        # 2) Translate images (if OCR & GPT available)
        try:
            self._translate_images_in_doc(
                doc,
                target_language=target_language,
                target_dialect=target_dialect,
            )
        except Exception as e:
            logger.error(f"Image translation step failed (non-fatal): {e}")

        # 3) Save final DOCX
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream.read()
