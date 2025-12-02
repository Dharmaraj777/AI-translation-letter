import json
import base64
import io
from typing import List, Dict, Optional
from PIL import Image
from openai import AzureOpenAI
from ai_translation_config_loader import ConfigLoader
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions


class OaiClient:
    def __init__(self):
        cfg = ConfigLoader.get_instance()
        utils = UtilityFunctions()
        self.openai_api_base = cfg.openai_api_base
        self.openai_api_key = cfg.openai_api_key
        self.openai_api_version = cfg.openai_api_version
        self.deployment_id = cfg.deployment_id

        self.target_language = cfg.target_language
        self.target_dialect = cfg.target_dialect

        self.client = AzureOpenAI(
            api_key=self.openai_api_key,
            api_version=self.openai_api_version,
            azure_endpoint=self.openai_api_base,
        )

    def _build_system_prompt(self, target_language: Optional[str] = None, target_dialect: Optional[str] = None) -> str:
        lang = target_language or self.target_language
        dialect = target_dialect or self.target_dialect

        dialect_clause = ""
        if dialect:
            dialect_clause = f" Use {lang} as used in {dialect}."

        return (
            "You are a professional translator.\n"
            f"Translate all provided text into {lang}.{dialect_clause}\n"
            "You will receive a JSON object with a list of segments, each having an 'id' and 'text'.\n"
            "Return a JSON object with the same 'segments' list, same 'id' for each segment, "
            "and a new field 'text_fr' containing the translated text for each segment.\n"
            "Do NOT add, remove, or reorder segments.\n"
            "Do NOT change placeholders like {name}, {date}, {url}, etc.\n"
            "Do NOT change numbers or URLs.\n"
            "Output ONLY valid JSON, no extra commentary."
        )

    def translate_segments(
        self,
        segments: List[Dict[str, str]],
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
        batch_size: int = 100,
        max_retries: int = 3,
    ) -> Dict[str, str]:
        """
        segments: [{"id": "seg_001", "text": "..."}, ...]
        Returns:  {"seg_001": "translated text", ...}
        """

     
        logger.info(f"Translating {len(segments)} segments via Azure OpenAI...")
        id_to_translation: Dict[str, str] = {}

        system_prompt = self._build_system_prompt(target_language, target_dialect)

        for batch in utils.chunk_list(segments, batch_size):
            batch_ids = [s["id"] for s in batch]
            logger.info(f"Translating batch of {len(batch)} segments: {batch_ids[0]} ... {batch_ids[-1]}")
            payload = {"segments": batch}

            attempts = 0
            while attempts < max_retries:
                attempts += 1
                try:
                    response = self.client.chat.completions.create(
                        model=self.deployment_id,
                        temperature=0.1,
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt,
                            },
                            {
                                "role": "user",
                                "content": json.dumps(payload, ensure_ascii=False),
                            },
                        ],
                    )
                    content = response.choices[0].message.content
                    logger.debug(f"Raw model output: {content}")

                    parsed = utils.safe_json_loads(content)
                    out_segments = parsed.get("segments", [])
                    for seg in out_segments:
                        seg_id = seg["id"]
                        seg_text_fr = seg["text_fr"]
                        id_to_translation[seg_id] = seg_text_fr

                    # Sanity check
                    missing_ids = set(batch_ids) - set(id_to_translation.keys())
                    if missing_ids:
                        raise ValueError(f"Model did not return translations for IDs: {missing_ids}")

                    break  # success, go to next batch

                except Exception as e:
                    logger.error(f"Error translating batch attempt {attempts}/{max_retries}: {e}")
                    if attempts >= max_retries:
                        raise

        logger.info("Translation complete.")
        return id_to_translation
    
    def _prepare_image_for_vision(self, image_bytes: bytes) -> bytes:
        """
        Normalize and upscale the image so GPT-4.1 can read small text better:
        - Convert to RGB
        - If max dimension < 800 px, scale up to ~1024 px on the longer side
        - Encode as PNG
        """
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size

        # Upscale small images so tiny words like "rewards" are readable
        max_dim = max(w, h)
        if max_dim < 800:
            scale = 1024 / max_dim
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            logger.info(f"Upscaled image from {w}x{h} to {new_w}x{new_h} for vision OCR.")

        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        return out.read()

    def translate_image_to_language(
        self,
        image_bytes: bytes,
        content_type: str = "image/png",
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> str:
      
        lang = target_language or self.target_language
        dialect = target_dialect or self.target_dialect

        system_message = f"""
            You are a professional document translator.

            You will be shown an IMAGE extracted from a Word document. It may contain:
            - a table rendered as an image
            - headings, labels, or multiple pieces of text

            Your task:
            1. Read ALL clearly visible text in the image.
            2. Translate ALL of that text into {lang}.
            3. Preserve the logical structure as plain text or simple Markdown:
            - If it looks like a table, keep a table-like layout.
            - If there are headings, keep them on separate lines.

            Important:
            - Do NOT add explanations or commentary.
            - Do NOT include the original language.
            - Output ONLY the translated text (plain/Markdown), nothing else.
            """

        user_prompt = f"""
            Translate ALL readable text in this image into {lang}.
            If it looks like a table, keep a table-like layout.
            Output only the translated content.
            """

        # Normalize & upscale
        norm_bytes = self._prepare_image_for_vision(image_bytes)
        b64 = base64.b64encode(norm_bytes).decode("utf-8")
        image_url = {"url": f"data:image/png;base64,{b64}"}

        logger.info("Calling GPT-4.1 vision to translate image text...")
        response = self.client.chat.completions.create(
            model=self.deployment_id,
            messages=[
                {
                    "role": "system",
                    "content": system_message,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": image_url},
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=1024,
            top_p=1,
        )

        translated_text = response.choices[0].message.content.strip()
        logger.info(f"[image translation] GPT output (first 120 chars): {translated_text[:120]!r}")
        return translated_text
