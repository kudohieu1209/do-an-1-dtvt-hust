# Cải thiện độ tin cậy — 23/10/2026

## Phạm vi đã triển khai

- Đăng ký: truyền IP thực tế từ ASGI request tới giới hạn lượt đăng ký; trả HTTP 429 và `Retry-After`. Header chuyển tiếp chỉ được xử lý bởi cấu hình proxy tin cậy của server.
- Nhập bảng điểm: học phần ngoài danh mục phải có số tín chỉ do sinh viên xác nhận; trả `needs_confirmation` và không ghi một phần bảng điểm trước khi đủ dữ liệu. Giá trị âm/không hữu hạn bị từ chối, số tín chỉ 0 không bị đổi thành 3. Điểm chữ phải nằm cuối dòng để tránh đọc chữ C trong tên môn thành điểm khi phía sau vẫn còn cột tín chỉ.
- Cảnh báo: `warning_level: null` và `warning_status: unverified` khi thiếu căn cứ, thay cho kết luận mức 0. Kế hoạch tạm giới hạn 14 TC/kỳ chính và ghi rõ tính tạm thời. Sinh viên có thể cập nhật hoặc xóa mức khai báo trong hộp nhập bảng điểm.
- Tốt nghiệp: mỗi yêu cầu Ngoại ngữ/GDTC/GDQP có trạng thái `completed`, `incomplete`, `unverified`; cùng áp dụng cho ET1–2022 và ET1–2023 dù mã nhóm nguồn khác nhau. Trạng thái hoàn thành là khai báo của sinh viên theo CTT, không thay xác nhận của nhà trường.
- Tín chỉ tiến độ: giới hạn theo yêu cầu từng nhóm và một phương án mô-đun; tín chỉ tự chọn vượt mức không bù phần bắt buộc còn thiếu.
- Mục tiêu CPA: phân biệt đã đạt, có thể đạt bằng phần còn lại và cần học cải thiện. Khi không còn tín chỉ và CPA dưới mục tiêu, không trả GPA cần đạt bằng 0 rồi kết luận có thể đạt. Kiểm tra khả thi dùng giá trị chưa làm tròn; GPA hiển thị được làm tròn lên để không đánh giá thiếu mức cần đạt.
- RAG: chỉ nạp nguồn được phê duyệt, giữ ngữ cảnh trang/điều/khoản khi chia đoạn; kết hợp BM25 có cụm từ với vector search; ưu tiên đúng phiên bản CTĐT; bỏ phần mục lục và lời giới thiệu không mang nội dung học vụ. Nhận diện bậc đào tạo từ chương trong quy chế: mặc định đại học cho CTĐT cử nhân đang hỗ trợ, câu hỏi nêu rõ kỹ sư/thạc sĩ/tiến sĩ hoặc số điều được xử lý đúng phạm vi. Mã ngành trong câu hỏi học phí/học bổng không ép truy xuất sang tài liệu CTĐT.
- Khi một điểm được khớp, truy xuất mở rộng sang các điểm trong cùng khoản để giữ đầy đủ phần dẫn và điều kiện; chỉ mở rộng khi tổng nội dung không vượt 4.000 ký tự. Khử trùng lặp theo khoản, giữ phạm vi trang nếu khoản trải qua nhiều trang. Trích xuất tối đa 4 ngữ cảnh, kèm URL và phạm vi áp dụng; nguồn có thể bấm mở từ giao diện.
- Phạm vi học phí: không dùng quyết định cũ để xác nhận mức của năm khác hoặc học kỳ hiện tại chưa có văn bản tương ứng.
- Hai kiểm thử HTTP có sẵn phát hiện Origin ngoài danh sách vẫn đăng nhập được và tin nhắn quá dài chưa bị từ chối; đã bổ sung kiểm tra. Kiểm thử TTL Mongo giả lập được cố định đồng hồ để không tự hỏng khi ngày chạy vượt quá ngày hết hạn fixture.

## Kết quả tái lập trên cùng 100 câu gốc

Nguồn trước sửa là commit `884e0181977d08257b42a1ae32c8aee073b9caa1`. Bộ câu hỏi gốc không thay đổi trong đợt sửa này.

| Chỉ số | Trước sửa | Sau sửa |
|---|---:|---:|
| Phân loại ý định | 97,0% | 100,0% |
| Trích xuất mã học phần | 100,0% | 100,0% |
| Recall@4 (tỷ lệ có ít nhất một bằng chứng khớp) | 79,7% | 100,0% |
| MRR@4 | 62,6% | 80,7% |
| Câu trả lời chứa cụm từ kỳ vọng | 77,4% | 100,0% |
| Độ trễ trung vị trong lần đo | 172 ms | 225 ms |

Báo cáo: [trước sửa](../../project/eval/reports/before_reliability_fixes.md), [sau sửa](../../project/eval/reports/reliability_fixes.md). Các ngưỡng `project/eval/thresholds.json` được giữ nguyên và đều đạt.

Các phép đo này **tắt LLM**, không đo chất lượng Gemini. Chỉ số chứa ý chính dùng khớp cụm từ; câu trả lời có thể chứa cụm từ đúng nhưng vẫn chưa giải quyết trọn câu hỏi. Đơn vị ngữ cảnh mới có thể là cả khoản, đồng thời chế độ trích xuất giữ 4 ngữ cảnh đầy đủ thay cho tối đa 3 đoạn cắt ở 900 ký tự. Vì vậy, phần tăng của chỉ số không thể quy hoàn toàn cho chất lượng xếp hạng; đây là so sánh toàn pipeline với cách chia đoạn và kích thước ngữ cảnh khác nhau. Số ký tự ngữ cảnh trung vị của bản mới là 2.246 trên tập gốc và 2.208 trên tập bổ sung. Độ trễ là kết quả một lần chạy cục bộ, không phải benchmark tải đồng thời. Các báo cáo mới ghi chế độ, commit nền, trạng thái chưa commit và checksum bộ câu hỏi/mã nguồn/corpus; đánh giá dừng nếu các nguồn này thay đổi giữa lần chạy.

## Bộ diễn đạt bổ sung

Thêm [20 câu](../../project/eval/validation_questions.jsonl) dưới dạng diễn đạt khác dựa trên cùng căn cứ với bộ gốc. Bộ này giúp phát hiện và sửa thêm lỗi định tuyến ký hiệu điểm, trình độ năm học và câu chào. Vì đã dùng để phát hiện lỗi, đây là tập kiểm thử hồi quy mở rộng, **không phải tập kiểm định độc lập chưa từng sử dụng**.

[Kết quả](../../project/eval/reports/validation_reliability.md): ý định 100%, mã môn 100%, Recall@4 93,3%, MRR@4 70,6%, chứa ý chính 92,9%. Còn một câu chưa đạt về học phí tiến sĩ có nêu năm học; câu này được giữ nguyên trong báo cáo, không thay đáp án để nâng điểm. Một nhãn mã môn sao chép nhầm khi tạo tập bổ sung đã được sửa từ hai mã sang `ET3300`, đúng với câu hỏi chỉ nêu một học phần.

## Kiểm chứng và phần còn lại

- 191 kiểm thử backend, 17 kiểm thử dữ liệu và 19 kiểm thử bộ đánh giá chạy đạt (227 kiểm thử).
- Frontend build và lint chạy đạt. Kiểm tra trình duyệt trên backend và kho hồ sơ riêng bằng tài khoản giả: môn lạ yêu cầu xác nhận, không lưu trước bước xác nhận; xác nhận 4 TC cho môn ngoài danh mục rồi tính CPA đúng 3,43; chuẩn đầu ra của CTĐT 2023 xuất hiện đủ; thông báo lưu thành công hiển thị.
- Tập gốc đạt toàn bộ tiêu chí tự động; tập bổ sung còn một câu chưa đạt. Chưa đánh giá Gemini trực tiếp, chưa bổ sung nguồn học phí mới và chưa mở thêm CTĐT ngoài ET1. Cần có thêm bộ kiểm định do người khác biên soạn cùng chấm tính đúng của trả lời và dẫn nguồn trước khi kết luận khả năng tổng quát hóa. Không diễn giải kết quả 100% trên bộ hồi quy thành độ chính xác 100% ngoài thực tế.
- Chưa mở rộng giao diện sang cây học phần hay lập kế hoạch nhiều kỳ: ưu tiên tiếp theo vẫn là xử lý các ca chưa đạt và chuẩn hóa thêm một CTĐT từ nguồn chính thức khi hoàn tất rà soát dữ liệu.

## Chạy lại

`./scripts/test_all.sh` chạy các bộ kiểm thử, đánh giá gốc có kiểm tra ngưỡng, tập diễn đạt bổ sung, lint và build. Chạy bằng Git Bash sau khi thiết lập venv như README. Script dùng kho cục bộ, không gọi Gemini hay ghi MongoDB thật.

Trên Windows, mỗi lần chạy đánh giá riêng nên dùng một `VECTOR_DB_DIR` mới nằm trong `project/data/vector_db_test/`; không chia sẻ thư mục vector với backend dev đang chạy. ChromaDB trên Windows có thể để lại chỉ mục không đọc được giữa các tiến trình; chỉ mục thử nghiệm là dữ liệu sinh lại được.
