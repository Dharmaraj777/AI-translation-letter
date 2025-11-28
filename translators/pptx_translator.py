import io
import uuid
from typing import List, Dict, Optional
from pptx import Presentation  # python-pptx

from .base_translator import BaseTranslator
from ..translation_logger import logger
from ..translation_utils import UtilityFunctions


class PptxTranslator(BaseTranslator):
    """
    Simple PPTX translator.
    Translates text at paragraph level inside shapes & table cells.
    Mixed formatting within a paragraph may lose per-word styles.
    """

    def can_handle(self, filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) == ".pptx"

    def _collect_segments(self, pres: Presentation) -> List[Dict[str, str]]:
        segments: List[Dict[str, str]] = []

        for s_idx, slide in enumerate(pres.slides):
            for sh_idx, shape in enumerate(slide.shapes):
                if not shape.has_text_frame:
                    continue
                text_frame = shape.text_frame
                for p_idx, paragraph in enumerate(text_frame.paragraphs):
                    text = paragraph.text.strip()
                    if not text:
                        continue
                    seg_id = f"s{s_idx}_sh{sh_idx}_p{p_idx}_{uuid.uuid4().hex[:8]}"
                    segments.append({"id": seg_id, "text": text})

                # Tables inside shapes are handled separately
                if shape.has_table:
                    table = shape.table
                    for r_idx, row in enumerate(table.rows):
                        for c_idx, cell in enumerate(row.cells):
                            cell_text = cell.text.strip()
                            if not cell_text:
                                continue
                            seg_id = f"s{s_idx}_tbl{sh_idx}_r{r_idx}_c{c_idx}_{uuid.uuid4().hex[:8]}"
                            segments.append({"id": seg_id, "text": cell_text})

        return segments

    def _apply_translations(self, pres: Presentation, segments: List[Dict[str, str]], id_to_translation: Dict[str, str]) -> None:
        ordered_ids = [s["id"] for s in segments]
        id_iter = iter(ordered_ids)

        for slide in pres.slides:
            for shape in slide.shapes:
                # Shape text
                if shape.has_text_frame:
                    text_frame = shape.text_frame
                    for paragraph in text_frame.paragraphs:
                        text = paragraph.text.strip()
                        if not text:
                            continue
                        seg_id = next(id_iter, None)
                        if seg_id is None:
                            return
                        translated_text = id_to_translation.get(seg_id, text)
                        paragraph.text = translated_text

                # Table text
                if shape.has_table:
                    table = shape.table
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
        logger.info(f"Translating PPTX document: {filename}")
        pres_stream = io.BytesIO(content_bytes)
        pres = Presentation(pres_stream)

        segments = self._collect_segments(pres)
        if not segments:
            logger.info("No text segments found in PPTX, returning original document.")
            return content_bytes

        id_to_translation = self.oai_client.translate_segments(
            segments,
            target_language=target_language,
            target_dialect=target_dialect,
        )

        self._apply_translations(pres, segments, id_to_translation)

        out_stream = io.BytesIO()
        pres.save(out_stream)
        out_stream.seek(0)
        return out_stream.read()
