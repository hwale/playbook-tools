from fastapi import APIRouter

from playbook_schemas.v1.workflow import WorkflowSpecV1
from playbook_schemas.v1.tool import ToolSpecV1
from playbook_schemas.v1.run import RunRecordV1, StepRecordV1, FinalOutputV1

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("/v1")
def get_schemas_v1():
    return {
        "WorkflowSpecV1": WorkflowSpecV1.model_json_schema(),
        "ToolSpecV1": ToolSpecV1.model_json_schema(),
        "RunRecordV1": RunRecordV1.model_json_schema(),
        "StepRecordV1": StepRecordV1.model_json_schema(),
        "FinalOutputV1": FinalOutputV1.model_json_schema(),
    }