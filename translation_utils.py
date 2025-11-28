import io
import json
import os
from typing import Iterable, List, Dict
from azure.storage.blob import ContainerClient, BlobClient
from .translation_logger import logger


ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}


class UtilityFunctions:
    @staticmethod
    def get_extension(filename: str) -> str:
        return os.path.splitext(filename)[1].lower()

    @staticmethod
    def is_supported_document(filename: str) -> bool:
        return UtilityFunctions.get_extension(filename) in ALLOWED_EXTENSIONS

    @staticmethod
    def list_blobs(container_client: ContainerClient) -> List[str]:
        blob_names = []
        for blob in container_client.list_blobs():
            blob_names.append(blob.name)
        return blob_names

    @staticmethod
    def download_blob_to_bytes(blob_client: BlobClient) -> bytes:
        logger.info(f"Downloading blob: {blob_client.blob_name}")
        downloader = blob_client.download_blob()
        return downloader.readall()

    @staticmethod
    def upload_bytes_to_blob(
        container_client: ContainerClient,
        blob_name: str,
        data: bytes,
        overwrite: bool = True,
    ) -> None:
        logger.info(f"Uploading translated file: {blob_name}")
        container_client.upload_blob(name=blob_name, data=data, overwrite=overwrite)

    @staticmethod
    def chunk_list(items: List, chunk_size: int) -> Iterable[List]:
        for i in range(0, len(items), chunk_size):
            yield items[i : i + chunk_size]

    @staticmethod
    def safe_json_loads(text: str) -> Dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from model output: {e}")
            raise
