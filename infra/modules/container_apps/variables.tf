variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "tags" {
  type = map(string)
}

# Registry
variable "registry_login_server" {
  type = string
}

variable "registry_username" {
  type = string
}

variable "registry_password" {
  type      = string
  sensitive = true
}

# Images
variable "api_image_tag" {
  type    = string
  default = "latest"
}

variable "frontend_image_tag" {
  type    = string
  default = "latest"
}

# Monitoring
variable "log_analytics_workspace_id" {
  type = string
}

variable "app_insights_connection_string" {
  type      = string
  sensitive = true
}

# Database
variable "database_url" {
  type      = string
  sensitive = true
}

# App config
variable "azure_client_id" {
  type      = string
  sensitive = true
}

variable "azure_client_secret" {
  type      = string
  sensitive = true
}

variable "session_secret_key" {
  type      = string
  sensitive = true
}

variable "llm_provider" {
  type    = string
  default = "claude"
}

variable "anthropic_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "openai_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "gemini_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "cors_origins" {
  type    = string
  default = "[\"*\"]"
}
