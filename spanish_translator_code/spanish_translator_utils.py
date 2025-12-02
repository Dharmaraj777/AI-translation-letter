from spanish_translator_logger import logger, log_stream
from io import BytesIO
from spanish_translator_config_loader import ConfigLoader
from azure.storage.blob import BlobServiceClient
from datetime import date
import os
import fitz  # PyMuPDF
from docx import Document
from pptx import Presentation
from io import BytesIO
from azure.storage.blob import BlobServiceClient

class UtilityFunctions:

    def __init__(self):
        '''
        This function initalize static varibales set in config.json
        '''
        self.config_loader = ConfigLoader.get_instance()
        
        # Access the configuration and clients through the config_loader instance
        
        self.connection_string = self.config_loader.connection_string
        self.blob_service_client =  self.config_loader.blob_service_client
        self.output_container_name =  self.config_loader.output_container_name
        self.content_container_name = self.config_loader.content_container_name

         

    def upload_log_to_blob(self, blob_name, config_loader, log_data):
        try:
            blob_client = config_loader.blob_service_client.get_blob_client(
                container=config_loader.efax_urgent_label_logs,
                blob=blob_name
            )
            blob_client.upload_blob(BytesIO(log_data.encode('utf-8')), overwrite=True)
            logger.info(f"Log file {blob_name} uploaded successfully.")
        except Exception as e:
            logger.error(f"Failed to upload log file {blob_name}: {str(e)}")


    def connect_to_blob_storage(self):
        """Connect to Azure Blob Storage."""
        try:
            # Get the container client
            container_client = self.blob_service_client.get_container_client(self.content_container_name)
            return container_client
        except Exception as e:
            logger.error(f"Error connecting to Azure Blob Storage: {e}")
            return None

    def get_files_in_prompt_library_container_today(self):
        """Return only files uploaded to the prompt library *today* (UTC)."""
        container_client = self.connect_to_blob_storage()
    
        files_today = []
        if container_client:
            for blob in container_client.list_blobs():
                #if blob.last_modified.date() == today:
                files_today.append(blob.name)
        return files_today


    def get_files_to_process(self):
        all_files_uploaded_today = self.get_files_in_prompt_library_container_today()
        file_list = [item for item in all_files_uploaded_today]
        return file_list


    def get_page_count_from_blob(self, blob_name):
        """
        Reads a blob from Azure Blob Storage and returns the total number of pages/slides
        for PDF, DOCX, or PPTX files.
        """
        container_client = self.blob_service_client.get_container_client(self.content_container_name)
        blob_client = container_client.get_blob_client(blob_name)
        file_data = blob_client.download_blob().readall()

        # Determine file extension
        _, ext = os.path.splitext(blob_name)
        ext = ext.lower()

        if ext == ".pdf" or ext == ".docx":
            with fitz.open(stream=file_data) as doc:
                return len(doc)  # Number of pages

        elif ext == ".pptx":
            prs = Presentation(BytesIO(file_data))
            return len(prs.slides)  # Number of slides

        else:
            raise ValueError(f"Unsupported file type: {ext}")
        
    
    