# Hướng dẫn Trợ lý AI QLKH - QLCV

## 1. Trợ lý AI làm gì?

Menu `QLKH > Trợ lý AI hỏi nhanh` đọc dữ liệu trực tiếp từ:

- Cơ hội và doanh thu kỳ vọng trong QLKH.
- Công việc, trạng thái nghiệp vụ và SLA trong QLCV.
- Phân công Sales, Presales, Trưởng phòng liên kết từ HRM `nhan_su`.

Các câu hỏi demo:

- `Công việc nào đang quá hạn?`
- `Cơ hội nào đang chờ phê duyệt?`
- `Ai phụ trách GreenLake?`
- `Tổng doanh thu kỳ vọng là bao nhiêu?`
- `Có bao nhiêu công việc IT?`

## 2. Hai chế độ hoạt động

### Dữ liệu nội bộ

Không cần API key. Hệ thống nhận diện các câu hỏi quản trị phổ biến và trả lời bằng dữ liệu Odoo hiện tại. Badge hiển thị `Dữ liệu nội bộ`.

### LLM/API ngoài

Hệ thống gửi câu hỏi cùng bản tóm tắt nghiệp vụ đã lọc tới endpoint tương thích OpenAI Chat Completions. Không gửi số điện thoại hoặc email khách hàng. Badge hiển thị `LLM/API ngoài` khi gọi thành công.

Nếu API lỗi, hệ thống vẫn trả lời bằng dữ liệu nội bộ và badge hiển thị `API lỗi - dùng dữ liệu nội bộ`.

## 3. Cấu hình API

Đăng nhập tài khoản Admin và mở `Settings > General Settings`. Tìm khối `IT Solution CRM - AI và API ngoài`, sau đó nhập:

- **AI endpoint:** `https://api.openai.com/v1/chat/completions`
- **AI API key:** khóa bí mật của tài khoản API.
- **AI model:** một model Chat Completions đang khả dụng trong tài khoản. Cấu hình demo mặc định là `gpt-4o-mini`.

Bấm `Save`. Không đưa API key vào file Python, XML, ảnh chụp hoặc GitHub.

Có thể tạo và quản lý khóa OpenAI tại: <https://platform.openai.com/api-keys>

## 4. Cách kiểm thử và chứng minh mức 3

1. Hỏi `Công việc nào đang quá hạn?` khi chưa cấu hình API: badge phải là `Dữ liệu nội bộ`.
2. Nhập endpoint, API key, model và lưu Settings.
3. Mở lại `QLKH > Trợ lý AI hỏi nhanh`.
4. Hỏi `Hãy tóm tắt tình hình phòng tư vấn và đề xuất ưu tiên xử lý hôm nay`.
5. Kiểm tra badge chuyển thành `LLM/API ngoài`.
6. Admin mở phần `Dữ liệu kiểm chứng` để đối chiếu câu trả lời với JSON lấy từ QLKH, QLCV và HRM.

## 5. Phân biệt hai chức năng AI

- `AI phân tích nhu cầu`: nhận nội dung cuộc gọi/email của một khách hàng, phân loại giải pháp và đề xuất có cần khảo sát hay không.
- `Trợ lý AI hỏi nhanh`: hỏi đáp trên dữ liệu tổng hợp của cả phòng tư vấn để hỗ trợ điều hành.

Hai chức năng dùng chung cấu hình endpoint, API key và model.
