import json
from pathlib import Path
from azure.storage.blob import BlobServiceClient


class ConfigLoader:
    """
    Singleton-style config loader (like BCBS survey projects).
    Loads config.json once and exposes blob + OpenAI settings.
    """
    _instance = None

    def __init__(self, config_file: str = "config.json"):
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path.resolve()}")

        with config_path.open("r", encoding="utf-8") as f:
            self.config_details = json.load(f)

        # Blob Storage
        self.storage_connection_string = self.config_details["storage_connection_string"]
        self.input_container_name = self.config_details["input_container_name"]
        self.output_container_name = self.config_details["output_container_name"]
        self.logs_container_name = self.config_details["logs_container_name"]

        self.blob_service_client = BlobServiceClient.from_connection_string(
            self.storage_connection_string
        )

        self.input_container_client = self.blob_service_client.get_container_client(
            self.input_container_name
        )
        self.output_container_client = self.blob_service_client.get_container_client(
            self.output_container_name
        )
        self.logs_container_client = self.blob_service_client.get_container_client(
            self.logs_container_name
        )

        # Azure OpenAI
        self.openai_api_base = self.config_details["openai_api_base"].rstrip("/")
        self.openai_api_key = self.config_details["openai_api_key"]
        self.openai_api_version = self.config_details["openai_api_version"]
        self.deployment_id = self.config_details["deployment_id"]

        # Translation settings
        self.target_language = self.config_details.get("target_language", "French")
        self.target_dialect = self.config_details.get("target_dialect", "France")

    @classmethod
    def get_instance(cls, config_file: str = "config.json") -> "ConfigLoader":
        if cls._instance is None:
            cls._instance = cls(config_file=config_file)
        return cls._instance
