import os
from typing import List

from ai_translation_config_loader import ConfigLoader
from ai_translation_logger import logger
from ai_translation_output_manager import OutputManager
from ai_translation_oai_client import OaiClient
from translators import get_translators
from ai_translation_utils import list_blobs, process_blob


def main():
    logger.info("Starting document translation pipeline...")

    cfg = ConfigLoader.get_instance()
    oai_client = OaiClient()
    translators = get_translators(oai_client)

    # OutputManager now handles BOTH logs and translated file uploads
    output_manager = OutputManager(
        logs_container_client=cfg.logs_container_client,
        output_container_client=cfg.output_container_client,
    )

    blob_names: List[str] = list_blobs(cfg.input_container_client)
    logger.info(f"Found {len(blob_names)} blobs in input container.")

    for blob_name in blob_names:
        logger.info(f"Processing blob: {blob_name}")
        process_blob(blob_name, cfg, translators, output_manager)

    logger.info("Document translation pipeline completed.")


if __name__ == "__main__":
    main()
