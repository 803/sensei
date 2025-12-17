#!/usr/bin/env bash
#
# Deploy Sensei MCP server to Google Cloud Run
#
# Prerequisites:
#   - doppler CLI installed and authenticated
#   - gcloud CLI installed and authenticated
#   - GCP APIs enabled: run, secretmanager, cloudbuild, artifactregistry
#
# Usage:
#   ./deploy.sh
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

DOPPLER_PROJECT="sensei"
DOPPLER_CONFIG="prd"

GCP_PROJECT="gen-lang-client-0320494525"
GCP_REGION="us-central1"
SERVICE_NAME="sensei"

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

error() {
    echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2
    exit 1
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 is required but not installed"
    fi
}

# =============================================================================
# Prerequisites Check
# =============================================================================

log "Checking prerequisites..."

check_command doppler
check_command gcloud
check_command jq

# Verify Doppler is configured
if ! doppler run --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" -- true 2>/dev/null; then
    error "Doppler not configured for $DOPPLER_PROJECT/$DOPPLER_CONFIG. Run: doppler setup"
fi

# Verify GCP project matches expected
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [[ "$CURRENT_PROJECT" != "$GCP_PROJECT" ]]; then
    error "GCP project mismatch. Expected: $GCP_PROJECT, Current: $CURRENT_PROJECT. Run: gcloud config set project $GCP_PROJECT"
fi

log "Prerequisites OK"

# =============================================================================
# Enable Required APIs
# =============================================================================

log "Enabling required GCP APIs..."

gcloud services enable \
    run.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    --project="$GCP_PROJECT" \
    --quiet

# =============================================================================
# Sync Doppler Secrets to GCP Secret Manager
# =============================================================================

log "Syncing secrets from Doppler to GCP Secret Manager..."

# Get all secrets from Doppler as JSON
SECRETS_JSON=$(doppler secrets \
    --project "$DOPPLER_PROJECT" \
    --config "$DOPPLER_CONFIG" \
    --json)

# Track secret names for Cloud Run --set-secrets flag
SECRET_MAPPINGS=()

# Iterate over each secret
for SECRET_NAME in $(echo "$SECRETS_JSON" | jq -r 'keys[]'); do
    # Skip Doppler internal keys
    if [[ "$SECRET_NAME" == DOPPLER_* ]]; then
        continue
    fi

    SECRET_VALUE=$(echo "$SECRETS_JSON" | jq -r --arg key "$SECRET_NAME" '.[$key].computed')

    # Convert to lowercase with hyphens for GCP Secret Manager naming convention
    GCP_SECRET_NAME=$(echo "$SECRET_NAME" | tr '[:upper:]_' '[:lower:]-')

    # Check if secret exists
    if gcloud secrets describe "$GCP_SECRET_NAME" --project="$GCP_PROJECT" &>/dev/null; then
        # Secret exists - add new version
        log "  Updating secret: $GCP_SECRET_NAME"
        echo -n "$SECRET_VALUE" | gcloud secrets versions add "$GCP_SECRET_NAME" \
            --project="$GCP_PROJECT" \
            --data-file=- \
            --quiet
    else
        # Secret doesn't exist - create it
        log "  Creating secret: $GCP_SECRET_NAME"
        echo -n "$SECRET_VALUE" | gcloud secrets create "$GCP_SECRET_NAME" \
            --project="$GCP_PROJECT" \
            --data-file=- \
            --replication-policy="automatic" \
            --quiet
    fi

    # Build mapping: ENV_VAR=secret-name:latest
    SECRET_MAPPINGS+=("${SECRET_NAME}=${GCP_SECRET_NAME}:latest")
done

log "Synced ${#SECRET_MAPPINGS[@]} secrets"

# =============================================================================
# Grant Cloud Run Service Account Access to Secrets
# =============================================================================

log "Granting secret access to Cloud Run service account..."

# Get the project number for the compute service account
PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT" --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant access to each secret
for SECRET_NAME in $(echo "$SECRETS_JSON" | jq -r 'keys[]'); do
    if [[ "$SECRET_NAME" == DOPPLER_* ]]; then
        continue
    fi

    GCP_SECRET_NAME=$(echo "$SECRET_NAME" | tr '[:upper:]_' '[:lower:]-')

    gcloud secrets add-iam-policy-binding "$GCP_SECRET_NAME" \
        --project="$GCP_PROJECT" \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true
done

log "Secret access granted"

# =============================================================================
# Deploy to Cloud Run
# =============================================================================

log "Deploying to Cloud Run..."

# Build the --set-secrets flag value
SECRETS_FLAG=$(IFS=','; echo "${SECRET_MAPPINGS[*]}")

gcloud run deploy "$SERVICE_NAME" \
    --project="$GCP_PROJECT" \
    --region="$GCP_REGION" \
    --source=. \
    --execution-environment=gen2 \
    --allow-unauthenticated \
    --set-secrets="$SECRETS_FLAG" \
    --memory=1Gi \
    --cpu=1 \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=10 \
    --cpu-boost

# =============================================================================
# Output Service URL
# =============================================================================

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$GCP_PROJECT" \
    --region="$GCP_REGION" \
    --format="value(status.url)")

log "Deployment complete!"
log ""
log "Service URL: $SERVICE_URL"
log ""
log "Test with:"
log "  curl $SERVICE_URL/health"
