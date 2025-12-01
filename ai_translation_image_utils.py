# ai_translation_oai_client.py

import json
import base64
from typing import List, Dict, Optional

from openai import AzureOpenAI
from ai_translation_config_loader import ConfigLoader
from ai_translation_logger import logger
from ai_translation_utils import UtilityFunctions  # if you have it

class OaiClient:
    def __init__(self):
        cfg = ConfigLoader.get_instance()
        self.openai_api_base = cfg.openai_api_base
        self.openai_api_key = cfg.openai_api_key
        self.openai_api_version = cfg.openai_api_version
        self.deployment_id = cfg.deployment_id

        self.target_language = getattr(cfg, "target_language", "French")
        self.target_dialect = getattr(cfg, "target_dialect", "France")

        self.client = AzureOpenAI(
            api_key=self.openai_api_key,
            api_version=self.openai_api_version,
            azure_endpoint=self.openai_api_base,
        )

    # your existing translate_segments(...) goes here
    # ...

    def translate_image_to_language(
        self,
        image_bytes: bytes,
        content_type: str = "image/png",
        target_language: Optional[str] = None,
        target_dialect: Optional[str] = None,
    ) -> str:
        """
        Use GPT-4.1 vision to:
          - read all text from the image
          - translate it into the target language
          - return ONLY the translated text (plain / Markdown-friendly)

        This is similar to eFax get_fax_number / identify_urgent_efaxes,
        but specialized for translation.
        """
        lang = target_language or self.target_language
        dialect = target_dialect or self.target_dialect

        system_message = f"""
You are a professional document translator.

You will be shown an IMAGE extracted from a Word document. It may contain:
- a table rendered as an image
- headings, paragraphs, labels, or mixed content

Your task:
1. Read all text you can clearly see in the image.
2. Translate ALL readable text into {lang}.
3. Preserve the structure as best you can using plain text:
   - If it is a table, use a simple text layout or Markdown table.
   - If it is multiple labeled fields, keep them on separate lines.

Important:
- Do NOT add explanations or commentary.
- Do NOT invent new content.
- Do NOT include the original language, only the translated text.
- Output ONLY the translated text (plain text or simple Markdown), nothing else.
"""

        user_prompt = f"""
Translate all readable text in this image into {lang}.
If it looks like a table, keep a table-like layout in text form.
Output only the translated content.
"""

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime = content_type or "image/png"
        image_url = {"url": f"data:{mime};base64,{b64}"}

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
            max_tokens=2048,
            top_p=1,
        )

        translated_text = response.choices[0].message.content.strip()
        logger.debug(f"[image translation] raw model output: {translated_text}")
        return translated_text
