import io
import csv
from datetime import datetime
from typing import Optional
from azure.storage.blob import ContainerClient
from .translation_logger import logger


class OutputManager:
    """
    Simple manager to track translation status in a CSV stored in logs container.
    Appends rows like:
      timestamp, blob_name, status, details
    """

    def __init__(self, logs_container_client: ContainerClient, status_blob_name: str = "translation_status.csv"):
        self.logs_container_client = logs_container_client
        self.status_blob_name = status_blob_name

    def _download_existing_status(self) -> str:
        try:
            blob_client = self.logs_container_client.get_blob_client(self.status_blob_name)
            data = blob_client.download_blob().readall().decode("utf-8")
            return data
        except Exception:
            # No existing file
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
            # Move cursor to end
            output.seek(0, io.SEEK_END)

        timestamp = datetime.utcnow().isoformat()
        writer.writerow([timestamp, blob_name, status, details or ""])

        # Upload back
        self.logs_container_client.upload_blob(
            name=self.status_blob_name,
            data=output.getvalue().encode("utf-8"),
            overwrite=True,
        )
