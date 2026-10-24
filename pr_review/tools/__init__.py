"""Tool schemas and handlers for each phase, with their budgets."""

from typing import Any


def function_schema(
    name: str,
    description: str,
    properties: dict[str, Any] | None = None,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    """An OpenAI-style function tool schema."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": list(required),
            },
        },
    }


def tool_names(schemas: list[dict[str, Any]]) -> set[str]:
    return {schema["function"]["name"] for schema in schemas}
