"""
LangGraph ReACT agent with optional verifier loop.

Graph shape WITHOUT verifier (verifier_enabled=False):
  START → agent → (tool_calls?) → tools → agent → ... → END

Graph shape WITH verifier (verifier_enabled=True):
  START → agent → (tool_calls?) → tools → agent → ... → verifier → (good?) → END
                                                              ↓ (bad, max 1 retry)
                                                            agent (with feedback)

The verifier is a separate LLM call (cheap model, structured output) that
evaluates the agent's final answer for completeness and groundedness.
If it flags the answer as bad, it injects feedback as a HumanMessage and
sends the agent back to re-generate. Max 1 retry to cap latency.

Interview note: "This is a quality gate — same principle as a CI pipeline
gate or a load balancer health check. The verifier adds one LLM call of
latency (~200-400ms with gpt-4o-mini) but catches hallucinations and
incomplete answers before they reach the user."
"""
import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from app.agent.playbooks import get_playbook
from app.agent.tools.rag_retrieve import make_rag_tool
from app.agent.tools.web_search import make_web_search_tool
from app.services.memory import format_memory_context

logger = logging.getLogger(__name__)

# Max times the verifier can reject and loop back to the agent.
# 1 retry is the sweet spot: catches real issues without runaway loops.
_MAX_VERIFIER_RETRIES = 1


# --- Structured output schema for the verifier ---

class VerifierJudgment(BaseModel):
    """The verifier's structured assessment of the agent's answer."""
    verdict: Literal["good", "bad"] = Field(
        description="'good' if the answer is complete, relevant, and grounded. "
                    "'bad' if it is incomplete, off-topic, or likely hallucinated."
    )
    feedback: str = Field(
        description="If verdict is 'bad', explain what's wrong and what the agent "
                    "should fix. If 'good', leave empty."
    )


_VERIFIER_SYSTEM_PROMPT = """\
You are a quality-check verifier. You evaluate an AI assistant's answer to a user question.

Judge the answer on three criteria:
1. **Relevance** — Does the answer address the user's actual question?
2. **Completeness** — Does it cover the key points, or is it missing important information?
3. **Groundedness** — Is the answer based on retrieved context / tool results, or does it appear to hallucinate facts?

If the answer is acceptable on all three criteria, verdict = "good".
If it fails on ANY criterion, verdict = "bad" and provide specific feedback on what to fix.

Be pragmatic — don't reject answers for minor style issues. Only flag genuine quality problems."""


# --- Extended state to track verifier retries ---

class AgentState(MessagesState):
    verifier_retries: int


def build_agent(
    playbook_name: str,
    document_id: str | None = None,
    long_term_memory: list[dict] | None = None,
):
    """
    Compiles a LangGraph ReACT agent for the given playbook.

    If the playbook has verifier_enabled=True, a verifier node is added
    that checks the agent's final answer before passing to END.
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

    # Append long-term memory to the system prompt if available.
    memory_block = format_memory_context(long_term_memory or [])
    if memory_block:
        system_prompt = f"{system_prompt}\n\n{memory_block}"

    def agent_node(state: AgentState) -> dict:
        # Prepend the system prompt on every call so the persona is always in context.
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> Literal["tools", "verifier", "__end__"]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        # If verifier is enabled, route there instead of END.
        if playbook.verifier_enabled:
            return "verifier"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_edge("tools", "agent")

    if playbook.verifier_enabled:
        # --- Verifier node ---
        verifier_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        verifier_with_schema = verifier_model.with_structured_output(VerifierJudgment)

        def verifier_node(state: AgentState) -> dict:
            # Find the original user question (last HumanMessage before tool calls).
            user_question = ""
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_question = msg.content
                    break

            agent_answer = state["messages"][-1].content

            judgment: VerifierJudgment = verifier_with_schema.invoke([
                SystemMessage(content=_VERIFIER_SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"## User Question\n{user_question}\n\n"
                    f"## Agent Answer\n{agent_answer}"
                )),
            ])

            if judgment.verdict == "bad":
                logger.info("Verifier rejected answer: %s", judgment.feedback)
                return {
                    "messages": [HumanMessage(content=(
                        f"[VERIFIER FEEDBACK] Your previous answer was flagged as "
                        f"incomplete or incorrect. Please revise:\n{judgment.feedback}"
                    ))],
                    "verifier_retries": state.get("verifier_retries", 0) + 1,
                }

            # Good — pass through (no new messages needed).
            logger.info("Verifier approved answer")
            return {}

        def after_verifier(state: AgentState) -> Literal["agent", "__end__"]:
            # If the verifier just approved (no new messages added), we're done.
            last = state["messages"][-1]
            if isinstance(last, AIMessage):
                return END
            # If verifier injected feedback, check retry limit.
            retries = state.get("verifier_retries", 0)
            if retries > _MAX_VERIFIER_RETRIES:
                logger.warning("Verifier retry limit reached, passing through")
                return END
            return "agent"

        graph.add_node("verifier", verifier_node)
        graph.add_conditional_edges("agent", should_continue, ["tools", "verifier"])
        graph.add_conditional_edges("verifier", after_verifier, ["agent", END])
    else:
        graph.add_conditional_edges("agent", should_continue, ["tools", END])

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
