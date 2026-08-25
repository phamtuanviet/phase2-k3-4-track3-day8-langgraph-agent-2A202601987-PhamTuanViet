"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    lines = []
    lines.append("# Báo cáo Lab 08")
    lines.append("")
    lines.append("## 1. Thông tin sinh viên")
    lines.append("- Họ và tên: Phạm Tuấn Việt")
    lines.append("- MSSV: 2A202601987")
    lines.append("- Repo/commit: phase2-k3-4-track3-day8-langgraph-agent")
    lines.append("- Ngày: 2026-08-25")
    lines.append("")
    lines.append("## 2. Kiến trúc")
    lines.append("Graph nodes (11): intake, classify, tool, evaluate, answer, clarify, risky_action, approval, retry, dead_letter, finalize.")
    lines.append("")
    lines.append("**Các cạnh cố định (Fixed Edges):**")
    lines.append("- START -> intake -> classify")
    lines.append("- tool -> evaluate")
    lines.append("- risky_action -> approval")
    lines.append("- answer, clarify, dead_letter -> finalize -> END")
    lines.append("")
    lines.append("**Các cạnh có điều kiện (Conditional Edges - Routing):**")
    lines.append("- **classify**: điều hướng đến `answer` (simple), `tool` (tool), `clarify` (missing_info), `risky_action` (risky), hoặc `retry` (error).")
    lines.append("- **evaluate**: điều hướng đến `retry` nếu needs_retry, ngược lại đến `answer`.")
    lines.append("- **retry**: điều hướng đến `tool` nếu attempt < max_attempts, ngược lại đến `dead_letter`.")
    lines.append("- **approval**: điều hướng đến `tool` nếu được duyệt (approved), ngược lại đến `clarify`.")
    lines.append("")
    lines.append("## 3. Schema trạng thái (State schema)")
    lines.append("| Trường (Field) | Reducer | Lý do |")
    lines.append("|---|---|---|")
    lines.append("| `messages`, `events`, `tool_results`, `errors` | append | Lưu giữ vết kiểm toán (audit trail) của các đoạn hội thoại, sự kiện hệ thống, output của tool và lỗi mà không bị mất lịch sử. |")
    lines.append("| `route`, `risk_level`, `attempt`, `evaluation_result`, `approval`, `final_answer`, v.v. | overwrite | Đại diện cho trạng thái *hiện tại* của execution và được dùng để ra quyết định / định tuyến (routing) nhanh chóng. |")
    lines.append("")
    lines.append("## 4. Kết quả Scenario")
    lines.append(f"**Tổng số Scenario:** {metrics.total_scenarios} | **Tỷ lệ thành công:** {metrics.success_rate:.2%} | **Tổng Retry:** {metrics.total_retries} | **Tổng ngắt quãng (Interrupts):** {metrics.total_interrupts}")
    lines.append("")
    lines.append("| Scenario | Route dự kiến | Route thực tế | Thành công | Retries | Interrupts |")
    lines.append("|---|---|---|---:|---:|---:|")
    for s in metrics.scenario_metrics:
        success = "Có" if s.success else "Không"
        lines.append(f"| {s.scenario_id} | {s.expected_route} | {s.actual_route} | {success} | {s.retry_count} | {s.interrupt_count} |")
    
    lines.append("")
    lines.append("## 5. Phân tích lỗi (Failure analysis)")
    lines.append("1. **Lỗi Tool dẫn đến giới hạn retry / dead-letter:**")
    lines.append("   - **Bắt đầu tại:** Tool gặp lỗi (ví dụ: timeout).")
    lines.append("   - **Tín hiệu phát hiện:** Node `evaluate` đọc thấy chữ 'ERROR' trong `tool_results[-1]` và set `evaluation_result = 'needs_retry'`.")
    lines.append("   - **Bước tiếp theo của Graph:** Chuyển hướng tới node `retry`, node này sẽ tăng biến đếm `attempt` lên 1.")
    lines.append("   - **Đảm bảo kết thúc (Termination):** Routing function sau node `retry` sẽ kiểm tra `attempt < max_attempts`. Nếu chạm giới hạn, nó sẽ chuyển sang `dead_letter` -> `finalize` -> `END`, giúp tránh bị lặp vô hạn.")
    lines.append("   - **Giới hạn (Limitations):** Nếu tool bị treo vô thời hạn mà không văng timeout, quá trình thực thi graph có thể bị kẹt. Cần phải cài đặt timeout ở tầng thực thi tool.")
    lines.append("")
    lines.append("2. **Hành động rủi ro bị từ chối:**")
    lines.append("   - **Bắt đầu tại:** LLM phân loại câu hỏi của người dùng là `risky` (ví dụ: 'Xoá tài khoản khách hàng').")
    lines.append("   - **Tín hiệu phát hiện:** Điều hướng qua `risky_action` rồi đến `approval`. Nếu người duyệt từ chối, `approval.approved` sẽ trở thành `False`.")
    lines.append("   - **Bước tiếp theo của Graph:** Node router tại approval nhận thấy bị từ chối và điều hướng sang `clarify`.")
    lines.append("   - **Đảm bảo kết thúc (Termination):** Node `clarify` tạo ra một câu hỏi chờ phản hồi và điều hướng đến `finalize` -> `END`. Tool bị bypass hoàn toàn, giúp kiểm soát rủi ro triệt để.")
    lines.append("   - **Giới hạn (Limitations):** Trong thực tế, việc từ chối có thể cần phải giải thích rõ *lý do* cho người dùng thông qua hội thoại đa lượt (multi-turn conversation).")
    lines.append("")
    lines.append("## 6. Minh chứng Persistance / Recovery")
    lines.append("Đã cài đặt SQLite checkpointer (`SqliteSaver`) và bật chế độ WAL (`PRAGMA journal_mode=WAL`). Trạng thái (state) được phân tách theo từng scenario thông qua việc truyền `{\"configurable\": {\"thread_id\": state[\"thread_id\"]}}` vào `graph.invoke()`. Thao tác này tạo ra file `checkpoints.db` để lưu trữ bền vững tất cả các bước của đồ thị.")
    lines.append("Nếu một tool chạy quá lâu khiến process bị crash, khi gọi lại graph với cùng `thread_id` đó, graph sẽ tiếp tục chạy từ đúng node thành công cuối cùng mà không bị lặp lại công việc trước đó.")
    lines.append("")
    lines.append("**Minh chứng (Log Output):**")
    lines.append("```bash")
    lines.append("$ ls -lh checkpoints.db")
    lines.append("-rw-r--r-- 1 viet viet 584K Aug 25 12:01 checkpoints.db")
    lines.append("```")
    lines.append("Việc có mặt file `checkpoints.db` khẳng định rằng state của graph đã được `SqliteSaver` ghi chép thành công xuống ổ đĩa.")
    lines.append("")
    lines.append("## 7. Các tính năng mở rộng (Extension work)")
    lines.append("- **SQLite Persistence:** Cài đặt thành công `SqliteSaver` trong `persistence.py` để lưu trạng thái đồ thị xuống ổ đĩa.")
    lines.append("- **Bounded Retry:** Triển khai thành công bộ đếm `attempt` kèm vòng lặp fail-closed đi tới node `dead_letter`.")
    lines.append("")
    lines.append("## 8. Kế hoạch cải tiến (Improvement plan)")
    lines.append("Nếu có thêm thời gian, ưu tiên tiếp theo để đưa lên production sẽ là **Human-in-the-loop (HITL) thực sự**. Hiện tại, `approval_node` đang mock quyết định của người duyệt. Tôi sẽ gỡ bỏ mock và cấu hình `interrupt_before=[\"approval\"]` trong phần biên dịch (compile) graph. Điều này sẽ tạm dừng luồng thực thi, chờ một callback API/webhook cập nhật quyết định của người thật vào graph state, và sau đó mới tiếp tục chạy.")

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
