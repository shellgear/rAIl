"""
Hermes API client - direct HTTP connection to Hermes Agent (api_server platform).

Talks to the Hermes gateway's OpenAI-compatible endpoint:
    POST <endpoint> (default http://localhost:8642/v1/chat/completions)

Auth: Authorization: Bearer <HERMES_API_KEY> (from environment or rAIl/.env).
Session continuity via X-Hermes-Session-Id so Hermes keeps conversation
context across chat messages and screen-capture analyses.

Text and images (base64 JPEG/PNG) are supported. Audio requires a local
STT step before chat() (not implemented yet).
"""

import os
import logging
from pathlib import Path
from typing import Optional

import requests
import yaml

def _load_env_file() -> None:
    """Load KEY=VALUE pairs from rAIl/.env without requiring python-dotenv."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass
_load_env_file()

logger = logging.getLogger(__name__)


class HermesApiClient:
    """Synchronous client for the Hermes Agent api_server endpoint."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"

        self.config = self._load_config(config_path)
        api_cfg = self.config.get("api", {})
        # .env / environment variables win over config.yaml defaults
        self.endpoint = (os.getenv("HERMES_API_ENDPOINT")
                         or api_cfg.get("endpoint", "http://localhost:8642/v1/chat/completions"))
        self.model = api_cfg.get("model", "hermes-agent")
        self.timeout = int(os.getenv("HERMES_API_TIMEOUT") or api_cfg.get("timeout", 150))
        self.session_id = api_cfg.get("session_id", "rail-desktop")
        # Accept both "api_key_env" (name of env var) and plain "api_key".
        key_env = api_cfg.get("api_key_env", "HERMES_API_KEY")
        self.api_key = os.getenv(key_env) or api_cfg.get("api_key", "")
        # RAIL_API_ENABLED=false in .env disables the direct channel entirely.
        self._disabled = os.getenv("RAIL_API_ENABLED", "").strip().lower() == "false"

    def _load_config(self, config_path) -> dict:
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except OSError:
            return {}

    @property
    def enabled(self) -> bool:
        """True when api_server integration is configured and usable."""
        if self._disabled:
            return False
        return bool(self.api_key) and "http" in self.endpoint

    def chat(self, text: str, image_b64: Optional[str] = None,
             image_mime: str = "image/jpeg",
             session_id: Optional[str] = None) -> dict:
        """
        Send a chat turn to Hermes and wait for the reply.

        Args:
            text: user message text
            image_b64: optional base64-encoded image (no data: prefix)
            image_mime: image mime type when image_b64 is given
            session_id: override the configured session id (separate
                        contexts for chat vs. screen capture)

        Returns:
            dict with: success (bool), response (str|None), error (str|None),
                      elapsed (float)
        """
        import time
        start = time.time()

        if not self.enabled:
            return {
                "success": False,
                "response": None,
                "error": "Hermes API non configurato (HERMES_API_KEY mancante)",
                "elapsed": 0.0,
            }

        content = []
        if text:
            content.append({"type": "text", "text": text})
        if image_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime};base64,{image_b64}"},
            })
        if not content:
            content = [{"type": "text", "text": text or ""}]

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 500,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Hermes-Session-Id": session_id or self.session_id,
        }

        try:
            response = requests.post(
                self.endpoint, json=payload, headers=headers,
                timeout=self.timeout,
            )
            elapsed = time.time() - start
            response.raise_for_status()
            result = response.json()
            answer = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not answer:
                return {
                    "success": False,
                    "response": None,
                    "error": f"Hermes risposta vuota: {str(result)[:200]}",
                    "elapsed": elapsed,
                }
            return {
                "success": True,
                "response": answer,
                "error": None,
                "elapsed": elapsed,
            }

        except requests.exceptions.RequestException as exc:
            return {
                "success": False,
                "response": None,
                "error": f"Hermes API unreachable: {exc}",
                "elapsed": time.time() - start,
            }


def test_connection() -> dict:
    """Quick manual check: python -m hermes_avatar.api_client"""
    client = HermesApiClient()
    print(f"Endpoint: {client.endpoint}")
    print(f"Auth:     {'key configurata' if client.api_key else 'MANCANTE'}")
    return client.chat("Ping di test dal client Rail. Rispondi 'pong' e basta.")
