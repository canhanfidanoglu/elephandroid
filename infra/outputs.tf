# ── URLs ────────────────────────────────────────────────────────────

output "api_url" {
  description = "FastAPI backend URL"
  value       = "https://${module.container_apps.api_fqdn}"
}

output "frontend_url" {
  description = "Next.js frontend URL"
  value       = "https://${module.container_apps.frontend_fqdn}"
}

output "qdrant_internal_fqdn" {
  description = "Qdrant internal FQDN (only accessible within Container App Environment)"
  value       = module.container_apps.qdrant_internal_fqdn
}

# ── Registry ───────────────────────────────────────────────────────

output "registry_login_server" {
  description = "ACR login server for docker push"
  value       = module.registry.login_server
}

# ── Database ───────────────────────────────────────────────────────

output "postgres_fqdn" {
  description = "PostgreSQL server FQDN"
  value       = module.database.server_fqdn
}

output "postgres_connection_string" {
  description = "PostgreSQL connection string for the application"
  value       = module.database.connection_string
  sensitive   = true
}

# ── Bot ────────────────────────────────────────────────────────────

output "bot_messaging_endpoint" {
  description = "Bot Framework messaging endpoint"
  value       = module.bot.messaging_endpoint
}

# ── Monitoring ─────────────────────────────────────────────────────

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for querying logs"
  value       = module.monitoring.log_analytics_workspace_id
}

output "app_insights_instrumentation_key" {
  description = "Application Insights instrumentation key"
  value       = module.monitoring.app_insights_instrumentation_key
  sensitive   = true
}

# ── Deployment Info ────────────────────────────────────────────────

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "oauth_redirect_uri" {
  description = "OAuth2 redirect URI to configure in Azure AD app registration"
  value       = "https://${module.container_apps.api_fqdn}/auth/callback"
}
