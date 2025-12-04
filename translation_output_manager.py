import io
import csv
from datetime import datetime
from typing import Optional

from azure.storage.blob import ContainerClient
from spanish_translator_logger import logger


class OutputManager:
    """
    Manages:
      1) Translation status log in a CSV stored in the logs container.
      2) Upload of translated documents into the output container.

    Status CSV rows:
      timestamp, blob_name, status, details
    """

    def __init__(
        self,
        logs_container_client: ContainerClient,
        output_container_client: ContainerClient,
        status_blob_name: str = "translation_status.csv",
    ):
        self.logs_container_client = logs_container_client
        self.output_container_client = output_container_client
        self.status_blob_name = status_blob_name

    # -----------------------------
    # Status CSV handling
    # -----------------------------
    def _download_existing_status(self) -> str:
        try:
            blob_client = self.logs_container_client.get_blob_client(self.status_blob_name)
            data = blob_client.download_blob().readall().decode("utf-8")
            return data
        except Exception:
            # No existing file or can't read -> start from empty
            return ""

    def log_status(self, blob_name: str, status: str, details: Optional[str] = None) -> None:
        logger.info(f"[STATUS] {blob_name} -> {status} ({details})")
        old_content = self._download_existing_status()

        output = io.StringIO()
        writer = csv.writer(output)

        if not old_content:
            writer.writerow(["timestamp", "blob_name", "status", "details"])
        else:
            output.write(old_content)
            output.seek(0, io.SEEK_END)

        timestamp = datetime.utcnow().isoformat()
        writer.writerow([timestamp, blob_name, status, details or ""])

        # Upload updated CSV back to logs container
        self.logs_container_client.upload_blob(
            name=self.status_blob_name,
            data=output.getvalue().encode("utf-8"),
            overwrite=True,
        )

    # -----------------------------
    # Upload translated document
    # -----------------------------
    def upload_translated_file(self,  blob_name, data, overwrite = True,):
        logger.info(f"Uploading translated file: {blob_name}")
        self.output_container_client.upload_blob(
            name=blob_name,
            data=data,
            overwrite=overwrite,
        )
