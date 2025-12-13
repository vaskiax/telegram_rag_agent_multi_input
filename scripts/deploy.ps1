# PowerShell Deployment Script for Windows Users
# Usage: .\scripts\deploy.ps1

# Configuration
$PROJECT_ID = "telegram-brain-480905"
$REGION = "us-central1"
$SERVICE_NAME = "telegram-brain-agent"
$REPO_NAME = "telegram-brain-repo"

# Load .env variables
if (Test-Path .env) {
    Write-Host "Loading variables from .env..." -ForegroundColor Gray
    Get-Content .env | Where-Object { $_ -match '=' -and -not ($_ -match '^#') } | ForEach-Object {
        $key, $value = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

Write-Host "Building and Submitting Image..." -ForegroundColor Cyan
# Build and Submit
gcloud builds submit --tag "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME" .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit $LASTEXITCODE
}

Write-Host "Deploying to Cloud Run (Initial)..." -ForegroundColor Cyan

# Construct Env Vars String dynamically from relevant keys
$RelevantKeys = @("TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "QDRANT_URL", "QDRANT_API_KEY")
$EnvVarsList = @()

foreach ($key in $RelevantKeys) {
    $val = [Environment]::GetEnvironmentVariable($key, "Process")
    if (-not [string]::IsNullOrEmpty($val)) {
        $EnvVarsList += "$key=$val"
    }
}

$EnvVarsString = $EnvVarsList -join ","

# Initial Deploy (without Webhook URL)
gcloud run deploy $SERVICE_NAME `
    --image "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/$SERVICE_NAME" `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --port 8080 `
    --no-cpu-throttling `
    --memory 2Gi `
    --cpu 2 `
    --set-env-vars $EnvVarsString

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed."
    exit $LASTEXITCODE
}

Write-Host "Retrieving Service URL..." -ForegroundColor Cyan
$ServiceUrl = gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)'

if (-not $ServiceUrl) {
    Write-Error "Failed to retrieve Service URL."
    exit 1
}

Write-Host "Service URL: $ServiceUrl" -ForegroundColor Green
Write-Host "Updating TELEGRAM_WEBHOOK_URL..." -ForegroundColor Cyan

# Update Service with Webhook URL
gcloud run services update $SERVICE_NAME `
    --platform managed `
    --region $REGION `
    --update-env-vars "TELEGRAM_WEBHOOK_URL=$ServiceUrl"

Write-Host "Deployment and Configuration Complete!" -ForegroundColor Green
