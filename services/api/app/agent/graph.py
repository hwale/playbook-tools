from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agent.playbooks import get_playbook
from app.agent.tools.rag_retrieve import make_rag_tool
from app.agent.tools.web_search import make_web_search_tool


def build_agent(playbook_name: str, document_id: str | None = None):
    """
    Compiles a LangGraph ReACT agent for the given playbook.

    create_react_agent builds a StateGraph with two nodes:
      - "agent": calls the LLM with the tool definitions attached
      - "tools": executes whatever tool calls the LLM requested, appends results

    Edges:
      agent → tools   (when the LLM response contains tool_calls)
      agent → END     (when no tool_calls — the LLM is done reasoning)
      tools → agent   (always — feed tool results back into the next LLM call)

    recursion_limit (set at invoke time) caps total node visits so a runaway
    agent doesn't loop forever on a bad prompt.
    """
    playbook = get_playbook(playbook_name)

    tools = []
    if "rag.retrieve" in playbook.tool_names and document_id:
        tools.append(make_rag_tool(document_id))
    if "web.search" in playbook.tool_names:
        tools.append(make_web_search_tool())

    model = ChatOpenAI(model=playbook.model, temperature=0)

    # state_modifier prepends the system prompt to the message list on every
    # agent node call — this is how LangGraph injects the persona/instructions.
    graph = create_react_agent(
        model=model,
        tools=tools,
        prompt=playbook.system_prompt,
    )
    return graph


async def run_agent(
    question: str,
    playbook_name: str = "game-design",
    document_id: str | None = None,
) -> dict:
    graph = build_agent(playbook_name, document_id)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": 20},
    )

    # The final answer is always the last message in the state.
    answer = result["messages"][-1].content

    # Collect tool call steps for transparency / debugging.
    steps = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                steps.append({"tool": tc["name"], "input": tc["args"]})

    return {"answer": answer, "steps": steps}
