from pydantic import BaseModel
from typing import List, Literal, Optional


class PlaybookSpecV1(BaseModel):
    """
    A playbook bundles everything needed to run an agent:
    a system prompt (the agent's mission) and the list of tools it can use.

    Keeping the playbook separate from the agent executor means you can swap
    the playbook without changing any infrastructure — different game, different
    system prompt, same ReACT loop.
    """
    version: Literal["v1"] = "v1"
    name: str
    description: Optional[str] = None
    system_prompt: str
    tool_names: List[str]   # references to tools in the agent's tool registry
    model: str = "gpt-4o-mini"
    # Used to generate the rag_retrieve tool's description at runtime so the LLM
    # knows what kind of document it is searching (GDD, legal brief, financial report, etc.)
    document_description: str = "the uploaded document"
