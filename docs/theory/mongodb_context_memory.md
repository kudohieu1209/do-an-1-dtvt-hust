# MongoDB, conversation context và ghi nhớ học tập

Ngày kiểm tra: 23/10/2026. Đây là đợt triển khai nền tảng; Tool Calling, planner
nhiều kỳ, mô phỏng CPA theo mục tiêu và smart alerts chưa nằm trong đợt này.

## Dữ liệu nghiệp vụ

Backend chỉ dùng MongoDB cho tài khoản, phiên, hồ sơ, hội thoại, tin nhắn và
ghi nhớ. Thiếu `MONGODB_URI` hoặc kết nối thất bại sẽ dừng khởi động. Các lớp
SQLite và kho hồ sơ file đã được gỡ khỏi `app/`. Dataset CTĐT và nguồn RAG vẫn
được quản lý bằng file có phiên bản; ChromaDB vẫn giữ SQLite nội bộ của nó.

`migrate_to_mongodb.py` dùng bộ đọc legacy tách khỏi runtime:

- `--dry-run`: đếm nguồn, không kết nối MongoDB.
- `--check`: đối chiếu, không ghi MongoDB.
- Import: chỉ bổ sung bản ghi thiếu, giữ bản MongoDB khi khác biệt, không
  chuyển phiên đăng nhập; từ chối xung đột khác chủ sở hữu trước khi ghi.
- Giữ hash mật khẩu tài khoản legacy, cấp lại ID tin nhắn nếu trùng số, dùng
  dấu migration và kiểm tra bản nhập trước đó để chạy lại không nhân đôi.

Đối chiếu thực tế: 8 hồ sơ, 10 hội thoại và 42 tin nhắn legacy đều đã có trên
MongoDB; không cần bổ sung bản ghi. Giữ nguyên một hồ sơ và một hội thoại có
khác biệt trên MongoDB. Backend sau chuyển đổi khởi động thành công, kho đích
còn 8 tài khoản, 8 hồ sơ, 17 hội thoại và 92 tin nhắn.

Nguồn cục bộ được chuyển vào `project/data/legacy_backup/2026-10-23-mongodb/`
(đã ignore Git), gồm database, WAL/SHM và thư mục `students/`. Kiểm tra hash
khi chuyển; đối chiếu lại từ chính bản sao lưu vẫn không thiếu bản ghi.
Không xóa dữ liệu nguồn. Đối chiếu lại từ thư mục gốc repository:

```powershell
& project/backend/.venv-win/Scripts/python.exe project/backend/migrate_to_mongodb.py --source project/data/legacy_backup/2026-10-23-mongodb --check
```

## Conversation context

API chỉ dùng lịch sử đã lưu của hội thoại thuộc tài khoản đăng nhập. Trường
`history` cũ của client không thiết lập context; frontend cũng đã ngừng gửi nó.
Truy vấn MongoDB chỉ lấy 12 tin gần nhất, có thứ tự ổn định. Assistant lưu một
context ngắn trong `data_context.conversation_context`, giúp giữ chủ đề qua
câu cảm ơn hoặc tải lại trang mà không cần biến trạng thái dùng chung.

Các trường hợp đã kiểm tra:

- “Điều kiện ET3300?” → “Nếu trượt thì sao?” dùng đúng ET3300.
- “Môn đó cần gì?” giữ học phần trong câu hỏi, không lấy nhầm mã môn tiên quyết
  xuất hiện trong câu trả lời.
- Hai môn rồi hỏi “môn đó” thì yêu cầu làm rõ; “cả hai môn đó” kiểm tra cả hai.
- “Còn kỳ hè thì sao?” giữ chủ đề hạn mức tín chỉ từ câu hỏi trước.
- Môn mới nêu rõ thay môn cũ; hội thoại/tài khoản khác không kế thừa context.

Đây là bộ phân giải tham chiếu có quy tắc, chưa phải mô hình hiểu mọi dạng
hội thoại dài. Không suy diễn điểm hoặc sửa hồ sơ từ lời trò chuyện.

## Ghi nhớ do sinh viên quản lý

Mở **Cài đặt → Ghi nhớ học tập**. Dữ liệu mặc định tắt; sinh viên tự bật, sửa,
tắt hoặc xóa qua API `GET`, `PUT`, `DELETE /api/student/memory`.

Lưu định hướng, mức tín chỉ mong muốn và mục tiêu CPA tại `student_memory`,
gắn với tài khoản và phiên bản CTĐT. CTĐT thay đổi thì bản nhớ cũ không được
áp dụng. Payload không được chứa MSSV, điểm hay các trường tùy ý.

Gợi ý môn ở chat mới dùng định hướng và tải tín chỉ đã lưu. Lựa chọn trong câu
hỏi hiện tại được ưu tiên; Rule Engine vẫn kiểm tra điều kiện và hạn mức học
vụ theo hồ sơ hiện tại. Mục tiêu CPA hiện chỉ lưu và nhắc lại rõ ràng, chưa có
tính toán đảm bảo danh sách môn sẽ đạt CPA mong muốn. Xóa ghi nhớ dừng áp dụng
cho gợi ý mới; không sửa nội dung những câu trả lời đã lưu trước đó.

## Kiểm chứng

- 181 kiểm thử backend, 17 dữ liệu và 19 bộ đánh giá đều đạt (217 tổng cộng).
  Các contract test chỉ dành cho SQLite đã bỏ cùng implementation SQLite.
- Kiểm thử dùng MongoDB giả lập trong bộ nhớ và bảng điểm tổng hợp từ CTĐT
  công khai. Không đọc bảng điểm cá nhân hoặc ghi vào MongoDB thật.
- Chỉ mục Chroma test/eval mặc định riêng cho mỗi tiến trình, tránh dùng lại
  HNSW hỏng giữa các lần chạy trên Windows. Không sửa chỉ mục ứng dụng.
- Frontend lint và production build đạt. Chưa xác minh trực quan mục mới do
  công cụ trình duyệt từ chối truy cập tab thử nghiệm theo chính sách URL.
- Bộ 100 câu gốc: intent/entity/Recall@4/khớp ý chính đạt 100%, MRR 80,7%,
  trung vị 215 ms. Đây là chế độ trích dẫn cục bộ, không gọi LLM thật.
- Bộ 20 câu bổ sung: Recall@4 93,3%, khớp ý chính 92,9%; vẫn còn câu `val-010`
  về cách diễn đạt học phí tiến sĩ không đạt. Không hạ ngưỡng hay đổi bộ gốc.

Báo cáo: `project/eval/reports/mongo_context_memory.{json,md}` và
`project/eval/reports/validation_mongo_context_memory.{json,md}`; có hash mã
nguồn/corpus/fixture và hash bộ câu hỏi để đối chiếu lần chạy.

## Bước phát triển kế tiếp

Tách các thao tác học vụ hiện có thành công cụ chỉ đọc với schema tham số,
kiểm tra quyền theo phiên đăng nhập và dấu vết thực thi. Sau đó mới cho mô
hình phối hợp các công cụ; điều kiện học phần và phép tính vẫn thuộc engine.
Các bước tiếp theo là đánh giá chất lượng nguồn, planner/CPA và feedback/admin/
alerts theo lộ trình đã thống nhất.
