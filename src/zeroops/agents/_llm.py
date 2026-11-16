"""Shared LLM call utilities for agent nodes.

run_as_json() / run_as_json_list() bypass PydanticAI structured output
(tool calling) which is unreliable on small local models. Instead:
  1. Tell the model to return raw JSON in the system prompt
  2. Get plain text back (output_type=str)
  3. Extract the JSON block from the response
  4. Validate with Pydantic (which runs the enum unwrapping validator)
"""

import json
import re
from typing import TypeVar, Type, Optional

from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent

T = TypeVar("T", bound=BaseModel)


def _extract_json(text: str) -> Optional[str]:
    """Extract the first JSON object from text, handling markdown code blocks."""
    code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block:
        return code_block.group(1)
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, c in enumerate(text[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_array(text: str) -> Optional[str]:
    """Extract the first JSON array from text."""
    code_block = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if code_block:
        return code_block.group(1)
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    for i, c in enumerate(text[start:], start):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


async def run_as_json(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    output_class: Type[T],
) -> T:
    """Call LLM with output_type=str, extract JSON, validate as a Pydantic model.

    Retries once with a repair prompt on parse/validation failure.
    """
    schema_str = json.dumps(output_class.model_json_schema(), indent=2)

    full_system = (
        f"{system_prompt}\n\n"
        "Return a single valid JSON object and NOTHING else — no explanation, "
        "no markdown fencing, no text before or after the JSON.\n\n"
        f"JSON schema:\n{schema_str}\n\n"
        "IMPORTANT: For enum/Literal fields return the plain string value. "
        'Write "classification": "novel" — NOT "classification": {"enum": ["novel"]}.'
    )

    agent = Agent(model_id, output_type=str, system_prompt=full_system)

    async def _parse(prompt: str) -> T:
        result = await agent.run(prompt)
        text = result.output.strip()
        json_text = _extract_json(text)
        if not json_text:
            raise ValueError(f"No JSON object found in response:\n{text[:300]}")
        try:
            return output_class.model_validate_json(json_text)
        except (ValidationError, json.JSONDecodeError):
            return output_class.model_validate(json.loads(json_text))

    try:
        return await _parse(user_prompt)
    except (ValidationError, ValueError, json.JSONDecodeError) as first_error:
        repair = (
            f"Your previous response was invalid. Return ONLY a JSON object "
            f"matching the schema. No text before or after.\n"
            f"Error: {first_error}\n\n"
            f"Original request:\n{user_prompt}"
        )
        return await _parse(repair)


async def run_as_json_list(
    model_id: str,
    system_prompt: str,
    user_prompt: str,
    item_class: Type[T],
) -> list[T]:
    """Call LLM and validate response as a JSON array of Pydantic models.

    Returns empty list on persistent failure (acceptable for prevention tickets).
    """
    schema_str = json.dumps(item_class.model_json_schema(), indent=2)

    full_system = (
        f"{system_prompt}\n\n"
        "Return a valid JSON array and NOTHING else. Return [] if there are no items.\n\n"
        f"Each element must match this schema:\n{schema_str}\n\n"
        "IMPORTANT: For enum/Literal fields return the plain string value."
    )

    agent = Agent(model_id, output_type=str, system_prompt=full_system)

    async def _parse(prompt: str) -> list[T]:
        result = await agent.run(prompt)
        text = result.output.strip()
        json_text = _extract_json_array(text)
        if not json_text:
            # Model may have wrapped the array: {"tickets": [...]}
            obj_text = _extract_json(text)
            if obj_text:
                obj = json.loads(obj_text)
                for v in obj.values():
                    if isinstance(v, list):
                        json_text = json.dumps(v)
                        break
        if not json_text:
            return []
        items = json.loads(json_text)
        if not isinstance(items, list):
            return []
        return [item_class.model_validate(item) for item in items]

    try:
        return await _parse(user_prompt)
    except Exception as first_error:
        repair = (
            f"Your previous response was invalid. Return ONLY a JSON array. "
            f"Error: {first_error}\n\nOriginal request:\n{user_prompt}"
        )
        try:
            return await _parse(repair)
        except Exception:
            return []
