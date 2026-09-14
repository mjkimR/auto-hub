#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-}"

if [[ -z "$REPO" ]]; then
  echo "Usage: just register-webhook <owner/repo>"
  echo "Example: just register-webhook mjkimR/my-repo"
  exit 1
fi

echo "==> Fetching Auto Hub configuration from Google Cloud..."
SERVICE_NAME="auto-hub"
REGION="asia-northeast3"

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)" 2>/dev/null || echo "https://auto-hub-y2hhy3omua-du.a.run.app")
WEBHOOK_SECRET=$(gcloud secrets versions access latest --secret=auto-hub-webhook-secret 2>/dev/null || echo "")

if [[ -z "$WEBHOOK_SECRET" ]]; then
  echo "Error: Could not retrieve 'auto-hub-webhook-secret' from Google Secret Manager."
  echo "Please make sure you are logged into gcloud and have permissions."
  exit 1
fi

WEBHOOK_URL="${SERVICE_URL}/api/github/webhooks"

echo "==> Target Repository: $REPO"
echo "==> Webhook URL:       $WEBHOOK_URL"

# Check if webhook already exists for this URL
EXISTING_HOOK_ID=$(gh api "repos/${REPO}/hooks" --jq ".[] | select(.config.url == \"${WEBHOOK_URL}\") | .id" 2>/dev/null || echo "")

if [[ -n "$EXISTING_HOOK_ID" ]]; then
  echo "==> Webhook already exists (ID: $EXISTING_HOOK_ID). Updating configuration..."
  gh api "repos/${REPO}/hooks/${EXISTING_HOOK_ID}" \
    -X PATCH \
    -F "active=true" \
    -F "events[]=pull_request" \
    -F "events[]=issue_comment" \
    -F "events[]=workflow_run" \
    -f "config[url]=${WEBHOOK_URL}" \
    -f "config[content_type]=json" \
    -f "config[secret]=${WEBHOOK_SECRET}" \
    -f "config[insecure_ssl]=0" > /dev/null
  echo "✓ Webhook (ID: $EXISTING_HOOK_ID) updated successfully!"
else
  echo "==> Creating new webhook..."
  HOOK_ID=$(gh api "repos/${REPO}/hooks" \
    -X POST \
    -f name="web" \
    -F "active=true" \
    -F "events[]=pull_request" \
    -F "events[]=issue_comment" \
    -F "events[]=workflow_run" \
    -f "config[url]=${WEBHOOK_URL}" \
    -f "config[content_type]=json" \
    -f "config[secret]=${WEBHOOK_SECRET}" \
    -f "config[insecure_ssl]=0" --jq ".id")
  echo "✓ Webhook (ID: $HOOK_ID) created successfully!"
fi

echo "==> Testing ping delivery..."
gh api "repos/${REPO}/hooks/${EXISTING_HOOK_ID:-$HOOK_ID}/pings" -X POST > /dev/null 2>&1 || true
echo "✓ Webhook is active and listening for PRs, comments, and CI workflows."
