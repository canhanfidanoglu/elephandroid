#!/usr/bin/env bash
set -euo pipefail

# ── Azure Container Apps Deploy Script ──────────────────────────────
#
# Usage:
#   ./scripts/azure-deploy.sh          # First-time setup + deploy
#   ./scripts/azure-deploy.sh update   # Redeploy after code changes
#
# Prerequisites:
#   - Azure CLI: brew install azure-cli
#   - Logged in: az login
# ────────────────────────────────────────────────────────────────────

# Config — change these
RG="elephandroid-rg"
LOCATION="westeurope"
ACR_NAME="elephandroidacr"
APP_ENV="elephandroid-env"
APP_NAME="elephandroid-app"
PG_SERVER="elephandroid-pg"
PG_USER="elephandroid"
PG_DB="elephandroid"

IMAGE="${ACR_NAME}.azurecr.io/elephandroid:latest"

echo "=== Elephandroid Azure Deploy ==="

# ── Helper: check if resource exists ──
exists() { az "$@" &>/dev/null 2>&1; }

if [[ "${1:-}" != "update" ]]; then
    echo ""
    echo "── Step 1: Resource Group ──"
    az group create --name "$RG" --location "$LOCATION" -o none
    echo "✓ Resource group: $RG"

    echo ""
    echo "── Step 2: Container Registry ──"
    if ! exists acr show --name "$ACR_NAME" --resource-group "$RG"; then
        az acr create --name "$ACR_NAME" --resource-group "$RG" --sku Basic --admin-enabled true -o none
    fi
    echo "✓ Container registry: $ACR_NAME"

    echo ""
    echo "── Step 3: PostgreSQL Flexible Server ──"
    if ! exists postgres flexible-server show --name "$PG_SERVER" --resource-group "$RG"; then
        PG_PASS=$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)
        az postgres flexible-server create \
            --name "$PG_SERVER" \
            --resource-group "$RG" \
            --location "$LOCATION" \
            --admin-user "$PG_USER" \
            --admin-password "$PG_PASS" \
            --database-name "$PG_DB" \
            --sku-name Standard_B1ms \
            --tier Burstable \
            --storage-size 32 \
            --public-access 0.0.0.0 \
            -o none
        echo "✓ PostgreSQL created. Password: $PG_PASS"
        echo "  ⚠ SAVE THIS PASSWORD — it won't be shown again!"
        echo "  DATABASE_URL=postgresql+asyncpg://${PG_USER}:${PG_PASS}@${PG_SERVER}.postgres.database.azure.com:5432/${PG_DB}"
    else
        echo "✓ PostgreSQL already exists: $PG_SERVER"
        echo "  Enter your existing password when prompted."
        read -sp "  PostgreSQL password: " PG_PASS
        echo ""
    fi

    echo ""
    echo "── Step 4: Container Apps Environment ──"
    if ! exists containerapp env show --name "$APP_ENV" --resource-group "$RG"; then
        az containerapp env create \
            --name "$APP_ENV" \
            --resource-group "$RG" \
            --location "$LOCATION" \
            -o none
    fi
    echo "✓ Container Apps environment: $APP_ENV"
fi

echo ""
echo "── Step 5: Build & Push Image ──"
az acr login --name "$ACR_NAME"
docker build -t "$IMAGE" .
docker push "$IMAGE"
echo "✓ Image pushed: $IMAGE"

echo ""
echo "── Step 6: Deploy / Update Container App ──"
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)

if exists containerapp show --name "$APP_NAME" --resource-group "$RG"; then
    # Update existing app
    az containerapp update \
        --name "$APP_NAME" \
        --resource-group "$RG" \
        --image "$IMAGE" \
        -o none
    echo "✓ App updated: $APP_NAME"
else
    # Create new app
    az containerapp create \
        --name "$APP_NAME" \
        --resource-group "$RG" \
        --environment "$APP_ENV" \
        --image "$IMAGE" \
        --registry-server "${ACR_NAME}.azurecr.io" \
        --registry-username "$ACR_NAME" \
        --registry-password "$ACR_PASS" \
        --target-port 8000 \
        --ingress external \
        --cpu 0.5 \
        --memory 1.0Gi \
        --min-replicas 0 \
        --max-replicas 3 \
        --env-vars \
            "DATABASE_URL=postgresql+asyncpg://${PG_USER}:${PG_PASS}@${PG_SERVER}.postgres.database.azure.com:5432/${PG_DB}" \
            "LLM_PROVIDER=claude" \
            "LOG_JSON=true" \
            "LOG_LEVEL=INFO" \
        -o none
    echo "✓ App created: $APP_NAME"
fi

echo ""
echo "── Step 7: Get App URL ──"
FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RG" --query "properties.configuration.ingress.fqdn" -o tsv)
echo ""
echo "════════════════════════════════════════════"
echo "  🐘 Elephandroid is live!"
echo "  URL: https://${FQDN}"
echo "════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Set env vars: az containerapp update --name $APP_NAME --resource-group $RG --set-env-vars 'AZURE_CLIENT_ID=...' 'AZURE_CLIENT_SECRET=...'"
echo "  2. Update Azure AD redirect URI to: https://${FQDN}/auth/callback"
echo "  3. Run migrations: az containerapp exec --name $APP_NAME --resource-group $RG -- alembic upgrade head"
echo "  4. To redeploy: ./scripts/azure-deploy.sh update"
