from pydantic import BaseModel, Field
from typing import Any, Dict, Literal

JsonSchema = Dict[str, Any]

class ToolSpecV1(BaseModel):
    """Contract describing a single deterministic tool."""
    version: Literal["v1"] = "v1"
    name: str = Field(..., pattern=r"^[a-z]+(\.[a-z_]+)+$")  # e.g. rag.retrieve
    description: str
    input_schema: JsonSchema
    output_schema: JsonSchema