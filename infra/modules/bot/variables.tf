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

variable "bot_app_id" {
  description = "Azure AD app registration ID for the bot"
  type        = string
  sensitive   = true
}

variable "bot_app_password" {
  description = "Azure AD app registration password for the bot"
  type        = string
  sensitive   = true
}

variable "api_fqdn" {
  description = "API container app FQDN for bot messaging endpoint"
  type        = string
}
