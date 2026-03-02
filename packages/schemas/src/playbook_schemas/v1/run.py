from pydantic import BaseModel
from typing import Any, Dict, Literal, Optional, List

class StepRecordV1(BaseModel):
    version: Literal["v1"] = "v1"
    step_id: str
    tool: str
    status: str
    started_at: str
    ended_at: str
    input: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

class RunRecordV1(BaseModel):
    version: Literal["v1"] = "v1"
    run_id: str
    workflow_name: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    state: Dict[str, Any]
    steps: List[StepRecordV1]

class FinalOutputV1(BaseModel):
    version: Literal["v1"] = "v1"
    run_id: str
    result: Dict[str, Any]