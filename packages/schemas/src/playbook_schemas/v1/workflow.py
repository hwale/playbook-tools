from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional

class WorkflowStepV1(BaseModel):
    id: str = Field(..., pattern=r"^[a-z0-9_]+$")
    tool: str = Field(..., description="Tool name from registry, e.g. rag.retrieve")
    input: Dict[str, Any] = Field(default_factory=dict)
    save_as: Optional[str] = Field(
        default=None,
        description="If provided, store tool output in run state under this key",
    )

class WorkflowSpecV1(BaseModel):
    """Linear workflow definition."""
    version: Literal["v1"] = "v1"
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStepV1]