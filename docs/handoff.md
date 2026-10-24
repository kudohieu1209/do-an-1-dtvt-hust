# Bàn giao Đồ án 1 — 24/10/2026

## Thầy có thể bắt đầu từ đâu?

1. Đọc [báo cáo tiến độ](report/MaiDuyHiếu.pdf) và [đối chiếu yêu cầu](theory/yeu_cau_cua_thay.md).
2. Làm theo [README gốc](../README.md) để cài đặt và chạy local. MongoDB bắt buộc
   cho ứng dụng; có thể tự đăng ký và nhập bảng điểm giả trong README.
3. Chạy `scripts/test_all.ps1` trên PowerShell hoặc `scripts/test_all.sh` trên
   Linux/macOS/Git Bash. Không cần file hồ sơ cá nhân, MongoDB thật hoặc API key.
4. Đọc [100 câu hồi quy](../project/eval/reports/handoff_20261024.md) và
   [20 câu diễn đạt bổ sung](../project/eval/reports/validation_handoff_20261024.md).

## Phạm vi đã triển khai

- Frontend React/Vite, FastAPI, MongoDB cho dữ liệu nghiệp vụ; Chroma chỉ cho RAG.
- CTĐT đã chuẩn hóa: ET1–2022/K67 và ET1–2023/K68. Danh mục 68 chương trình không
  đồng nghĩa đã hỗ trợ audit/chọn môn cho cả 68 chương trình.
- Đăng ký/đăng nhập/đổi mật khẩu, cookie HttpOnly, phân quyền hồ sơ và hội thoại.
- Nhập bảng điểm có xác nhận tín chỉ môn ngoài danh mục; cảnh báo/chuẩn đầu ra
  chưa biết được ghi rõ, không tự kết luận đã đạt.
- Rule Engine giữ nhánh AND/OR, audit và gợi ý theo phiên bản CTĐT.
- RAG chỉ nhận nguồn đã phê duyệt, truy xuất kết hợp từ khóa/vector và trả nguồn.
- Context hội thoại riêng theo tài khoản; memory bật/tắt/sửa/xóa do sinh viên quản lý.
- Giao diện trạng thái thiếu bảng điểm, mất kết nối và mốc tín chỉ; avatar mặc định
  dùng chữ viết tắt tên. Mốc tín chỉ không phải xác nhận tốt nghiệp.

## Giới hạn phải nêu khi báo cáo

- Kết quả tự động mặc định không gọi Gemini. Khớp ý chính không phải độ đúng toàn
  diện của câu trả lời; cần người chấm dẫn nguồn và kiểm định ngoài bộ hồi quy.
- Tập diễn đạt bổ sung còn trường hợp học phí tiến sĩ chưa đạt; không đổi đáp án
  hay hạ ngưỡng để làm đẹp chỉ số.
- Mục tiêu CPA được lưu và nhắc lại; chưa có planner nhiều kỳ hoặc bộ mô phỏng
  điểm theo mục tiêu. Chưa có LLM Tool Calling, smart alerts hay quản trị đầy đủ.
- Bản bàn giao chạy local; triển khai HTTPS, cookie/proxy production và kiểm thử
  tải/LLM thực tế là bước tiếp theo. Thầy có thể xem tiến độ trước khi có web live.

## Cách tái lập từ bản clone sạch

Các bộ kiểm thử dùng hồ sơ tổng hợp từ CTĐT công khai và `mongomock` trong bộ nhớ.
Ngày giờ TTL được cố định trong test tài khoản. Chỉ mục Chroma riêng cho mỗi tiến
trình, không dùng dữ liệu hay chỉ mục của backend đang chạy.

`test_all` dừng ngay nếu một bước thất bại: backend, pipeline dữ liệu, bộ đánh giá,
100 câu có ngưỡng, 20 câu bổ sung báo cáo riêng, frontend lint và build. Quy trình
GitHub Actions chạy từ checkout sạch trên Ubuntu; không cấp secrets MongoDB/Gemini.

Các báo cáo JSON/Markdown ghi nhãn lần chạy, chế độ, hash bộ câu hỏi và hash mã
nguồn/corpus/fixture. Baseline ngày 15/10 là kết quả lịch sử của 96 câu; không dùng
để tuyên bố kết quả của phiên bản bàn giao hiện tại.

## Tài liệu và dữ liệu riêng

`.env`, bảng điểm cá nhân, database cục bộ, thư mục sao lưu legacy và attachment
không đưa lên GitHub. `report/` là tài liệu thực tập kỹ thuật không thuộc ĐA1:
đã ngừng theo dõi Git nhưng vẫn giữ trên máy. Lịch sử Git cũ không được viết lại.
