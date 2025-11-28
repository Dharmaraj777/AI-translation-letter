import json
from typing import List, Dict, Optional

from openai import AzureOpenAI
from .translation_config_loader import ConfigLoader
from .translation_logger import logger
from .translation_utils import UtilityFunctions


class OaiClient:
    """
    Azure OpenAI client wrapper for segment-based translation.
    """

    def __init__(self):
        cfg = ConfigLoader.get_instance()
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

        for batch in UtilityFunctions.chunk_list(segments, batch_size):
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

                    parsed = UtilityFunctions.safe_json_loads(content)
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
