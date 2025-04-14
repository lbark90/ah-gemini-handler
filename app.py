import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from gemini_processor import process_with_gemini
from storage_handler import store_document, get_user_credentials
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Print environment settings for debugging
env_mode = os.environ.get("ENVIRONMENT", "production")
logging.info(f"Running in {env_mode} mode")

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/')
def index():
    """Render the home page with basic information about the API."""
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_webhook():
    """
    Process incoming webhook JSON data:
    1. Extract user ID
    2. Process with Gemini AI
    3. Store result in GCP bucket
    """
    try:
        # Get JSON data from request
        webhook_data = request.json
        if not webhook_data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Validate webhook data
        if not isinstance(webhook_data, dict):
            return jsonify({"error": "Invalid JSON format - expected object"}), 400
        
        # Extract user ID
        user_id = webhook_data.get('user_id')
        if not user_id:
            return jsonify({"error": "Missing user_id in request data"}), 400
        
        logging.debug(f"Processing request for user_id: {user_id}")
        
        # Retrieve user credentials from GCP bucket
        user_credentials = get_user_credentials(user_id)
        if not user_credentials:
            logging.warning(f"No credentials found for user_id: {user_id}, proceeding without user info")
        else:
            logging.info(f"Retrieved credentials for user: {user_credentials.get('first_name')} {user_credentials.get('last_name')}")
        
        # Add user credentials to the webhook data
        if user_credentials:
            webhook_data['user_info'] = user_credentials
        
        # Convert webhook data to string for the prompt
        json_string = json.dumps(webhook_data.get('reflections', []))
        
        # Process with Gemini, including user info if available
        if user_credentials:
            # Create user info string to add to the prompt
            user_info_str = f"User Info: {user_credentials.get('first_name')} {user_credentials.get('middle_name', '')} {user_credentials.get('last_name')}, DOB: {user_credentials.get('dob', 'Not provided')}"
            document_content = process_with_gemini(json_string, user_info=user_info_str)
        else:
            document_content = process_with_gemini(json_string)
        if not document_content:
            return jsonify({"error": "Failed to generate document content"}), 500
        
        # Check if content appears to be truncated
        from gemini_processor import check_for_truncation
        is_truncated, last_complete_section = check_for_truncation(document_content)
        
        # If truncated, continue generating from the last complete section
        if is_truncated and last_complete_section:
            logging.info(f"Content appears truncated. Continuing from: {last_complete_section}")
            
            # Prepare user info for continuation if available
            user_info_str = None
            if user_credentials:
                user_info_str = f"User Info: {user_credentials.get('first_name')} {user_credentials.get('middle_name', '')} {user_credentials.get('last_name')}, DOB: {user_credentials.get('dob', 'Not provided')}"
            
            # Attempt to complete the document (up to 3 retry attempts)
            for attempt in range(3):
                additional_content = process_with_gemini(
                    json_string, 
                    continue_from=last_complete_section,
                    user_info=user_info_str
                )
                
                if additional_content:
                    # Append the new content, avoiding duplication
                    if last_complete_section in additional_content:
                        # Extract only the new content (after the continuation point)
                        continuation_point = additional_content.find(last_complete_section) + len(last_complete_section)
                        additional_content = additional_content[continuation_point:]
                    
                    document_content += additional_content
                    
                    # Check if still truncated after appending
                    is_truncated, last_complete_section = check_for_truncation(document_content)
                    if not is_truncated:
                        break
                    
                    logging.info(f"Document still truncated after attempt {attempt+1}. Continuing again.")
                else:
                    logging.warning(f"Failed to generate additional content on attempt {attempt+1}")
                    break
        
        # Store document in GCP bucket
        document_url = store_document(user_id, document_content)
        
        return jsonify({
            "status": "success", 
            "message": "Document generated and stored successfully",
            "user_id": user_id,
            "document_url": document_url,
            "complete": not is_truncated
        })
        
    except Exception as e:
        logging.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
