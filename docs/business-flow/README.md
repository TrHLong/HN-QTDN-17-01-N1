# Business Flow - QLKH + QLCV IT

File chính:

- `Nhom01_BusinessFlow_QLKH_QLCV_IT.pdf`

Luồng này mô tả quy trình happy path end-to-end của đề tài Quản lý khách hàng + Quản lý công việc cho phòng tư vấn giải pháp IT.

Các điểm bắt buộc đã thể hiện:

- Actor/vai trò: Khách hàng, Sales IT, Hệ thống Odoo, HRM `nhan_su`, Presales, Trưởng phòng.
- Các bước chính từ tiếp nhận nhu cầu đến báo giá và bàn giao.
- Điểm tích hợp HRM: `nhan_vien.user_id` là dữ liệu gốc nhân sự để QLKH/QLCV map người phụ trách.
- Trigger mức 2: các thao tác QLKH tự động tạo/cập nhật task QLCV.
- Điểm mức 3: AI phân tích nhu cầu, Google Calendar và Telegram.
