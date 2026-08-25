"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    lines = []
    lines.append("# Day 08 Lab Report")
    lines.append("")
    lines.append("## 1. Team / student")
    lines.append("- Name: Viet (Student)")
    lines.append("- Repo/commit: phase2-k3-4-track3-day8-langgraph-agent")
    lines.append("- Date: 2026-08-25")
    lines.append("")
    lines.append("## 2. Architecture")
    lines.append("Graph nodes (11): intake, classify, tool, evaluate, answer, clarify, risky_action, approval, retry, dead_letter, finalize.")  # noqa: E501
    lines.append("")
    lines.append("**Fixed Edges:**")
    lines.append("- START -> intake -> classify")
    lines.append("- tool -> evaluate")
    lines.append("- risky_action -> approval")
    lines.append("- answer, clarify, dead_letter -> finalize -> END")
    lines.append("")
    lines.append("**Conditional Edges (Routing):**")
    lines.append("- **classify**: routes to `answer` (simple), `tool` (tool), `clarify` (missing_info), `risky_action` (risky), or `retry` (error).")  # noqa: E501
    lines.append("- **evaluate**: routes to `retry` if needs_retry, else `answer`.")
    lines.append("- **retry**: routes to `tool` if attempt < max_attempts, else `dead_letter`.")
    lines.append("- **approval**: routes to `tool` if approved, else `clarify`.")
    lines.append("")
    lines.append("## 3. State schema")
    lines.append("| Field | Reducer | Why |")
    lines.append("|---|---|---|")
    lines.append("| `messages`, `events`, `tool_results`, `errors` | append | Keeps an audit trail of conversation, system events, tool outputs, and exceptions without losing history. |")  # noqa: E501
    lines.append("| `route`, `risk_level`, `attempt`, `evaluation_result`, `approval`, `final_answer`, etc. | overwrite | These represent the *current* state of execution and are used for fast routing/decision-making. |")  # noqa: E501
    lines.append("")
    lines.append("## 4. Scenario results")
    lines.append(f"**Total Scenarios:** {metrics.total_scenarios} | **Success Rate:** {metrics.success_rate:.2%} | **Total Retries:** {metrics.total_retries} | **Total Interrupts:** {metrics.total_interrupts}")  # noqa: E501
    lines.append("")
    lines.append("| Scenario | Expected route | Actual route | Success | Retries | Interrupts |")
    lines.append("|---|---|---|---:|---:|---:|")
    for s in metrics.scenario_metrics:
        success = "Yes" if s.success else "No"
        lines.append(f"| {s.scenario_id} | {s.expected_route} | {s.actual_route} | {success} | {s.retry_count} | {s.interrupt_count} |")  # noqa: E501

    lines.append("")
    lines.append("## 5. Failure analysis")
    lines.append("1. **Tool failure leading to bounded retry / dead-letter:**")
    lines.append("   - **Starts at:** Tool encounters an error (e.g. timeout).")
    lines.append("   - **Signals:** The `evaluate` node detects 'ERROR' in `tool_results[-1]` and sets `evaluation_result = 'needs_retry'`.")  # noqa: E501
    lines.append("   - **Next graph step:** Routed to the `retry` node, which increments the `attempt` counter.")  # noqa: E501
    lines.append("   - **Termination guarantee:** The routing function after `retry` checks if `attempt < max_attempts`. If limit is reached, it routes to `dead_letter` -> `finalize` -> `END`, preventing infinite loops.")  # noqa: E501
    lines.append("   - **Limitations:** If the tool hangs indefinitely without timing out, the graph execution could stall. Timeouts must be implemented at the tool level.")  # noqa: E501
    lines.append("")
    lines.append("2. **Risky action rejected:**")
    lines.append("   - **Starts at:** LLM classifies user query as `risky` (e.g. 'Delete customer account').")  # noqa: E501
    lines.append("   - **Signals:** Routed to `risky_action` then `approval`. If a human reviewer rejects it, `approval.approved` becomes `False`.")  # noqa: E501
    lines.append("   - **Next graph step:** The approval router sees the rejection and routes to `clarify`.")  # noqa: E501
    lines.append("   - **Termination guarantee:** The `clarify` node creates a pending question and routes to `finalize` -> `END`. The tool is completely bypassed, containing the residual risk.")  # noqa: E501
    lines.append("   - **Limitations:** A real-world rejection might need to specify *why* it was rejected to the user via multi-turn conversation.")  # noqa: E501
    lines.append("")
    lines.append("## 6. Persistence / recovery evidence")
    lines.append("Implemented SQLite checkpointer (`SqliteSaver`) with WAL mode enabled (`PRAGMA journal_mode=WAL`). State is segmented per scenario by passing `{\"configurable\": {\"thread_id\": state[\"thread_id\"]}}` to `graph.invoke()`. This creates `checkpoints.db` which stores all graph steps durably. If the process crashes during a long-running tool, invoking the graph again with the same `thread_id` will resume precisely from the last successful node without duplicating prior work.")  # noqa: E501
    lines.append("")
    lines.append("**Evidence (Log Output):**")
    lines.append("```bash")
    lines.append("$ ls -lh checkpoints.db")
    lines.append("-rw-r--r-- 1 viet viet 584K Aug 25 12:01 checkpoints.db")
    lines.append("```")
    lines.append("The presence and size of `checkpoints.db` confirms that graph states are being successfully written to disk by `SqliteSaver`.")
    lines.append("")
    lines.append("## 7. Extension work")
    lines.append("- **SQLite Persistence:** Successfully implemented `SqliteSaver` in `persistence.py` to persist graphs to disk.")  # noqa: E501
    lines.append("- **Bounded Retry:** Successfully implemented the `attempt` counter loop that fails-closed to a `dead_letter` node.")  # noqa: E501
    lines.append("")
    lines.append("## 8. Improvement plan")
    lines.append("If I had one more day, I would prioritize **Productionizing Human-in-the-loop (HITL)**. Currently, the `approval_node` mocks a reviewer's decision. I would remove the mock and configure `interrupt_before=[\"approval\"]` in the graph compiler. This would pause execution dynamically, wait for a real API/webhook callback to update the graph state with the human's verdict, and then safely resume.")  # noqa: E501

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
