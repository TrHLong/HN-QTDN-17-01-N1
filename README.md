<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>
<h2 align="center">
    PLATFORM ERP
</h2>
<div align="center">
    <p align="center">
        <img src="docs/logo/aiotlab_logo.png" alt="AIoTLab Logo" width="170"/>
        <img src="docs/logo/fitdnu_logo.png" alt="AIoTLab Logo" width="180"/>
        <img src="docs/logo/dnu_logo.png" alt="DaiNam University Logo" width="200"/>
    </p>

[![AIoTLab](https://img.shields.io/badge/AIoTLab-green?style=for-the-badge)](https://www.facebook.com/DNUAIoTLab)
[![Faculty of Information Technology](https://img.shields.io/badge/Faculty%20of%20Information%20Technology-blue?style=for-the-badge)](https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin)
[![DaiNam University](https://img.shields.io/badge/DaiNam%20University-orange?style=for-the-badge)](https://dainam.edu.vn)

</div>

## 📖 1. Giới thiệu
Platform ERP được áp dụng vào học phần Thực tập doanh nghiệp dựa trên mã nguồn mở Odoo. 

## 🔧 2. Các công nghệ được sử dụng
<div align="center">

### Hệ điều hành
[![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](https://ubuntu.com/)
### Công nghệ chính
[![Odoo](https://img.shields.io/badge/Odoo-714B67?style=for-the-badge&logo=odoo&logoColor=white)](https://www.odoo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![XML](https://img.shields.io/badge/XML-FF6600?style=for-the-badge&logo=codeforces&logoColor=white)](https://www.w3.org/XML/)
### Cơ sở dữ liệu
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
</div>

## 🚀 3. Các project đã thực hiện dựa trên Platform

Một số project sinh viên đã thực hiện:
- #### [Khoá 15](./docs/projects/K15/README.md)
- #### [Khoá 16](./docs/projects/K16/README.md)
- #### [Khoá 17](./docs/projects/K17/README.md)
## ⚙️ 4. Cài đặt

### 4.1. Cài đặt công cụ, môi trường và các thư viện cần thiết

#### 4.1.1. Tải project.
```
git clone https://github.com/FIT-DNU/Business-Internship.git
```
#### 4.1.2. Cài đặt các thư viện cần thiết
Người sử dụng thực thi các lệnh sau đề cài đặt các thư viện cần thiết

```
sudo apt-get install libxml2-dev libxslt-dev libldap2-dev libsasl2-dev libssl-dev python3.10-distutils python3.10-dev build-essential libssl-dev libffi-dev zlib1g-dev python3.10-venv libpq-dev
```
#### 4.1.3. Khởi tạo môi trường ảo.
- Khởi tạo môi trường ảo
```
python3.10 -m venv ./venv
```
- Thay đổi trình thông dịch sang môi trường ảo
```
source venv/bin/activate
```
- Chạy requirements.txt để cài đặt tiếp các thư viện được yêu cầu
```
pip3 install -r requirements.txt
```
### 4.2. Setup database

Khởi tạo database trên docker bằng việc thực thi file dockercompose.yml.
```
sudo docker-compose up -d
```
### 4.3. Setup tham số chạy cho hệ thống
Tạo tệp **odoo.conf** có nội dung như sau:
```
[options]
addons_path = addons
db_host = localhost
db_password = odoo
db_user = odoo
db_port = 5431
xmlrpc_port = 8069
```
Có thể kế thừa từ file **odoo.conf.template**
### 4.4. Chạy hệ thống và cài đặt các ứng dụng cần thiết
Lệnh chạy
```
python3 odoo-bin.py -c odoo.conf -u all
```
Người sử dụng truy cập theo đường dẫn _http://localhost:8069/_ để đăng nhập vào hệ thống.

## 📝 5. License

© 2024 AIoTLab, Faculty of Information Technology, DaiNam University. All rights reserved.

---

## Bài tập lớn: Tích hợp QLKH - QLCV cho phòng tư vấn giải pháp IT

### Đề tài và phạm vi

Nhóm chọn cặp module **Quản lý khách hàng + Quản lý công việc** theo yêu cầu bài tập lớn. Bối cảnh nghiệp vụ là phòng tư vấn giải pháp IT, nơi mọi tương tác với khách hàng như tiếp nhận nhu cầu, tư vấn, khảo sát, thiết kế giải pháp, phê duyệt và báo giá được chuyển hóa thành các đầu việc cụ thể để theo dõi trong QLCV.

Các module tham gia:

- `nhan_su`: HRM, dữ liệu gốc về nhân viên, đơn vị, chức vụ và tài khoản Odoo của nhân viên.
- `it_solution_crm`: phân hệ tích hợp QLKH - QLCV IT, mở rộng `crm.lead`, `project.task`, `project.project`.
- Module chuẩn Odoo: `crm`, `project`, `mail`, `calendar`.

### Nguồn kế thừa và cải tiến

Sản phẩm được phát triển trên nền tảng ERP/Odoo 15 do Khoa CNTT cung cấp trong kho học phần FIT-DNU Business-Internship. Nhóm kế thừa platform gốc và module HRM `nhan_su`, sau đó bổ sung module `it_solution_crm` để tích hợp QLKH, QLCV, HRM, tự động hóa quy trình và AI/API ngoài.

Các cải tiến chính:

- Bổ sung quy trình tư vấn giải pháp IT end-to-end trên hồ sơ khách hàng/cơ hội CRM.
- Liên kết nhân sự HRM với tài khoản Odoo qua `nhan_vien.user_id`.
- Tự động sinh/cập nhật công việc QLCV từ các bước xử lý QLKH.
- Theo dõi SLA, trạng thái nghiệp vụ, người phụ trách và nhật ký thao tác.
- Tích hợp AI phân tích nhu cầu khách hàng, Google Calendar cho lịch khảo sát và Telegram cho cảnh báo công việc.

### Đối chiếu tiêu chí mức độ hoàn thiện

- **Mức 1 - Tích hợp hệ thống:** Đạt. QLKH/QLCV dùng HRM `nhan_su` làm nguồn dữ liệu nhân sự gốc thông qua `nhan_vien.user_id`.
- **Mức 2 - Tự động hóa quy trình:** Đạt. Các sự kiện như tạo cơ hội, xác minh nhu cầu, đặt lịch khảo sát, gửi phê duyệt, phê duyệt, gửi báo giá và khách đồng ý tự động tạo/cập nhật task QLCV.
- **Mức 3 - AI & External API:** Có triển khai. Hệ thống có AI phân tích nhu cầu, cấu hình endpoint tương thích OpenAI Chat Completions, đồng bộ Google Calendar và gửi thông báo Telegram.

### Audit Code và Gap Analysis

Tài liệu đánh giá hiện trạng, phần kế thừa và phần phát triển mới:

`docs/analysis/AUDIT_AND_GAP_QLKH_QLCV.md`

### Luồng nghiệp vụ bắt buộc

Sơ đồ happy path end-to-end được lưu tại:

`docs/business-flow/Nhom01_BusinessFlow_QLKH_QLCV_IT.pdf`

Luồng mô tả quá trình từ khi khách hàng gửi nhu cầu đến khi Sales/Presales xử lý, trưởng phòng phê duyệt, hệ thống tạo task QLCV, theo dõi SLA, tích hợp HRM và đánh dấu các điểm AI/API.

### Kịch bản kiểm thử nhanh

1. **Không cần khảo sát:** tạo cơ hội thiết bị văn phòng, AI phân tích nhu cầu, xác minh nhu cầu, thiết kế giải pháp, gửi phê duyệt, duyệt, gửi báo giá, khách đồng ý.
2. **Cần khảo sát:** tạo cơ hội Wi-Fi/camera/server, bật cần khảo sát hiện trạng, xác minh nhu cầu, kiểm tra task khảo sát trong QLCV, hoàn thành khảo sát để chuyển sang thiết kế giải pháp.
3. **Phê duyệt và SLA:** gửi phương án cho trưởng phòng, kiểm tra task phê duyệt trong QLCV, duyệt/từ chối, theo dõi task báo giá, follow-up và cảnh báo quá hạn SLA.

