"""Structured extraction via the Anthropic Messages API.

Why not the Agent SDK here? Extraction is a *deterministic, single-shot*
operation: render a page, hand the model the image (authoritative) plus the
garbled OCR text (hint), and force it to return data conforming to a Pydantic
model. Forced tool use + schema validation makes that predictable and unit-
testable. The Agent SDK (``bosc.agent.client``) remains the home for open-ended
*research* over already-extracted data; this primitive can be exposed to it as
a tool later.
"""

from __future__ import annotations

import base64
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_MEDIA_TYPE = "image/png"
_OCR_HINT_HEADER = (
    "\n\n--- Embedded OCR text layer (UNRELIABLE: digits are frequently wrong; "
    "verify every number against the image) ---\n"
)


class ExtractionError(RuntimeError):
    """Raised when the model fails to return the forced tool call."""


def _tool_schema(target: type[BaseModel]) -> dict[str, Any]:
    """JSON schema for a target model, minus any ``EXTRACTION_EXCLUDE`` fields.

    Hiding noise fields (rather than just ignoring them on the way back) keeps the
    model from filling them with misplaced sheet metadata.
    """
    schema = target.model_json_schema()
    exclude = getattr(target, "EXTRACTION_EXCLUDE", ())
    if exclude:
        for name in exclude:
            schema.get("properties", {}).pop(name, None)
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r not in exclude]
    return schema


def _first_tool_input(message: Any, tool_name: str) -> dict[str, Any]:
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return cast("dict[str, Any]", block.input)
    raise ExtractionError(f"model did not call tool {tool_name!r}")


class StructuredExtractor:
    """Force a Claude model to populate a Pydantic schema from image + text.

    The Anthropic client is injectable so tests can run without network/keys.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        settings: Settings | None = None,
        client: Any | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.extract_model
        self.max_tokens = max_tokens
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.settings.anthropic_api_key or None)
        return self._client

    def extract(
        self,
        target: type[T],
        *,
        instructions: str,
        image_png: bytes | None = None,
        images: list[bytes] | None = None,
        context_text: str = "",
        tool_name: str = "record_extraction",
    ) -> T:
        """Return a validated ``target`` read from one or more page images + text.

        Pass a single page via ``image_png`` or multiple (document-level reads)
        via ``images``; both are sent in order ahead of the text block.
        """
        page_images = ([image_png] if image_png is not None else []) + (images or [])
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": _MEDIA_TYPE,
                    "data": base64.standard_b64encode(img).decode("ascii"),
                },
            }
            for img in page_images
        ]
        text = instructions + (_OCR_HINT_HEADER + context_text if context_text else "")
        content.append({"type": "text", "text": text})

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            tools=[
                {
                    "name": tool_name,
                    "description": f"Record the extracted {target.__name__} for this page.",
                    "input_schema": _tool_schema(target),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": content}],
        )
        result = target.model_validate(_first_tool_input(message, tool_name))
        log.info("extractor.extracted", model=self.model, target=target.__name__)
        return result

    def extract_from_text(
        self,
        target: type[T],
        *,
        instructions: str,
        text: str,
        tool_name: str = "record_extraction",
    ) -> T:
        """Force the model to populate ``target`` from a text document (no image).

        For already-clean text (e.g. extracted meeting minutes) rather than a page
        render — same forced-tool-use + schema-validation contract as :meth:`extract`.
        """
        content = [{"type": "text", "text": f"{instructions}\n\n--- Document text ---\n{text}"}]
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            tools=[
                {
                    "name": tool_name,
                    "description": f"Record the extracted {target.__name__}.",
                    "input_schema": _tool_schema(target),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": content}],
        )
        result = target.model_validate(_first_tool_input(message, tool_name))
        log.info("extractor.extracted_text", model=self.model, target=target.__name__)
        return result
