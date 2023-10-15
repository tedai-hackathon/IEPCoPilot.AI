import os
#from dotenv import load_dotenv
from chromadb.config import Settings
import chromadb

#load_dotenv()

# Define the folder for storing database
PERSIST_DIRECTORY = '/home/dlyog/chrome_db_data' #os.environ.get('PERSIST_DIRECTORY')

# Define the Chroma settings
CHROMA_SETTINGS = Settings(
        chroma_db_impl='duckdb+parquet',
        persist_directory=PERSIST_DIRECTORY,
        anonymized_telemetry=False
)

COLLETION_NAME = 'chroma_collection_iep_guid'

chroma_client = chromadb.Client(CHROMA_SETTINGS)

chroma_collection = chroma_client.get_or_create_collection(name=COLLETION_NAME, metadata={"hnsw:space": "cosine"})



