# ── Project ──────────────────────────────────────────────────────────

variable "project_name" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "elephandroid"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "westeurope"
}

variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

# ── Azure AD (App Registration) ────────────────────────────────────

variable "azure_client_id" {
  description = "Azure AD application (client) ID for OAuth2"
  type        = string
  sensitive   = true
}

variable "azure_client_secret" {
  description = "Azure AD application client secret"
  type        = string
  sensitive   = true
}

variable "session_secret_key" {
  description = "Secret key for session middleware signing"
  type        = string
  sensitive   = true
}

# ── Database ────────────────────────────────────────────────────────

variable "postgres_admin_password" {
  description = "PostgreSQL administrator password"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.postgres_admin_password) >= 8
    error_message = "PostgreSQL password must be at least 8 characters."
  }
}

# ── Container Images ────────────────────────────────────────────────

variable "api_image_tag" {
  description = "Docker image tag for the API container"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend container"
  type        = string
  default     = "latest"
}

# ── LLM Provider ───────────────────────────────────────────────────

variable "llm_provider" {
  description = "LLM provider: ollama, claude, openai, or gemini"
  type        = string
  default     = "claude"

  validation {
    condition     = contains(["ollama", "claude", "openai", "gemini"], var.llm_provider)
    error_message = "LLM provider must be ollama, claude, openai, or gemini."
  }
}

variable "anthropic_api_key" {
  description = "Anthropic API key (required if llm_provider=claude)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key (required if llm_provider=openai)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "gemini_api_key" {
  description = "Google Gemini API key (required if llm_provider=gemini)"
  type        = string
  default     = ""
  sensitive   = true
}

# ── Bot Service ────────────────────────────────────────────────────

variable "bot_app_id" {
  description = "Azure Bot Service application ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "bot_app_password" {
  description = "Azure Bot Service application password"
  type        = string
  default     = ""
  sensitive   = true
}

# ── CORS ───────────────────────────────────────────────────────────

variable "cors_origins" {
  description = "Allowed CORS origins (JSON array string)"
  type        = string
  default     = "[\"*\"]"
}
