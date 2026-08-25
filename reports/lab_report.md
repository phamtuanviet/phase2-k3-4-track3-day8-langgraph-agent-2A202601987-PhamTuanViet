# Day 08 Lab Report

## 1. Team / student
- Name: Viet (Student)
- Repo/commit: phase2-k3-4-track3-day8-langgraph-agent
- Date: 2026-08-25

## 2. Architecture
Graph nodes (11): intake, classify, tool, evaluate, answer, clarify, risky_action, approval, retry, dead_letter, finalize.

**Fixed Edges:**
- START -> intake -> classify
- tool -> evaluate
- risky_action -> approval
- answer, clarify, dead_letter -> finalize -> END

**Conditional Edges (Routing):**
- **classify**: routes to `answer` (simple), `tool` (tool), `clarify` (missing_info), `risky_action` (risky), or `retry` (error).
- **evaluate**: routes to `retry` if needs_retry, else `answer`.
- **retry**: routes to `tool` if attempt < max_attempts, else `dead_letter`.
- **approval**: routes to `tool` if approved, else `clarify`.

## 3. State schema
| Field | Reducer | Why |
|---|---|---|
| `messages`, `events`, `tool_results`, `errors` | append | Keeps an audit trail of conversation, system events, tool outputs, and exceptions without losing history. |
| `route`, `risk_level`, `attempt`, `evaluation_result`, `approval`, `final_answer`, etc. | overwrite | These represent the *current* state of execution and are used for fast routing/decision-making. |

## 4. Scenario results
**Total Scenarios:** 7 | **Success Rate:** 100.00% | **Total Retries:** 0 | **Total Interrupts:** 6

| Scenario | Expected route | Actual route | Success | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | Yes | 0 | 0 |
| S02_tool | tool | tool | Yes | 0 | 0 |
| S03_missing | missing_info | missing_info | Yes | 0 | 0 |
| S04_risky | risky | risky | Yes | 0 | 3 |
| S05_error | error | error | Yes | 0 | 0 |
| S06_delete | risky | risky | Yes | 0 | 3 |
| S07_dead_letter | error | error | Yes | 0 | 0 |

## 5. Failure analysis
1. **Tool failure leading to bounded retry / dead-letter:**
   - **Starts at:** Tool encounters an error (e.g. timeout).
   - **Signals:** The `evaluate` node detects 'ERROR' in `tool_results[-1]` and sets `evaluation_result = 'needs_retry'`.
   - **Next graph step:** Routed to the `retry` node, which increments the `attempt` counter.
   - **Termination guarantee:** The routing function after `retry` checks if `attempt < max_attempts`. If limit is reached, it routes to `dead_letter` -> `finalize` -> `END`, preventing infinite loops.
   - **Limitations:** If the tool hangs indefinitely without timing out, the graph execution could stall. Timeouts must be implemented at the tool level.

2. **Risky action rejected:**
   - **Starts at:** LLM classifies user query as `risky` (e.g. 'Delete customer account').
   - **Signals:** Routed to `risky_action` then `approval`. If a human reviewer rejects it, `approval.approved` becomes `False`.
   - **Next graph step:** The approval router sees the rejection and routes to `clarify`.
   - **Termination guarantee:** The `clarify` node creates a pending question and routes to `finalize` -> `END`. The tool is completely bypassed, containing the residual risk.
   - **Limitations:** A real-world rejection might need to specify *why* it was rejected to the user via multi-turn conversation.

## 6. Persistence / recovery evidence
Implemented SQLite checkpointer (`SqliteSaver`) with WAL mode enabled (`PRAGMA journal_mode=WAL`). State is segmented per scenario by passing `{"configurable": {"thread_id": state["thread_id"]}}` to `graph.invoke()`. This creates `checkpoints.db` which stores all graph steps durably. If the process crashes during a long-running tool, invoking the graph again with the same `thread_id` will resume precisely from the last successful node without duplicating prior work.

## 7. Extension work
- **SQLite Persistence:** Successfully implemented `SqliteSaver` in `persistence.py` to persist graphs to disk.
- **Bounded Retry:** Successfully implemented the `attempt` counter loop that fails-closed to a `dead_letter` node.

## 8. Improvement plan
If I had one more day, I would prioritize **Productionizing Human-in-the-loop (HITL)**. Currently, the `approval_node` mocks a reviewer's decision. I would remove the mock and configure `interrupt_before=["approval"]` in the graph compiler. This would pause execution dynamically, wait for a real API/webhook callback to update the graph state with the human's verdict, and then safely resume.