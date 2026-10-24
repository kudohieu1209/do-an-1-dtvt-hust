# Kiểm tra bản bàn giao — 24/10/2026

Mã nguồn được kiểm tra ở commit
`1619584c3b162fa96ff49c89f017d482e7cc8888`. Bản sao kiểm tra được tạo bằng
`git clone --no-hardlinks --no-local` từ repository đã commit, có thư mục Git
riêng và working tree sạch. Không sao chép `.env`, bảng điểm, database, venv hay
`node_modules` của máy tác giả vào bản clone.

## Môi trường và cách chạy

- Windows, PowerShell; Python 3.14.5, Node.js 24.15.0, npm 11.12.1.
- Tạo venv mới và cài `requirements.txt` cùng `requirements-dev.txt` từ PyPI.
- Chạy `npm --prefix project/frontend ci` trong clone để cài đúng lockfile.
- Đặt `PYTHON_BIN` trỏ tới Python trong venv mới rồi chạy `scripts/test_all.ps1`
  của clone. Bộ chạy tắt các khóa API và dùng MongoDB giả lập.
- Sau đó chạy `npm --prefix project/frontend audit --json` trong clone.

## Kết quả

| Hạng mục | Kết quả |
|---|---|
| Backend | 181 test đạt |
| Pipeline dữ liệu | 17 test đạt; dùng HTML fixture đã bỏ danh tính/điểm thật |
| Bộ đo đánh giá | 19 test đạt |
| Hồi quy 100 câu | Đạt tất cả ngưỡng hiện có trong `thresholds.json` |
| Tập bổ sung 20 câu | Chạy hoàn tất, công bố riêng ca chưa đạt |
| Frontend lint | 0 lỗi, 0 cảnh báo |
| Frontend production build | Thành công, Vite 8.3.5 |
| npm audit | 0 lỗ hổng được báo tại thời điểm kiểm tra |

Tổng cộng **217 kiểm thử đơn vị/tích hợp đạt**. Bộ 100 câu có Recall@4 100%,
MRR@4 80,7%, khớp ý chính 100%. Bộ 20 câu có Recall@4 93,3%, MRR@4 70,6%, khớp
ý chính 92,9%; còn một câu về học phí tiến sĩ chưa đạt. Đây là đánh giá tự động
ở chế độ trích xuất, không gọi Gemini và không thay thế chấm chất lượng thực tế.

Báo cáo đầy đủ và JSON được lưu từ lần chạy sạch này, giữ nguyên commit/hash và
chỉ đổi nhãn tiêu đề Markdown từ `latest` sang nhãn bàn giao:

- [100 câu](../project/eval/reports/handoff_20261024.md)
- [20 câu bổ sung](../project/eval/reports/validation_handoff_20261024.md)

Các commit sau commit đã kiểm tra chỉ bổ sung bằng chứng/tài liệu và quyền thực
thi cho hai script Bash; không thay đổi mã ứng dụng, test hay lockfile đã chạy.
GitHub Actions sẽ kiểm tra lại checkout trên Ubuntu, Python 3.12 và Node.js 22.
Trạng thái thực tế của CI xem tại [Actions](https://github.com/kudohieu1209/do-an-1-dtvt-hust/actions).

## Kiểm tra nội dung công khai

Không theo dõi `.env`, database cục bộ, hồ sơ sinh viên, bản sao lưu legacy,
attachment hay thư mục `report/` của tài liệu thực tập. File trong `report/`
vẫn còn trên máy; lịch sử Git cũ được giữ nguyên. Quét mẫu khóa/token/private
key trên cây file được theo dõi không phát hiện khóa thật; URI có mật khẩu
trong `test_mongo_storage.py` là giá trị giả để kiểm tra che mật khẩu.

Các phụ thuộc Python đang dùng khoảng phiên bản trong requirements; kết quả
trên ghi nhận môi trường đã chạy, không cam kết mọi phiên bản tương lai. Chưa
nghiệm thu web Internet/HTTPS, MongoDB production, tải đồng thời hay Gemini thật.
