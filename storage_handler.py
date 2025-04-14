import os
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from google.cloud import storage
import google.auth

def store_document(user_id, document_content):
    """
    Store the generated document in a GCP bucket, or in a local file as fallback.
    
    Args:
        user_id (str): User ID to determine the bucket folder
        document_content (str): Content to be stored in the document
        
    Returns:
        str: URL or path of the stored document
    """
    try:
        # Try GCP storage first for all environments
        try:
            return _store_document_in_gcp(user_id, document_content)
        except Exception as gcp_error:
            # Check if we're in development mode for fallback
            is_development = os.environ.get("ENVIRONMENT") == "development"
            
            if is_development:
                logging.warning(f"GCP storage failed, using local storage: {str(gcp_error)}")
                return _store_document_locally(user_id, document_content)
            else:
                # In production, we should not fall back to local storage
                logging.error(f"GCP storage error in production: {str(gcp_error)}")
                raise
            
    except Exception as e:
        logging.error(f"Error storing document: {str(e)}", exc_info=True)
        # Return the content directly as fallback
        local_path = _store_document_locally(user_id, document_content)
        return local_path

def _store_document_locally(user_id, document_content):
    """Store document in a local file for development purposes."""
    try:
        # Create a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create user directory if it doesn't exist
        user_dir = os.path.join("memorial_documents", user_id)
        os.makedirs(user_dir, exist_ok=True)
        
        # Create profile_description subdirectory
        profile_dir = os.path.join(user_dir, "profile_description")
        os.makedirs(profile_dir, exist_ok=True)
        
        # Define file path and name
        file_name = f"memorial_document_{timestamp}.md"
        file_path = os.path.join(profile_dir, file_name)
        
        # Write document content to file
        with open(file_path, 'w') as f:
            f.write(document_content)
            
        logging.info(f"Document stored locally at: {file_path}")
        
        # Return the absolute path for easier access
        abs_path = os.path.abspath(file_path)
        return abs_path
        
    except Exception as e:
        logging.error(f"Error storing document locally: {str(e)}")
        # Create a really basic fallback
        return "document_generated_but_not_stored.md"

def get_user_credentials(user_id):
    """
    Fetch the user's credentials from the GCP bucket.
    
    Args:
        user_id (str): User ID to locate the credentials file
        
    Returns:
        dict: Dictionary containing user credentials (first_name, middle_name, last_name, dob)
              or empty dict if not found
    """
    # Check if we're in development mode
    is_development = os.environ.get("ENVIRONMENT") == "development"
    
    try:
        # In development, we might not have access to GCP
        if is_development:
            # For development, we can use a mock user in certain cases
            logging.info(f"Development mode: Using local mock data for user: {user_id}")
            
            # We'll try to read from a local file first if it exists
            local_dir = os.path.join("memorial_documents", user_id, "credentials")
            local_path = os.path.join(local_dir, "login_credentials.json")
            
            if os.path.exists(local_path):
                with open(local_path, 'r') as f:
                    credentials = json.load(f)
                    
                user_info = {
                    "first_name": credentials.get("first_name", ""),
                    "middle_name": credentials.get("middle_name", ""),
                    "last_name": credentials.get("last_name", ""),
                    "dob": credentials.get("date_of_birth", "")
                }
                
                logging.info(f"Successfully retrieved local credentials for user: {user_id}")
                return user_info
            
            # In development, just continue without credentials
            logging.warning(f"No local credentials found for user: {user_id}, continuing without user info")
            return {}
        
        # Production mode, use GCP storage
        # Get GCP project ID
        project_id = os.environ.get("GCP_PROJECT_ID", "psyched-bee-455519-d7")
        
        # Initialize GCP storage client with explicit project
        storage_client = storage.Client(project=project_id)
        
        # Get bucket name from environment or use default
        bucket_name = os.environ.get("GCP_BUCKET_NAME")
        if not bucket_name:
            logging.error("GCP_BUCKET_NAME environment variable not set")
            raise ValueError("GCP_BUCKET_NAME environment variable not set")
            
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        
        # Define blob path for credentials file
        credentials_path = f"{user_id}/credentials/login_credentials.json"
        blob = bucket.blob(credentials_path)
        
        # Check if credentials file exists
        if not blob.exists():
            logging.warning(f"Credentials file not found for user: {user_id}")
            return {}
            
        # Download and parse the credentials
        credentials_data = blob.download_as_text()
        credentials = json.loads(credentials_data)
        
        # Extract required fields
        user_info = {
            "first_name": credentials.get("first_name", ""),
            "middle_name": credentials.get("middle_name", ""),
            "last_name": credentials.get("last_name", ""),
            "dob": credentials.get("date_of_birth", "")
        }
        
        logging.info(f"Successfully retrieved credentials for user: {user_id}")
        return user_info
        
    except Exception as e:
        logging.error(f"Error retrieving user credentials: {str(e)}")
        return {}

def _store_document_in_gcp(user_id, document_content):
    """Store document in a GCP bucket for production use."""
    try:
        # Check if we're in development mode with limited GCP access
        is_development = os.environ.get("ENVIRONMENT") == "development"
        
        # Skip GCP operations in development mode if needed
        if is_development and os.environ.get("SKIP_GCP_STORAGE") == "true":
            logging.warning("Development mode with SKIP_GCP_STORAGE=true, falling back to local storage")
            return _store_document_locally(user_id, document_content)
        
        # Get GCP project ID
        project_id = os.environ.get("GCP_PROJECT_ID", "psyched-bee-455519-d7")
        
        # Initialize GCP storage client with explicit project
        try:
            storage_client = storage.Client(project=project_id)
        except Exception as e:
            if is_development:
                logging.warning(f"Failed to initialize GCP storage client in development: {str(e)}")
                return _store_document_locally(user_id, document_content)
            else:
                # In production, we need to raise the error
                raise
        
        # Get bucket name from environment or use default
        bucket_name = os.environ.get("GCP_BUCKET_NAME")
        if not bucket_name:
            logging.error("GCP_BUCKET_NAME environment variable not set")
            if is_development:
                return _store_document_locally(user_id, document_content)
            raise ValueError("GCP_BUCKET_NAME environment variable not set")
            
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Define blob path with profile_description folder
        blob_name = f"{user_id}/profile_description/memorial_document_{timestamp}.md"
        blob = bucket.blob(blob_name)
        
        # Upload document content
        blob.upload_from_string(document_content, content_type="text/markdown")
        
        # Get the blob URL
        document_url = f"gs://{bucket_name}/{blob_name}"
        logging.info(f"Document stored at: {document_url}")
        
        return document_url
        
    except Exception as e:
        logging.error(f"Error storing document in GCP: {str(e)}")
        # In development, fall back to local storage
        if os.environ.get("ENVIRONMENT") == "development":
            logging.warning("Falling back to local storage due to GCP error")
            return _store_document_locally(user_id, document_content)
        # In production, raise the error
        raise
