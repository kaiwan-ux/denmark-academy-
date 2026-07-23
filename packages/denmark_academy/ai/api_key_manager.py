"""
API Key Manager with Load Balancing
Distributes requests across multiple API keys to avoid rate limits
"""
import random
from typing import Literal
from pydantic import SecretStr

from denmark_academy.config import get_settings

ProviderType = Literal["grok", "gemini"]


class APIKeyManager:
    """Manages multiple API keys with round-robin and random selection"""
    
    def __init__(self):
        self.settings = get_settings()
        self._grok_index = 0
        self._gemini_index = 0
    
    def get_grok_keys(self) -> list[SecretStr]:
        """Get unique Grok API keys."""
        return self._unique_keys([
            self.settings.grok_api_key_1,
            self.settings.grok_api_key_2,
            self.settings.grok_api_key_3,
            self.settings.grok_api_key_4,
            self.settings.grok_api_key_5,
            self.settings.grok_api_key_6,
        ])
    
    def get_gemini_keys(self) -> list[SecretStr]:
        """Get unique Gemini API keys unless Gemini is disabled."""
        if self.settings.ai_disable_gemini:
            return []
        return self._unique_keys([
            self.settings.gemini_api_key_1,
            self.settings.gemini_api_key_2,
            self.settings.gemini_api_key_3,
        ])
    
    def _unique_keys(self, keys: list[SecretStr | None]) -> list[SecretStr]:
        unique: list[SecretStr] = []
        seen: set[str] = set()
        for key in keys:
            if not key:
                continue
            value = key.get_secret_value()
            if value in seen:
                continue
            seen.add(value)
            unique.append(key)
        return unique
    
    def get_next_grok_key(self) -> SecretStr | None:
        """Get next Grok key in round-robin fashion"""
        keys = self.get_grok_keys()
        if not keys:
            return None
        key = keys[self._grok_index % len(keys)]
        self._grok_index += 1
        return key
    
    def get_next_gemini_key(self) -> SecretStr | None:
        """Get next Gemini key in round-robin fashion"""
        keys = self.get_gemini_keys()
        if not keys:
            return None
        key = keys[self._gemini_index % len(keys)]
        self._gemini_index += 1
        return key
    
    def get_random_key(self, provider: ProviderType) -> SecretStr | None:
        """Get a random key for the specified provider"""
        if provider == "grok":
            keys = self.get_grok_keys()
        else:
            keys = self.get_gemini_keys()
        
        return random.choice(keys) if keys else None
    
    def get_key_for_task(self, task: str) -> tuple[ProviderType, SecretStr | None]:
        """
        Get an API key for a task, using only providers that are enabled and configured.
        """
        available: list[ProviderType] = []
        if self.get_grok_keys():
            available.append("grok")
        if self.get_gemini_keys():
            available.append("gemini")
        if not available:
            return "grok", None

        task_name = task.lower()
        if ("search" in task_name or "explanation" in task_name) and "gemini" in available:
            return "gemini", self.get_next_gemini_key()

        provider = random.choice(available)
        key = self.get_next_grok_key() if provider == "grok" else self.get_next_gemini_key()
        return provider, key

    def has_any_keys(self) -> bool:
        """Check if any API keys are configured"""
        return bool(self.get_grok_keys() or self.get_gemini_keys())


# Singleton instance
_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get the singleton API key manager instance"""
    global _manager
    if _manager is None:
        _manager = APIKeyManager()
    return _manager

