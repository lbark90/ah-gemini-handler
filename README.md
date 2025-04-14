# Memorial Document Generator API

This is a Python Flask API that processes incoming JSON webhooks, generates custom AI-powered memorial documents using Google's Gemini AI, and stores them in GCP buckets.

## Features

- Webhook processing of JSON data containing reflections
- User credential lookup from GCP storage to personalize content
- Gemini AI integration to generate personalized memorial content
- Truncation detection and continuation for longer documents
- Service account authentication for GCP services
- Cloud storage in organized user folders
- Development mode with local storage fallback

## Setup

1. **Environment Variables**:
   Create a `.env` file with the following configuration:
   ```
   GCP_PROJECT_ID=your-project-id
   GCP_BUCKET_NAME=your-bucket-name
   ```

2. **Authentication**:
   This application uses service account authentication. Make sure you have a service account key with access to the required GCP services (Gemini AI and Cloud Storage).

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application**:
   ```bash
   gunicorn --bind 0.0.0.0:8080 --reuse-port main:app
   ```

## API Usage

### Generate a Memorial Document

**Endpoint**: `POST /api/process`

**Request Body**:
```json
{
  "user_id": "unique_user_id",
  "reflections": [
    {
      "section": "Life Overview",
      "question": "How would you describe your life?",
      "answer": "Your answer here"
    },
    {
      "section": "Childhood and Family Life",
      "question": "What are your fondest childhood memories?",
      "answer": "Your answer here"
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Document generated and stored successfully",
  "user_id": "unique_user_id",
  "document_url": "gs://your-bucket/unique_user_id/profile_description/memorial_document_20250412_123456.md",
  "complete": true
}
```

## Document Structure

The generated documents follow this format:

```markdown
**Profile Summary:**

[First-person summary of the individual's life and essence]

**Knowledge Base Document:**

## Life Overview
[Summary of life overview reflections]

## Childhood and Family Life
[Summary of childhood reflections]

## Love and Relationships
[Summary or placeholder]

...additional sections...
```

## Storage Structure

### Document Storage
Documents are stored in GCP buckets with the following path structure:
```
{user_id}/profile_description/memorial_document_{timestamp}.md
```

### User Credentials
User credentials are stored in GCP buckets with the following structure:
```
{user_id}/credentials/login_credentials.json
```

The login_credentials.json file contains the user's personal information:
```json
{
  "first_name": "User's first name",
  "middle_name": "User's middle name (optional)",
  "last_name": "User's last name",
  "date_of_birth": "YYYY-MM-DD format"
}
```

## Deployment

This application is designed to be deployed to GCP Cloud Run. It uses application default credentials for authentication in that environment.