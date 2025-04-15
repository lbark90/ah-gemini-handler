import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from gemini_processor import process_with_gemini
from storage_handler import store_document, get_user_credentials, save_document_to_gcs
from dotenv import load_dotenv
from functools import wraps

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Print environment settings for debugging
env_mode = os.environ.get("ENVIRONMENT", "production")
logging.info(f"Running in {env_mode} mode")

# Middleware for API key validation
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        expected_key = os.environ.get('API_KEY') 
        
        # If running in development mode, allow missing key
        if os.environ.get("ENVIRONMENT") == "development" and not expected_key:
            logging.warning("Running in development mode without API key")
            return f(*args, **kwargs)
            
        # For production, strictly enforce API key
        if not api_key:
            logging.warning("Request missing X-API-KEY header")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
            
        if api_key != expected_key:
            logging.warning("Invalid API key provided")
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
            
        return f(*args, **kwargs)
    return decorated_function

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

@app.route('/')
def index():
    """Render the home page with basic information about the API."""
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
@require_api_key
def process_document():
    try:
        # Get request data without logging content in production
        if os.environ.get("ENVIRONMENT") != "development":
            # Minimal logging in production
            logging.info("Received processing request")
            data = request.get_json(silent=True)
        else:
            # More verbose logging in development
            logging.debug(f"Request content type: {request.content_type}")
            data = request.get_json(silent=True)
            logging.debug("Received JSON data")
        
        # Check for nested data structure
        if 'data' in data and isinstance(data['data'], dict):
            nested_data = data['data']
            
            # Extract user ID without logging
            user_id = nested_data.get('userID') or nested_data.get('user_id') or nested_data.get('userId')
            
            # Get template data (JSON array)
            template_data = nested_data.get('template', [])
            if template_data:
                # Convert template data to JSON string for Gemini
                json_data = json.dumps(template_data)
            else:
                json_data = '[]'
        else:
            # Extract from top level
            user_id = data.get('userID') or data.get('user_id') or data.get('userId')
            json_data = data.get('json_data', '[]')
        
        if not user_id:
            # Generic error without details
            return jsonify({"status": "error", "message": "Invalid request parameters"}), 400
        
        # Process with Gemini - synchronously
        result = process_with_gemini(json_data)
        
        if not result:
            logging.error("Failed to generate document content")
            return jsonify({"status": "error", "message": "Failed to generate document"}), 500
        
        # Save to GCS
        document_url = save_document_to_gcs(
            bucket_name="memorial-voices",
            user_id=user_id,
            document_content=result
        )
        
        if not document_url:
            logging.error("Failed to save document to storage")
            return jsonify({"status": "error", "message": "Failed to save document"}), 500
        
        # Return minimal success response with just the userId
        return jsonify({
            "status": "success", 
            "userId": user_id
        }), 200

    except Exception as e:
        # Simplified error handling for production
        logging.error(f"Error in process_document: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Processing request failed"}), 500

@app.route('/api/test', methods=['GET'])
@require_api_key
def test_auth():
    return jsonify({"status": "success", "message": "Authentication successful"}), 200

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
