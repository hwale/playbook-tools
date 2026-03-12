from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode

from app.agent.playbooks import get_playbook
from app.agent.tools.rag_retrieve import make_rag_tool
from app.agent.tools.web_search import make_web_search_tool


def build_agent(playbook_name: str, document_id: str | None = None):
    """
    Compiles a LangGraph ReACT agent for the given playbook using a manual
    StateGraph instead of create_react_agent.

    Why manual StateGraph instead of create_react_agent:
      create_react_agent produces a fixed 2-node graph (agent ↔ tools) that
      cannot be extended without a full rewrite. Building it manually is ~10
      extra lines but unlocks inserting new nodes (router, planner, verifier)
      later without changing the surrounding structure.

    Graph shape (identical behavior to create_react_agent for now):
      START → agent → (tool_calls?) → tools → agent → ... → END

    Nodes:
      "agent" — calls the LLM with tool definitions and the system prompt
      "tools" — executes all tool calls in the last LLM message, appends results

    Edges:
      agent → tools   (when LLM response contains tool_calls)
      agent → END     (when no tool_calls — reasoning is complete)
      tools → agent   (always — feed results back for the next reasoning step)

    recursion_limit (set at invoke time) caps total node visits so a runaway
    loop on a bad prompt doesn't spin forever.
    """
    playbook = get_playbook(playbook_name)

    tools = []
    if "rag.retrieve" in playbook.tool_names and document_id:
        tools.append(make_rag_tool(document_id, playbook.document_description))
    if "web.search" in playbook.tool_names:
        tools.append(make_web_search_tool())
    if "pdf.parse" in playbook.tool_names and document_id:
        from app.agent.tools.pdf_parse import make_pdf_parse_tool
        tools.append(make_pdf_parse_tool(document_id))

    model = ChatOpenAI(model=playbook.model, temperature=0)
    model_with_tools = model.bind_tools(tools)
    system_prompt = playbook.system_prompt

    def agent_node(state: MessagesState) -> dict:
        # Prepend the system prompt on every call so the persona is always in context.
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph.compile()


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
