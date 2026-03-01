# ── Azure Bot Service (F0 free tier) ────────────────────────────────

resource "azurerm_bot_service_azure_bot" "main" {
  name                = "${var.project_name}-${var.environment}-bot"
  location            = "global"
  resource_group_name = var.resource_group_name
  sku                 = "F0"
  microsoft_app_id    = var.bot_app_id

  developer_app_insights_api_key        = null
  developer_app_insights_application_id = null

  endpoint = "https://${var.api_fqdn}/bot/callbacks"

  tags = var.tags
}

# ── Teams Channel ──────────────────────────────────────────────────

resource "azurerm_bot_channel_ms_teams" "main" {
  bot_name            = azurerm_bot_service_azure_bot.main.name
  location            = azurerm_bot_service_azure_bot.main.location
  resource_group_name = var.resource_group_name
}
