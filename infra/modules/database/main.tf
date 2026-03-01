# ── Azure PostgreSQL Flexible Server ────────────────────────────────

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${var.project_name}-${var.environment}-pg"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  administrator_login           = var.admin_username
  administrator_password        = var.admin_password
  sku_name                      = "B_Standard_B1ms"
  version                       = "16"
  storage_mb                    = 32768
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = true

  tags = var.tags
}

# ── Database ───────────────────────────────────────────────────────

resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = var.database_name
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ── Firewall: Allow Azure services ─────────────────────────────────

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
