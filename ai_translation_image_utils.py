# ai_translation_image_utils.py

import io
from typing import Any, Dict, List, Optional

from ai_translation_logger import logger

# Optional OCR / image libs
try:
    from PIL import Image, ImageDraw, ImageFont
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    Image = None
    ImageDraw = None
    ImageFont = None
    pytesseract = None


def _ocr_image_to_segments(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Use Tesseract OCR to extract text + bounding boxes from the image.

    Returns a list of dicts:
      {
        "id": "seg-<n>",
        "text": "original text",
        "left": int,
        "top": int,
        "width": int,
        "height": int
      }
    """
    if not OCR_AVAILABLE:
        logger.warning(
            "OCR libraries (Pillow / pytesseract) not available. "
            "Install 'Pillow' and 'pytesseract' and ensure Tesseract is installed "
            "if you want image text translation."
        )
        return []

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # pytesseract.image_to_data gives per-word / per-segment boxes
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    segments: List[Dict[str, Any]] = []
    n = len(data["text"])
    seg_idx = 0
    for i in range(n):
        text = data["text"][i]
        conf = data["conf"][i]
        if not text or not text.strip():
            continue
        try:
            conf_val = float(conf)
        except ValueError:
            conf_val = -1.0

        # Filter out very low confidence noise
        if conf_val < 0:
            continue

        left = data["left"][i]
        top = data["top"][i]
        width = data["width"][i]
        height = data["height"][i]

        seg_id = f"img_seg_{seg_idx}"
        seg_idx += 1

        segments.append(
            {
                "id": seg_id,
                "text": text,
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
        )

    return segments


def _draw_translated_text_on_image(
    image_bytes: bytes,
    segments: List[Dict[str, Any]],
    id_to_translation: Dict[str, str],
) -> bytes:
    """
    Take an image and overlay translated text in the same bounding boxes.

    - Draws a white rectangle over the original text box.
    - Writes the translated text on top (single line).
    """
    if not OCR_AVAILABLE:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Use a default font (can be customized if needed)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for seg in segments:
        seg_id = seg["id"]
        orig_text = seg["text"]
        translated = id_to_translation.get(seg_id, None)
        if not translated:
            # If no translation, keep original text as fallback
            translated = orig_text

        left = seg["left"]
        top = seg["top"]
        width = seg["width"]
        height = seg["height"]

        # Draw a white rectangle over the original text region
        # Slightly expand the box to avoid clipping
        pad = 2
        box = [
            left - pad,
            top - pad,
            left + width + pad,
            top + height + pad,
        ]
        draw.rectangle(box, fill="white")

        # Write the translated text in the same region
        # (no wrapping logic here; for long text it may overflow)
        text_x = left
        text_y = top
        draw.text((text_x, text_y), translated, fill="black", font=font)

    out = io.BytesIO()
    img.save(out, format=img.format or "PNG")
    out.seek(0)
    return out.read()


def translate_image_with_ocr_and_gpt(
    image_bytes: bytes,
    oai_client: Any,
    target_language: Optional[str] = None,
    target_dialect: Optional[str] = None,
) -> Optional[bytes]:
    """
    Full pipeline for a single image:
      1) OCR -> segments with bounding boxes
      2) GPT translation for each segment.text
      3) Draw translated text back on a copy of the image

    Returns:
      - New image bytes if we found text and translation succeeded
      - None if no text was found (or OCR unavailable)
    """
    segments = _ocr_image_to_segments(image_bytes)
    if not segments:
        logger.info("No OCR text segments found in image; leaving image unchanged.")
        return None

    # Prepare segments for GPT translation
    text_segments = [{"id": seg["id"], "text": seg["text"]} for seg in segments]

    try:
        id_to_translation = oai_client.translate_segments(
            text_segments,
            target_language=target_language,
            target_dialect=target_dialect,
        )
    except Exception as e:
        logger.error(f"Failed to translate OCR segments with GPT: {e}")
        return None

    try:
        new_image_bytes = _draw_translated_text_on_image(
            image_bytes, segments, id_to_translation
        )
        return new_image_bytes
    except Exception as e:
        logger.error(f"Failed to draw translated text on image: {e}")
        return None
