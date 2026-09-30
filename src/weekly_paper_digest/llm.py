from __future__ import annotations

import os
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLM:
    def __init__(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set (paste it into .env).")
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=300_000,
                retry_options=types.HttpRetryOptions(
                    attempts=6, initial_delay=5, max_delay=90,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    def structured(self, model: str, system: str, contents: list, schema: type[T]) -> T:
        resp = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        if isinstance(resp.parsed, schema):
            return resp.parsed
        if not resp.text:
            raise RuntimeError(f"{model} returned no content (finish: {_finish_reason(resp)})")
        return schema.model_validate_json(resp.text)


def _finish_reason(resp) -> str:
    try:
        return str(resp.candidates[0].finish_reason)
    except (AttributeError, IndexError, TypeError):
        return "unknown"


def pdf_part(data: bytes) -> types.Part:
    return types.Part.from_bytes(data=data, mime_type="application/pdf")
