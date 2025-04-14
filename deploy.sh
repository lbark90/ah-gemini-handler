#!/bin/bash

# Memorial Document Generator API - Deployment Script
# This script deploys the application to Google Cloud Run

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}
SERVICE_NAME="memorial-document-api"
REGION="us-central1"
MEMORY="512Mi"
CPU="1"
MIN_INSTANCES=0
MAX_INSTANCES=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Exit on error
set -e

echo -e "${GREEN}=== Memorial Document Generator API Deployment ===${NC}"

# Check if project ID is available
if [ -z "$PROJECT_ID" ]; then
  echo -e "${RED}Error: No GCP project ID found. Please set GCP_PROJECT_ID environment variable or configure gcloud.${NC}"
  exit 1
fi

echo -e "${YELLOW}Project ID: ${PROJECT_ID}${NC}"

# Check if gcloud is authenticated
echo "Checking authentication..."
gcloud auth print-identity-token >/dev/null 2>&1 || {
  echo -e "${RED}Error: Not authenticated with gcloud. Please run 'gcloud auth login' first.${NC}"
  exit 1
}

# Build and push Docker image
echo -e "\n${GREEN}Building and pushing Docker image...${NC}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Create Dockerfile if it doesn't exist
if [ ! -f "Dockerfile" ]; then
  echo "Creating Dockerfile..."
  cat > Dockerfile << EOF
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 main:app
EOF
fi

# Build and push
gcloud builds submit --tag ${IMAGE_NAME} .

# Deploy to Cloud Run
echo -e "\n${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --memory ${MEMORY} \
  --cpu ${CPU} \
  --min-instances ${MIN_INSTANCES} \
  --max-instances ${MAX_INSTANCES} \
  --allow-unauthenticated

echo -e "\n${GREEN}Deployment complete!${NC}"
URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')
echo -e "Service URL: ${URL}"
echo -e "API Endpoint: ${URL}/api/process"