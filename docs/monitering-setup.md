# Monitoring & Alerting Setup for QyverixAI

## Quick Start

### 1. Get a Slack Webhook URL
- Go to https://api.slack.com/apps
- Click "Create New App" → "From scratch"
- Name it "QyverixAI Alerts"
- Select your workspace
- Click "Incoming Webhooks" → "Activate Incoming Webhooks"
- Click "Add New Webhook to Workspace"
- Select channel (#alerts or #critical-alerts)
- Copy the webhook URL

### 2. Configure Alertmanager
Edit `deploy/prometheus/alertmanager.yml` and paste your webhook URL

### 3. Start Monitoring Stack
```bash
# Create docker-compose.monitoring.yml (see below)
docker-compose -f docker-compose.monitoring.yml up -d