import json
import base64
import io
from typing import List, Dict, Optional
from PIL import Image
from openai import AzureOpenAI

from spanish_translator_config_loader import ConfigLoader
from spanish_translator_logger import logger


class OaiClient:
    def __init__(self):
        config_loader = ConfigLoader.get_instance()
        
        # Access the configuration and clients through the config_loader instance
        self.openai_api_base = config_loader.openai_api_base
        self.openai_api_key = config_loader.openai_api_key
       
        self.openai_api_version = config_loader.openai_api_version
        self.deployment_id = config_loader.deployment_id
        
        self.target_language = config_loader.target_language
        self.target_dialect = config_loader.target_dialect          

        #Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=self.openai_api_key,
            api_version=self.openai_api_version,
            azure_endpoint=self.openai_api_base
        )

    
    def _build_system_prompt(self):
        lang = self.target_language
        dialect = self.target_dialect

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

    def _prepare_image_for_vision(self, image_bytes):
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
    

    def translate_image_to_language(self,image_url):
      
        system_message = f"""
            You are a professional document translator.

            You will be shown an IMAGE extracted from a Word document. It may contain:
            - a table rendered as an image
            - headings, labels, or multiple pieces of text

            Your task:
            1. Read ALL clearly visible text in the image.
            2. Translate ALL of that text into {self.target_language}.
            3. Preserve the logical structure as plain text or simple Markdown:
            - If it looks like a table, keep a table-like layout.
            - If there are headings, keep them on separate lines.

            Important:
            - Do NOT add explanations or commentary.
            - Do NOT include the original language.
            - Output ONLY the translated text (plain/Markdown), nothing else.
            """

        user_prompt = f"""
            Translate ALL readable text in this image into {self.target_language}.
            If it looks like a table, keep a table-like layout.
            Output only the translated content.
            """

        # Normalize & upscale
        # norm_bytes = self._prepare_image_for_vision(image_bytes)
        # b64 = base64.b64encode(norm_bytes).decode("utf-8")
        # image_url = {"url": f"data:image/png;base64,{b64}"}

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
            #max_tokens=1024,
            top_p=1,
        )

        #print("response:", response)
        translated_text = response.choices[0].message.content.strip()
        logger.info(f"[image translation] GPT output (first 120 chars): {translated_text[:120]!r}")
        return translated_text
                

               

    


