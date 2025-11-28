import os
from typing import List

from translation_config_loader import ConfigLoader
from translation_logger import logger
from translation_utils import UtilityFunctions
from translation_output_manager import OutputManager
from translation_oai_client import OaiClient

from translators import DocxTranslator, PptxTranslator, PdfTranslator


def get_translators(oai_client: OaiClient):
    """
    Register available translators here.
    """
    return [
        DocxTranslator(oai_client),
        PptxTranslator(oai_client),
        PdfTranslator(oai_client),
    ]


def find_translator(filename: str, translators) -> object:
    for t in translators:
        if t.can_handle(filename):
            return t
    return None


def process_blob(
    blob_name: str,
    cfg: ConfigLoader,
    translators,
    output_manager: OutputManager,
) -> None:
    ext = UtilityFunctions.get_extension(blob_name)
    if ext not in {".docx", ".pptx", ".pdf"}:
        logger.info(f"Skipping unsupported file type: {blob_name}")
        output_manager.log_status(blob_name, "SKIPPED_UNSUPPORTED", f"Extension: {ext}")
        return

    translator = find_translator(blob_name, translators)
    if not translator:
        logger.info(f"No translator found for file: {blob_name}")
        output_manager.log_status(blob_name, "NO_TRANSLATOR", "")
        return

    input_container = cfg.input_container_client
    output_container = cfg.output_container_client

    blob_client = input_container.get_blob_client(blob_name)
    try:
        content_bytes = UtilityFunctions.download_blob_to_bytes(blob_client)
    except Exception as e:
        logger.error(f"Failed to download blob {blob_name}: {e}")
        output_manager.log_status(blob_name, "DOWNLOAD_FAILED", str(e))
        return

    try:
        translated_bytes = translator.translate_document(
            blob_name,
            content_bytes,
            target_language=cfg.target_language,
            target_dialect=cfg.target_dialect,
        )
    except Exception as e:
        logger.error(f"Translation failed for {blob_name}: {e}")
        output_manager.log_status(blob_name, "TRANSLATION_FAILED", str(e))
        return

    # Construct output name (e.g., "file.docx" -> "file_fr.docx")
    base, ext = os.path.splitext(blob_name)
    out_name = f"{base}_fr{ext}"

    try:
        UtilityFunctions.upload_bytes_to_blob(output_container, out_name, translated_bytes)
        output_manager.log_status(blob_name, "SUCCESS", f"Output: {out_name}")
    except Exception as e:
        logger.error(f"Failed to upload translated file {out_name}: {e}")
        output_manager.log_status(blob_name, "UPLOAD_FAILED", str(e))


def main():
    logger.info("Starting document translation pipeline...")

    cfg = ConfigLoader.get_instance()
    oai_client = OaiClient()
    translators = get_translators(oai_client)
    output_manager = OutputManager(cfg.logs_container_client)

    blob_names: List[str] = UtilityFunctions.list_blobs(cfg.input_container_client)
    logger.info(f"Found {len(blob_names)} blobs in input container.")

    for blob_name in blob_names:
        logger.info(f"Processing blob: {blob_name}")
        process_blob(blob_name, cfg, translators, output_manager)

    logger.info("Document translation pipeline completed.")


if __name__ == "__main__":
    main()
