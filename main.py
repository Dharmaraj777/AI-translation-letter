# ai_translation_main.py (or main.py)

from datetime import datetime
import os
from typing import List

from ai_translation_config_loader import ConfigLoader
from ai_translation_logger import logger
from ai_translation_output_manager import OutputManager
from ai_translation_oai_client import OaiClient
from ai_translation_utils import UtilityFunctions

# Translators are now top-level modules, not inside a "translators" package
from docx_translator import DocxTranslator
from pptx_translator import PptxTranslator
from pdf_translator import PdfTranslator


def main():
    cfg = ConfigLoader.get_instance()
    today_date = datetime.now().strftime("%Y-%m-%d")
    log_file_name = f"translation_log_{today_date}.log"  # if you later want to upload logs

    oai_client = OaiClient()
    utils = UtilityFunctions()  # uses ConfigLoader internally

    # OutputManager handles logs + translated file uploads
    output_manager = OutputManager(
        logs_container_client=cfg.logs_container_client,
        output_container_client=cfg.output_container_client,
    )

    # Instantiate per-type translators (they do NOT detect extensions)
    docx_translator = DocxTranslator(oai_client)
    pptx_translator = PptxTranslator(oai_client)
    pdf_translator = PdfTranslator(oai_client)

    logger.info("Starting document translation pipeline.")

    try:
        file_list: List[str] = utils.get_files_to_process()

        if not file_list:
            logger.warning("No files to process.")
            return

        logger.info(f"Found the following files to process: {file_list}.")

        for file in file_list:
            try:
                # Page/slide count is just for logging
                try:
                    file_len = utils.get_page_count_from_blob(file)
                    logger.info(f"Processing file: {file}...with ~{file_len} pages/slides")
                except Exception as e:
                    logger.warning(f"Could not determine page count for {file}: {e}")
                    logger.info(f"Processing file: {file}...")

                extension = os.path.splitext(file)[1].lower()

                # Download content bytes once
                content_bytes = utils.download_blob_bytes(file)

                # Decide which translator to use in MAIN (not inside translators)
                if extension == ".pdf":
                    translated_bytes = pdf_translator.translate_document(
                        file,
                        content_bytes,
                        target_language=cfg.target_language,
                        target_dialect=cfg.target_dialect,
                    )

                elif extension == ".pptx":
                    translated_bytes = pptx_translator.translate_document(
                        file,
                        content_bytes,
                        target_language=cfg.target_language,
                        target_dialect=cfg.target_dialect,
                    )

                elif extension == ".docx":
                    translated_bytes = docx_translator.translate_document(
                        file,
                        content_bytes,
                        target_language=cfg.target_language,
                        target_dialect=cfg.target_dialect,
                    )

                else:
                    logger.error(
                        f"This application is not able to process file with extension type: {extension} at this time."
                    )
                    output_manager.log_status(file, "SKIPPED_UNSUPPORTED", f"Extension: {extension}")
                    continue

                # Build output name: file -> file_fr.ext
                base, ext_only = os.path.splitext(file)
                out_name = f"{base}_fr{ext_only}"

                # Save translated file via OutputManager
                output_manager.upload_translated_file(out_name, translated_bytes)
                output_manager.log_status(file, "SUCCESS", f"Output: {out_name}")

                print("\n______________________________________")

            except Exception as e:
                logger.error(f"Error processing file {file}: {str(e)}")
                output_manager.log_status(file, "TRANSLATION_FAILED", str(e))
                continue

    except Exception as e:
        logger.error(f"An error occurred in the main process: {str(e)}")

    logger.info("************* END of Processing File ******************")

    # If you later want to upload logs blob:
    # from ai_translation_logger import log_stream
    # utils.upload_log_to_blob(log_file_name, cfg, log_stream.getvalue())


if __name__ == "__main__":
    main()
