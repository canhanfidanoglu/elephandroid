output "bot_id" {
  description = "Azure Bot Service resource ID"
  value       = azurerm_bot_service_azure_bot.main.id
}

output "messaging_endpoint" {
  description = "Bot Framework messaging endpoint"
  value       = azurerm_bot_service_azure_bot.main.endpoint
}
