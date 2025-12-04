import io
from typing import List, Dict, Optional, Tuple

import fitz  # PyMuPDF

from spanish_translator_logger import logger
from spanish_translator_oai_client import OaiClient


class PdfProcessor:
    """
    PDF translator.

    Strategy:
    - Use PyMuPDF to extract text spans with position + size.
    - Send spans to Azure OpenAI via translate_segments (like DOCX/PPTX).
    - Build a NEW PDF:
        * Insert the original page as a rasterized background image.
        * Overlay translated text at the same bounding boxes (visible, debug-marked).
    """

    def __init__(self, oai_client: OaiClient, raster_dpi: int = 150):
        self.oai_client = oai_client
        self.raster_dpi = raster_dpi

    # ---------------------------------------------------------
    # 1) Collect spans & metadata from the original PDF
    # ---------------------------------------------------------
    def _collect_spans(
        self,
        doc: fitz.Document,
    ) -> Tuple[List[Dict[str, str]], Dict[str, Dict]]:
        """
        Walk all pages and collect text spans with IDs and styling metadata.

        Returns:
            segments: list of {"id": seg_id, "text": original_text}
            span_meta: dict[seg_id] -> {
                "page": page_idx,
                "bbox": (x0, y0, x1, y1),
                "size": font_size,
            }
        """
        segments: List[Dict[str, str]] = []
        span_meta: Dict[str, Dict] = {}

        for page_idx, page in enumerate(doc):
            text_dict = page.get_text("dict")  # blocks -> lines -> spans
            for b_idx, block in enumerate(text_dict.get("blocks", [])):
                # type 0 == text, 1 == image, etc.
                if block.get("type", 0) != 0:
                    continue

                for l_idx, line in enumerate(block.get("lines", [])):
                    for s_idx, span in enumerate(line.get("spans", [])):
                        text = span.get("text", "")
                        if not text or not text.strip():
                            continue

                        seg_id = f"p-{page_idx}-b-{b_idx}-l-{l_idx}-s-{s_idx}"

                        segments.append({"id": seg_id, "text": text})
                        span_meta[seg_id] = {
                            "page": page_idx,
                            "bbox": span.get("bbox"),
                            "size": span.get("size", 10),
                        }

        logger.info(f"[pdf] Collected {len(segments)} text spans from PDF.")
        return segments, span_meta

    # ---------------------------------------------------------
    # 2) Build new PDF with background + translated text
    # ---------------------------------------------------------
    def _build_translated_pdf(
        self,
        original_doc: fitz.Document,
        id_to_translation: Dict[str, str],
        span_meta: Dict[str, Dict],
    ) -> bytes:
        """
        Create a new PDF:
        - For each original page:
            - New page with same size.
            - Insert rasterized original page as full-page background image.
            - Overlay translated text at each span's bbox.
        """
        new_doc = fitz.open()

        num_pages = len(original_doc)
        logger.info(f"[pdf] Rebuilding translated PDF with {num_pages} pages.")

        for page_idx in range(num_pages):
            orig_page = original_doc[page_idx]
            rect = orig_page.rect

            # New page, same size
            new_page = new_doc.new_page(width=rect.width, height=rect.height)

            # 1) Background = original page rendered as image
            try:
                # use scaling matrix so background aligns with page rect
                zoom = self.raster_dpi / 72.0
                mat = fitz.Matrix(zoom, zoom)
                pix = orig_page.get_pixmap(matrix=mat)
                new_page.insert_image(new_page.rect, pixmap=pix)
            except Exception as e:
                logger.error(f"[pdf] Failed to rasterize page {page_idx}: {e}")

            # 1b) Put a big debug header on the first page so we KNOW this is our output
            if page_idx == 0:
                header_rect = fitz.Rect(rect.x0 + 20, rect.y0 + 20, rect.x1 - 20, rect.y0 + 80)
                try:
                    new_page.insert_textbox(
                        header_rect,
                        "=== TRANSLATED TO SPANISH (DEBUG) ===",
                        fontsize=18,
                        fontname="helv",
                        color=(1, 0, 0),  # bright red
                        align=1,  # center
                    )
                except Exception as e:
                    logger.error(f"[pdf] Failed to insert debug header: {e}")

            # 2) Overlay translated text spans
            for seg_id, meta in span_meta.items():
                if meta["page"] != page_idx:
                    continue

                translated = id_to_translation.get(seg_id)
                if not translated or not translated.strip():
                    continue

                # DEBUG: prefix with [SP] so it's clearly different from original
                text_to_draw = f"[SP] {translated}"

                bbox = meta.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue

                rect_span = fitz.Rect(bbox)
                if rect_span.is_empty or rect_span.width <= 0 or rect_span.height <= 0:
                    continue

                # Slightly larger than original to make it visible
                base_size = float(meta.get("size", 10) or 10.0)
                font_size = max(base_size * 1.2, 8.0)
                font_name = "helv"  # safe built-in font

                # Dark navy overlay color
                color = (0 / 255.0, 32 / 255.0, 96 / 255.0)

                try:
                    new_page.insert_textbox(
                        rect_span,
                        text_to_draw,
                        fontsize=font_size,
                        fontname=font_name,
                        color=color,
                        align=0,  # left align
                    )
                except Exception as e:
                    logger.error(
                        f"[pdf] Failed to insert text for {seg_id} "
                        f"(font='{font_name}'): {e}. Skipping this span."
                    )
                    continue

        # Serialize new PDF to bytes
        buf = io.BytesIO()
        new_doc.save(buf)
        new_doc.close()
        buf.seek(0)
        return buf.read()

    # ---------------------------------------------------------
    # 3) Public entrypoint (matches DOCX/PPTX pattern)
    # ---------------------------------------------------------
    def translate_document(
        self,
        filename: str,
        content_bytes: bytes,
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> bytes:
        logger.info(
            f"Translating PDF document (overlay on original background): {filename}"
        )

        doc = fitz.open(stream=content_bytes, filetype="pdf")

        # Collect spans
        segments, span_meta = self._collect_spans(doc)
        if not segments:
            logger.info("[pdf] No text spans found; returning original PDF unchanged.")
            out = content_bytes
            doc.close()
            return out

        # Build id->original mapping for debug
        orig_by_id = {seg["id"]: seg["text"] for seg in segments}

        # Translate via Azure OpenAI (same API as DOCX/PPTX)
        id_to_translation = self.oai_client.translate_segments(
            segments,
            target_language=target_language,
            target_dialect=target_dialect,
        )

        # Log a few sample translations to prove it's doing something
        try:
            sample_ids = list(id_to_translation.keys())[:5]
            for sid in sample_ids:
                logger.info(
                    f"[pdf sample] {sid}: "
                    f"{orig_by_id.get(sid, '')!r} -> {id_to_translation.get(sid, '')!r}"
                )
        except Exception:
            # non-fatal if something goes wrong in debug logging
            pass

        # Build new PDF with background + translated text
        try:
            translated_bytes = self._build_translated_pdf(
                original_doc=doc,
                id_to_translation=id_to_translation,
                span_meta=span_meta,
            )
        finally:
            doc.close()

        return translated_bytes
