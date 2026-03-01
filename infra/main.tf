terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # Uncomment to use Azure Storage backend for remote state
  # backend "azurerm" {
  #   resource_group_name  = "elephandroid-tfstate-rg"
  #   storage_account_name = "elephandroidtfstate"
  #   container_name       = "tfstate"
  #   key                  = "elephandroid.tfstate"
  # }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# ── Resource Group ──────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location

  tags = local.tags
}

# ── Locals ──────────────────────────────────────────────────────────

locals {
  tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Modules ─────────────────────────────────────────────────────────

module "monitoring" {
  source = "./modules/monitoring"

  project_name        = var.project_name
  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

module "registry" {
  source = "./modules/registry"

  project_name        = var.project_name
  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

module "database" {
  source = "./modules/database"

  project_name        = var.project_name
  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  admin_password      = var.postgres_admin_password
  tags                = local.tags
}

module "container_apps" {
  source = "./modules/container_apps"

  project_name        = var.project_name
  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  # Registry
  registry_login_server = module.registry.login_server
  registry_username     = module.registry.admin_username
  registry_password     = module.registry.admin_password

  # Images
  api_image_tag      = var.api_image_tag
  frontend_image_tag = var.frontend_image_tag

  # Monitoring
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  app_insights_connection_string = module.monitoring.app_insights_connection_string

  # Database
  database_url = module.database.connection_string

  # App config
  azure_client_id     = var.azure_client_id
  azure_client_secret = var.azure_client_secret
  session_secret_key  = var.session_secret_key
  llm_provider        = var.llm_provider
  anthropic_api_key   = var.anthropic_api_key
  openai_api_key      = var.openai_api_key
  gemini_api_key      = var.gemini_api_key
  cors_origins        = var.cors_origins
}

module "bot" {
  source = "./modules/bot"

  project_name        = var.project_name
  environment         = var.environment
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags

  bot_app_id       = var.bot_app_id
  bot_app_password = var.bot_app_password
  api_fqdn         = module.container_apps.api_fqdn
}
