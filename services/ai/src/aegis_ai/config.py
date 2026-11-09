"""Environment-backed AI settings with secret-safe representations."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

@dataclass(frozen=True, slots=True)
class AISettings:
    """Settings for one OpenAI-compatible provider endpoint."""
    provider: str = "openai-compatible"
    base_url: str = "https://api.openai.com/v1"
    model: str = "unset"
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 30.0
    max_output_tokens: int = 1200

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("AI provider base_url must use HTTPS")
        if not parsed.netloc:
            raise ValueError("AI provider base_url must be an absolute URL")
        if not self.provider.strip() or not self.model.strip():
            raise ValueError("AI provider and model names must not be empty")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not 1 <= self.max_output_tokens <= 8192:
            raise ValueError("max_output_tokens must be between 1 and 8192")

    @classmethod
    def from_environment(cls) -> "AISettings":
        """Load settings without printing or logging credential values."""
        return cls(
            provider=os.getenv("AEGIS_AI_PROVIDER", "openai-compatible"),
            base_url=os.getenv("AEGIS_AI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("AEGIS_AI_MODEL", "unset"),
            api_key=os.getenv("AEGIS_AI_API_KEY") or None,
            timeout_seconds=float(os.getenv("AEGIS_AI_TIMEOUT_SECONDS", "30")),
            max_output_tokens=int(os.getenv("AEGIS_AI_MAX_OUTPUT_TOKENS", "1200")),
        )
