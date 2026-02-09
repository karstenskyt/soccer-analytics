"""Swappable VLM backend abstraction.

Currently supports Ollama (local open-source VLMs). The VLMBackend Protocol
allows adding new backends (e.g. AWS Bedrock) when needed.
"""

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)


@dataclass
class VLMResponse:
    """Standardized response from a VLM backend."""

    content: str
    model: str = ""
    usage: dict = field(default_factory=dict)


@runtime_checkable
class VLMBackend(Protocol):
    """Protocol for VLM backends."""

    async def chat_completion(
        self,
        image_path: Path,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> VLMResponse:
        """Send an image + prompt to the VLM and return the response."""
        ...


class OllamaBackend:
    """VLM backend using a local Ollama instance."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat_completion(
        self,
        image_path: Path,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> VLMResponse:
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Use native Ollama /api/chat for think control
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_b64],
                },
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "think": False,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        content = result["message"]["content"]
        usage = {}
        if "eval_count" in result:
            usage["eval_count"] = result["eval_count"]
        if "prompt_eval_count" in result:
            usage["prompt_eval_count"] = result["prompt_eval_count"]

        return VLMResponse(
            content=content,
            model=result.get("model", self.model),
            usage=usage,
        )


def create_vlm_backend(
    ollama_url: str,
    vlm_model: str,
) -> VLMBackend:
    """Create an Ollama VLM backend.

    Args:
        ollama_url: Ollama base URL.
        vlm_model: Model name (e.g. 'qwen3-vl:8b').

    Returns:
        VLMBackend instance.
    """
    return OllamaBackend(base_url=ollama_url, model=vlm_model)
