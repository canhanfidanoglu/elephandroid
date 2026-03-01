# ── Container App Environment (Consumption plan) ───────────────────

resource "azurerm_container_app_environment" "main" {
  name                       = "${var.project_name}-${var.environment}-env"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id

  tags = var.tags
}

# ── Qdrant (internal only, always running) ─────────────────────────

resource "azurerm_container_app" "qdrant" {
  name                         = "${var.project_name}-qdrant"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "qdrant"
      image  = "qdrant/qdrant:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "QDRANT__SERVICE__HTTP_PORT"
        value = "6333"
      }

      volume_mounts {
        name = "qdrant-storage"
        path = "/qdrant/storage"
      }
    }

    volume {
      name         = "qdrant-storage"
      storage_type = "EmptyDir"
    }
  }

  ingress {
    target_port      = 6333
    external_enabled = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  tags = var.tags
}

# ── API (FastAPI backend) ──────────────────────────────────────────

resource "azurerm_container_app" "api" {
  name                         = "${var.project_name}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = var.registry_login_server
    username             = var.registry_username
    password_secret_name = "registry-password"
  }

  secret {
    name  = "registry-password"
    value = var.registry_password
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  secret {
    name  = "azure-client-id"
    value = var.azure_client_id
  }

  secret {
    name  = "azure-client-secret"
    value = var.azure_client_secret
  }

  secret {
    name  = "session-secret-key"
    value = var.session_secret_key
  }

  secret {
    name  = "anthropic-api-key"
    value = var.anthropic_api_key
  }

  secret {
    name  = "openai-api-key"
    value = var.openai_api_key
  }

  secret {
    name  = "gemini-api-key"
    value = var.gemini_api_key
  }

  template {
    min_replicas = 0
    max_replicas = 3

    container {
      name   = "api"
      image  = "${var.registry_login_server}/${var.project_name}:${var.api_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }

      env {
        name        = "AZURE_CLIENT_ID"
        secret_name = "azure-client-id"
      }

      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "azure-client-secret"
      }

      env {
        name        = "SESSION_SECRET_KEY"
        secret_name = "session-secret-key"
      }

      env {
        name  = "LLM_PROVIDER"
        value = var.llm_provider
      }

      env {
        name        = "ANTHROPIC_API_KEY"
        secret_name = "anthropic-api-key"
      }

      env {
        name        = "OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }

      env {
        name        = "GEMINI_API_KEY"
        secret_name = "gemini-api-key"
      }

      env {
        name  = "QDRANT_URL"
        value = "http://${azurerm_container_app.qdrant.name}.internal.${azurerm_container_app_environment.main.default_domain}:6333"
      }

      env {
        name  = "REDIRECT_URI"
        value = "https://${var.project_name}-api.${azurerm_container_app_environment.main.default_domain}/auth/callback"
      }

      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }

      env {
        name  = "LOG_JSON"
        value = "true"
      }

      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = var.app_insights_connection_string
      }
    }

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = "50"
    }
  }

  ingress {
    target_port      = 8000
    external_enabled = true

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  tags = var.tags
}

# ── Frontend (Next.js) ─────────────────────────────────────────────

resource "azurerm_container_app" "frontend" {
  name                         = "${var.project_name}-frontend"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  registry {
    server               = var.registry_login_server
    username             = var.registry_username
    password_secret_name = "registry-password"
  }

  secret {
    name  = "registry-password"
    value = var.registry_password
  }

  template {
    min_replicas = 0
    max_replicas = 2

    container {
      name   = "frontend"
      image  = "${var.registry_login_server}/${var.project_name}-frontend:${var.frontend_image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${var.project_name}-api.${azurerm_container_app_environment.main.default_domain}"
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
    }

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = "100"
    }
  }

  ingress {
    target_port      = 3000
    external_enabled = true

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  tags = var.tags
}
