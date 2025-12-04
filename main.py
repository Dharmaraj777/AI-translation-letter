from datetime import datetime
import os
from typing import List

from spanish_translator_config_loader import ConfigLoader
from spanish_translator_logger import logger, log_stream
from spanish_translator_output_manager import OutputManager
from spanish_translator_oai_client import OaiClient
from spanish_translator_utils import UtilityFunctions
from docx_processor import DocxProcessor
from pptx_processor import PptxProcessor
# from pdf_translator import PdfTranslator


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
    docx_translator = DocxProcessor(oai_client)
    pptx_translator = PptxProcessor(oai_client)
    # pdf_translator = PdfTranslator(oai_client)

    logger.info("Starting document translation pipeline.")

    try:
        file_list: List[str] = utils.get_files_to_process()

        if not file_list:
            logger.warning("No files to process.")
            return

        logger.info(f"Found the following files to process: {file_list}.")

        for file in file_list:
            try:
                # Skip if translated output already exists
                if utils.translated_output_exists(file, suffix="_fr"):
                    output_manager.log_status(
                        file,
                        "SKIPPED_ALREADY_TRANSLATED",
                        "Translated output already present in output container.",
                    )
                    continue

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
                # if extension == ".pdf":
                #     translated_bytes = pdf_translator.translate_document(
                #         file,
                #         content_bytes,
                #         target_language=cfg.target_language,
                #         target_dialect=cfg.target_dialect,
                #     )

                if extension == ".pptx":
                    print(f"Processing a **PPTX** file: **{file}**")
                    translated_bytes = pptx_translator.translate_document(
                        file,
                        content_bytes,
                        target_language=cfg.target_language,
                        target_dialect=cfg.target_dialect,
                    )

                elif extension == ".docx":
                    print(f"Processing a **DOCX** file: **{file}**")
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

                # Build output name consistently with utils
                out_name = utils.get_translated_blob_name(file, suffix="_fr")

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

    # utils.upload_log_to_blob(log_file_name, cfg, log_stream.getvalue())


if __name__ == "__main__":
    main()
