"""Backward compatibility — delegates to src.providers."""

from src.providers import generate_json, health_check

__all__ = ["generate_json", "health_check"]
