output "server_fqdn" {
  description = "PostgreSQL server FQDN"
  value       = azurerm_postgresql_flexible_server.main.fqdn
}

output "connection_string" {
  description = "PostgreSQL connection string for asyncpg"
  value       = "postgresql+asyncpg://${var.admin_username}:${var.admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${var.database_name}?ssl=require"
  sensitive   = true
}

output "server_id" {
  description = "PostgreSQL server resource ID"
  value       = azurerm_postgresql_flexible_server.main.id
}
