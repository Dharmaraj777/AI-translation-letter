
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient

class ConfigLoader:
    _config_instance = None

    def __init__(self, config_file='config.json'):
        if not ConfigLoader._config_instance:
            # Load configuration from the config file only once
            with open(config_file, 'r') as f:
                self.config_details = json.load(f)
            
            self.connection_string = self.config_details['storage_connection_string']
            self.content_container_name = self.config_details['spanish_translation_data_files']
            self.output_container_name = self.config_details['spanish_translation_ai_generated_output']
            self.translation_logs = self.config_details['spanish_translation_logs']
            # Create a BlobServiceClient
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)

            # Azure OpenAI Configuration
            self.openai_api_base = self.config_details['openai_api_base']
            self.openai_api_key = self.config_details['openai_api_key']
            self.openai_api_version= self.config_details['large_model_api_version']
            self.deployment_id = self.config_details['large_model']

            # Translation settings
            self.target_language = self.config_details["target_language"]
            self.target_dialect = self.config_details["target_dialect"]

            
            ConfigLoader._config_instance = self  # Cache the instance for later reuse

    @staticmethod
    def get_instance():
        if ConfigLoader._config_instance is None:
            ConfigLoader()  # Initialize if not already done
        return ConfigLoader._config_instance
