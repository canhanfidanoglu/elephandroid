output "api_fqdn" {
  description = "API container app FQDN"
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "frontend_fqdn" {
  description = "Frontend container app FQDN"
  value       = azurerm_container_app.frontend.ingress[0].fqdn
}

output "qdrant_internal_fqdn" {
  description = "Qdrant internal FQDN"
  value       = "${azurerm_container_app.qdrant.name}.internal.${azurerm_container_app_environment.main.default_domain}"
}

output "environment_id" {
  description = "Container App Environment resource ID"
  value       = azurerm_container_app_environment.main.id
}

output "environment_default_domain" {
  description = "Container App Environment default domain"
  value       = azurerm_container_app_environment.main.default_domain
}
