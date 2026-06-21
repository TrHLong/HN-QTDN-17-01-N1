# Audit Code và Gap Analysis - QLKH + QLCV IT

## 1. Phạm vi đánh giá hiện trạng

Nền tảng kế thừa là Odoo 15 do Khoa CNTT cung cấp, bao gồm source Odoo và module HRM `nhan_su`.

Hiện trạng ban đầu:

- HRM quản lý nhân viên, đơn vị, chức vụ, lịch sử công tác và chứng chỉ.
- Các module HRM ban đầu hoạt động độc lập, chưa có quy trình tư vấn khách hàng kết hợp quản lý công việc.
- Nhân viên chưa có khóa liên kết rõ ràng với tài khoản Odoo để giao cơ hội và task.
- Chưa có luồng tự động từ tương tác khách hàng sang đầu việc cụ thể.
- Chưa có SLA, AI phân tích nhu cầu hoặc kết nối dịch vụ ngoài cho bài toán tư vấn IT.

## 2. Lỗi/hạn chế và nhu cầu bổ sung

| Khoảng trống ban đầu | Hướng xử lý trong sản phẩm |
|---|---|
| HRM chưa nối tài khoản hệ thống | Bổ sung `nhan_vien.user_id`, ràng buộc mỗi user thuộc tối đa một nhân viên |
| QLKH và QLCV chưa liên kết | `project.task.crm_lead_id` liên kết task với cơ hội CRM |
| Tương tác khách hàng chưa sinh đầu việc | Các action QLKH tự động tạo/cập nhật task theo loại nghiệp vụ |
| Chưa phân vai Sales/Presales/Manager | Bổ sung nhóm quyền và người phụ trách cho từng bước |
| Chưa theo dõi hạn xử lý | Bổ sung trạng thái nghiệp vụ, deadline, SLA và cron cảnh báo |
| Chưa lưu lịch sử tư vấn/KPI | Bổ sung model phiên tư vấn, kết quả mua hàng và đánh giá |
| Chưa có công nghệ mức 3 | Bổ sung AI/LLM, Google Calendar và Telegram |

## 3. Phần kế thừa

- Source Odoo 15 và các module chuẩn `crm`, `project`, `mail`, `calendar`.
- Platform ERP từ kho học phần FIT-DNU Business-Internship.
- Module HRM `nhan_su` với các model nhân viên, đơn vị, chức vụ, lịch sử công tác và chứng chỉ.

## 4. Phần phát triển/cải tiến mới

- Module tích hợp `it_solution_crm`.
- Trường liên kết HRM - tài khoản Odoo và các compute map nhân viên.
- Quy trình QLKH: mới, xác minh, khảo sát, thiết kế, phê duyệt, báo giá, khách đồng ý.
- Các loại task QLCV: liên hệ, follow-up, khảo sát, thiết kế, phê duyệt, báo giá, theo dõi báo giá, bàn giao.
- Tự động hóa theo sự kiện và chống tạo task trùng theo cơ hội/loại công việc.
- SLA, cron cảnh báo, mail activity và nhật ký thao tác.
- AI phân tích nhu cầu, cấu hình API, Google Calendar và Telegram.
- Báo cáo QLKH, QLCV và hiệu quả nhân viên tư vấn.

## 5. Kết quả đối chiếu

- Mức 1: tích hợp HRM làm dữ liệu nhân sự gốc.
- Mức 2: tự động hóa quy trình QLKH → QLCV theo sự kiện.
- Mức 3: có điểm tích hợp AI và External API.

## 6. Rủi ro/công việc còn phải chuẩn bị khi bảo vệ

- Cần cấu hình ít nhất một API thật để minh chứng Mức 3, ưu tiên Telegram hoặc AI endpoint.
- Cần kiểm thử bằng các tài khoản Sales, Presales và Manager, không chỉ bằng admin.
- Cần bổ sung poster và video nếu nhóm thực hiện phần khuyến khích.
- Repository nộp phải có commit history rõ ràng và ghi nguồn kế thừa.
