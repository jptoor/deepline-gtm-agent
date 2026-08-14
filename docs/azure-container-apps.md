# Azure Container Apps Deployment

Use Azure Container Apps when you want to host the Deepline GTM agent as a
rep-facing HTTP or Slack bot surface on Azure. The app remains a thin FastAPI
broker; Deepline still owns GTM execution, provider credentials, workflows, run
state, billing, and writebacks.

Use Azure Logic Apps / Workflows around this broker when you need event
orchestration, approvals, or scheduled triggers. Do not use Logic Apps as the
primary host for the FastAPI Slack broker; point Logic Apps HTTP actions at the
Container App instead.

## What Runs

- Container source: repo root `Dockerfile`
- Runtime: `python server.py`
- Port: `8000`
- Health check: `/health`
- Readiness/config check: `/doctor`

The root `Dockerfile` mirrors the hardened `managed_agent/Dockerfile`: it uses
`managed_agent/requirements.txt`, copies only the broker package/runtime code,
and runs as a non-root user.

## One-Time Azure Setup

Install Azure CLI and the Container Apps extension:

```bash
az login
az extension add --name containerapp --upgrade
```

Create the app with external ingress. Replace names with your subscription's
resource group, location, and registry names.

```bash
az group create \
  --name deepline-gtm-agent-rg \
  --location eastus

az acr create \
  --name deeplinegtmagentacr \
  --resource-group deepline-gtm-agent-rg \
  --sku Basic

az containerapp env create \
  --name deepline-gtm-agent-env \
  --resource-group deepline-gtm-agent-rg \
  --location eastus

az containerapp create \
  --name deepline-gtm-agent \
  --resource-group deepline-gtm-agent-rg \
  --environment deepline-gtm-agent-env \
  --image mcr.microsoft.com/azuredocs/containerapps-helloworld:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3
```

Store secrets on the Container App. Do not put these values in GitHub workflow
YAML, README files, Notion pages, Slack messages, or agent prompts.

```bash
az containerapp secret set \
  --name deepline-gtm-agent \
  --resource-group deepline-gtm-agent-rg \
  --secrets \
    deepline-api-key="$DEEPLINE_API_KEY" \
    api-key="$API_KEY" \
    slack-bot-token="$SLACK_BOT_TOKEN" \
    slack-signing-secret="$SLACK_SIGNING_SECRET" \
    redis-url="$REDIS_URL"
```

For GitHub Actions deploys, create a resource-group-scoped service principal:

```bash
SUBSCRIPTION_ID="$(az account show --query id --output tsv)"

az ad sp create-for-rbac \
  --name deepline-gtm-agent-github \
  --role contributor \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/deepline-gtm-agent-rg" \
  --json-auth \
  --output json
```

Save that JSON as the GitHub Actions secret `AZURE_CREDENTIALS`.

Set these GitHub Actions variables:

| Variable | Example |
|---|---|
| `AZURE_ACR_NAME` | `deeplinegtmagentacr` |
| `AZURE_CONTAINER_APP_NAME` | `deepline-gtm-agent` |
| `AZURE_RESOURCE_GROUP` | `deepline-gtm-agent-rg` |
| `CORS_ORIGINS` | `https://your-app.example.com` |
| `SLACK_ALLOWED_CHANNEL_IDS` | `C123,C456` |
| `SLACK_ALLOWED_USER_IDS` | empty or `U123,U456` |

## Deploy From GitHub

Use `.github/workflows/azure-container-apps.yml`.

The workflow uses Microsoft's `azure/container-apps-deploy-action@v1` to build
the root Dockerfile and publish a new Container Apps revision. It references
Container App secrets using `secretref:` for `DEEPLINE_API_KEY`, `API_KEY`,
Slack tokens, and Redis.

Trigger it manually from GitHub Actions first. After the first successful run,
pushes to `main` that touch broker/runtime files deploy automatically.

## Smoke Test

After deploy, check the app without exposing secrets:

```bash
APP_FQDN="$(az containerapp show \
  --name deepline-gtm-agent \
  --resource-group deepline-gtm-agent-rg \
  --query properties.configuration.ingress.fqdn \
  --output tsv)"

curl "https://$APP_FQDN/health"
curl "https://$APP_FQDN/doctor"
```

For Slack, set the Slack app Events Request URL to:

```text
https://<container-app-fqdn>/slack/events
```

Then mention the bot in an allowed test channel:

```text
@Deepline GTM Agent research stripe.com and reply with one account brief bullet
```

## Current Local Test Status

On this machine, Docker is installed and the production container build can be
validated locally. Azure CLI is not installed, so Azure resource creation and
live Azure deployment cannot be executed from this workstation until `az` is
available and authenticated.
