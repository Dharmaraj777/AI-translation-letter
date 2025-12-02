import os
from datetime import datetime
from io import BytesIO
import base64
import logging
import fitz  # PyMuPDF
from PIL import Image
import json

from azure.storage.blob import BlobServiceClient
from spanish_translator_config_loader import ConfigLoader
from spanish_translator_logger import logger, log_stream


class PDFProcessor():
    def __init__(self):
        
        config_loader = ConfigLoader.get_instance()
        
        # Access the configuration and clients through the config_loader instance
      
        self.connection_string = config_loader.connection_string
        self.blob_service_client =  config_loader.blob_service_client
        self.output_container_name =  config_loader.output_container_name
        self.content_container_name = config_loader.content_container_name

        
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        self.container_client = self.blob_service_client.get_container_client(self.content_container_name)

    
    def process_pdf(self, file, oai_client):
        blob_client = self.container_client.get_blob_client(file)
        pdf_bytes = blob_client.download_blob().readall()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for page_number in range(len(doc)):
            try:
                print(f'Processing page: {page_number + 1}')
                page = doc.load_page(page_number)
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
                image_url = {"url": f"data:image/png;base64,{base64_image}"}

                try:
                    #print("image_url:",image_url)
                    response = oai_client.translate_image_to_language(image_url)
                    if response:
                        try:
                            print("***response:***", response)
                            #Call function to write to PDF. We may have to create the PDF doc in memory and process it
                    
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON on page {page_number + 1} of file {file}")
                except Exception as e:
                    logger.error(f"Error calling identify_urgent_efaxes on page {page_number + 1} of file {file}: {str(e)}")
                    continue
            except Exception as e:
                logger.error(f"Error processing page {page_number + 1} of file {file}: {str(e)}")
                continue
    
