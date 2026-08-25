"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

from .state import AgentState, make_event


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── TODO(student): implement ALL nodes below ────────────────────────


def classify_node(state: AgentState) -> dict:
    from pydantic import BaseModel, Field

    from .llm import get_llm

    class Classification(BaseModel):
        route: str = Field(description="Must be one of: simple, tool, missing_info, risky, error.")

    query = state.get("query", "")
    prompt = (
        "Classify the following user query into one of the following intents (routes):\n"
        "1. risky: Requires human approval or is dangerous. Examples: Refund money, delete account, destructive actions.\n"  # noqa: E501
        "2. tool: Requires calling a tool to fetch info or perform an action. Example: Lookup order status.\n"  # noqa: E501
        "3. missing_info: Vague or incomplete query needing clarification. Example: Can you fix it?\n"  # noqa: E501
        "4. error: A problem occurred or user explicitly asks for an error. Example: Timeout failure, system failure.\n"  # noqa: E501
        "5. simple: A simple greeting or question that needs no tools. Examples: How do I reset my password?, Hello.\n"  # noqa: E501
        "Priority guide: risky > tool > missing_info > error > simple.\n\n"
        f"Query: {query}"
    )

    try:
        decision = get_llm().with_structured_output(Classification).invoke(prompt)
        route = decision.route
        if route not in ["simple", "tool", "missing_info", "risky", "error"]:
            route = "simple"
    except Exception as e:
        return {
            "route": "error",
            "risk_level": "low",
            "errors": [f"LLM classification failed: {str(e)}"],
            "events": [make_event("classify", "failed", "Fallback to error due to exception")]
        }

    risk_level = "high" if route == "risky" else "low"
    return {
        "route": route,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route}, risk={risk_level}")]
    }


def tool_node(state: AgentState) -> dict:
    route = state.get("route", "")
    attempt = state.get("attempt", 0)

    if route == "error" and attempt < 2:
        result = "ERROR: Transient failure occurred during tool execution."
    else:
        result = "Success: Tool executed normally."

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"Executed mock tool (attempt {attempt})")]
    }


def evaluate_node(state: AgentState) -> dict:
    tool_results = state.get("tool_results", [])
    if not tool_results:
        result = "success"
    else:
        latest = tool_results[-1]
        if "ERROR" in latest:
            result = "needs_retry"
        else:
            result = "success"

    return {
        "evaluation_result": result,
        "events": [make_event("evaluate", "completed", f"Evaluation verdict: {result}")]
    }


def answer_node(state: AgentState) -> dict:
    from .llm import get_llm
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval", {})
    proposed_action = state.get("proposed_action", "")

    context = []
    if tool_results:
        context.append(f"Tool results: {tool_results[-1]}")
    if proposed_action:
        context.append(f"Proposed action: {proposed_action}")
    if approval:
        context.append(f"Approval status: {approval.get('approved')}, Reviewer: {approval.get('reviewer')}")  # noqa: E501

    prompt = (
        "Answer the user's query based strictly on the provided context.\n"
        "If the context is insufficient, explicitly state that.\n\n"
        f"Query: {query}\n"
        f"Context: {' | '.join(context)}\n"
    )

    try:
        response = get_llm().invoke(prompt).content
        return {
            "final_answer": str(response),
            "events": [make_event("answer", "completed", "Answer generated successfully")]
        }
    except Exception as e:
        return {
            "final_answer": "Sorry, an error occurred while generating the answer.",
            "errors": [f"LLM Error: {str(e)}"],
            "events": [make_event("answer", "failed", "Answer generation failed")]
        }


def ask_clarification_node(state: AgentState) -> dict:
    query = state.get("query", "")
    approval = state.get("approval", {})

    if approval and not approval.get("approved"):
        question = f"Your requested action was rejected (Reason: {approval.get('comment')}). What would you like to do instead?"  # noqa: E501
    else:
        question = f"Your query '{query}' is unclear. Could you provide more details?"

    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("ask_clarification", "completed", "Clarification requested")]
    }


def risky_action_node(state: AgentState) -> dict:
    query = state.get("query", "")
    risk_level = state.get("risk_level", "high")

    action = f"Execute side effect for query: '{query}' with risk level: {risk_level}"

    return {
        "proposed_action": action,
        "events": [make_event("risky_action", "completed", "Proposed risky action")]
    }


def approval_node(state: AgentState) -> dict:
    decision = {
        "approved": True,
        "reviewer": "mock-reviewer",
        "comment": "Auto-approved by default"
    }

    return {
        "approval": decision,
        "events": [make_event("approval", "completed", "Approval decision recorded")]
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    attempt = state.get("attempt", 0)
    new_attempt = attempt + 1

    tool_results = state.get("tool_results", [])
    error_msg = tool_results[-1] if tool_results else "Unknown error"

    return {
        "attempt": new_attempt,
        "errors": [f"Retry #{new_attempt} due to: {error_msg}"],
        "events": [make_event("retry_or_fallback", "completed", f"Retrying, attempt {new_attempt}")]
    }


def dead_letter_node(state: AgentState) -> dict:
    attempt = state.get("attempt", 0)

    msg = f"Failed to complete the request after {attempt} attempts."

    return {
        "final_answer": msg,
        "events": [make_event("dead_letter", "completed", "Exhausted retries")]
    }


def finalize_node(state: AgentState) -> dict:
    return {
        "events": [make_event("finalize", "completed", "workflow finished")]
    }
