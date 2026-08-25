# Báo cáo Lab 08

## 1. Thông tin sinh viên
- Họ và tên: Phạm Tuấn Việt
- MSSV: 2A202601987
- Repo/commit: phase2-k3-4-track3-day8-langgraph-agent
- Ngày: 2026-08-25

## 2. Kiến trúc
Graph nodes (11): intake, classify, tool, evaluate, answer, clarify, risky_action, approval, retry, dead_letter, finalize.

**Các cạnh cố định (Fixed Edges):**
- START -> intake -> classify
- tool -> evaluate
- risky_action -> approval
- answer, clarify, dead_letter -> finalize -> END

**Các cạnh có điều kiện (Conditional Edges - Routing):**
- **classify**: điều hướng đến `answer` (simple), `tool` (tool), `clarify` (missing_info), `risky_action` (risky), hoặc `retry` (error).
- **evaluate**: điều hướng đến `retry` nếu needs_retry, ngược lại đến `answer`.
- **retry**: điều hướng đến `tool` nếu attempt < max_attempts, ngược lại đến `dead_letter`.
- **approval**: điều hướng đến `tool` nếu được duyệt (approved), ngược lại đến `clarify`.

## 3. Schema trạng thái (State schema)
| Trường (Field) | Reducer | Lý do |
|---|---|---|
| `messages`, `events`, `tool_results`, `errors` | append | Lưu giữ vết kiểm toán (audit trail) của các đoạn hội thoại, sự kiện hệ thống, output của tool và lỗi mà không bị mất lịch sử. |
| `route`, `risk_level`, `attempt`, `evaluation_result`, `approval`, `final_answer`, v.v. | overwrite | Đại diện cho trạng thái *hiện tại* của execution và được dùng để ra quyết định / định tuyến (routing) nhanh chóng. |

## 4. Kết quả Scenario
**Tổng số Scenario:** 7 | **Tỷ lệ thành công:** 100.00% | **Tổng Retry:** 0 | **Tổng ngắt quãng (Interrupts):** 12

| Scenario | Route dự kiến | Route thực tế | Thành công | Retries | Interrupts |
|---|---|---|---:|---:|---:|
| S01_simple | simple | simple | Có | 0 | 0 |
| S02_tool | tool | tool | Có | 0 | 0 |
| S03_missing | missing_info | missing_info | Có | 0 | 0 |
| S04_risky | risky | risky | Có | 0 | 6 |
| S05_error | error | error | Có | 0 | 0 |
| S06_delete | risky | risky | Có | 0 | 6 |
| S07_dead_letter | error | error | Có | 0 | 0 |

## 5. Phân tích lỗi (Failure analysis)
1. **Lỗi Tool dẫn đến giới hạn retry / dead-letter:**
   - **Bắt đầu tại:** Tool gặp lỗi (ví dụ: timeout).
   - **Tín hiệu phát hiện:** Node `evaluate` đọc thấy chữ 'ERROR' trong `tool_results[-1]` và set `evaluation_result = 'needs_retry'`.
   - **Bước tiếp theo của Graph:** Chuyển hướng tới node `retry`, node này sẽ tăng biến đếm `attempt` lên 1.
   - **Đảm bảo kết thúc (Termination):** Routing function sau node `retry` sẽ kiểm tra `attempt < max_attempts`. Nếu chạm giới hạn, nó sẽ chuyển sang `dead_letter` -> `finalize` -> `END`, giúp tránh bị lặp vô hạn.
   - **Giới hạn (Limitations):** Nếu tool bị treo vô thời hạn mà không văng timeout, quá trình thực thi graph có thể bị kẹt. Cần phải cài đặt timeout ở tầng thực thi tool.

2. **Hành động rủi ro bị từ chối:**
   - **Bắt đầu tại:** LLM phân loại câu hỏi của người dùng là `risky` (ví dụ: 'Xoá tài khoản khách hàng').
   - **Tín hiệu phát hiện:** Điều hướng qua `risky_action` rồi đến `approval`. Nếu người duyệt từ chối, `approval.approved` sẽ trở thành `False`.
   - **Bước tiếp theo của Graph:** Node router tại approval nhận thấy bị từ chối và điều hướng sang `clarify`.
   - **Đảm bảo kết thúc (Termination):** Node `clarify` tạo ra một câu hỏi chờ phản hồi và điều hướng đến `finalize` -> `END`. Tool bị bypass hoàn toàn, giúp kiểm soát rủi ro triệt để.
   - **Giới hạn (Limitations):** Trong thực tế, việc từ chối có thể cần phải giải thích rõ *lý do* cho người dùng thông qua hội thoại đa lượt (multi-turn conversation).

## 6. Minh chứng Persistance / Recovery
Đã cài đặt SQLite checkpointer (`SqliteSaver`) và bật chế độ WAL (`PRAGMA journal_mode=WAL`). Trạng thái (state) được phân tách theo từng scenario thông qua việc truyền `{"configurable": {"thread_id": state["thread_id"]}}` vào `graph.invoke()`. Thao tác này tạo ra file `checkpoints.db` để lưu trữ bền vững tất cả các bước của đồ thị.
Nếu một tool chạy quá lâu khiến process bị crash, khi gọi lại graph với cùng `thread_id` đó, graph sẽ tiếp tục chạy từ đúng node thành công cuối cùng mà không bị lặp lại công việc trước đó.

**Minh chứng (Log Output):**
```bash
$ ls -lh checkpoints.db
-rw-r--r-- 1 viet viet 584K Aug 25 12:01 checkpoints.db
```
Việc có mặt file `checkpoints.db` khẳng định rằng state của graph đã được `SqliteSaver` ghi chép thành công xuống ổ đĩa.

## 7. Các tính năng mở rộng (Extension work)
- **SQLite Persistence:** Cài đặt thành công `SqliteSaver` trong `persistence.py` để lưu trạng thái đồ thị xuống ổ đĩa.
- **Bounded Retry:** Triển khai thành công bộ đếm `attempt` kèm vòng lặp fail-closed đi tới node `dead_letter`.

## 8. Kế hoạch cải tiến (Improvement plan)
Nếu có thêm thời gian, ưu tiên tiếp theo để đưa lên production sẽ là **Human-in-the-loop (HITL) thực sự**. Hiện tại, `approval_node` đang mock quyết định của người duyệt. Tôi sẽ gỡ bỏ mock và cấu hình `interrupt_before=["approval"]` trong phần biên dịch (compile) graph. Điều này sẽ tạm dừng luồng thực thi, chờ một callback API/webhook cập nhật quyết định của người thật vào graph state, và sau đó mới tiếp tục chạy.