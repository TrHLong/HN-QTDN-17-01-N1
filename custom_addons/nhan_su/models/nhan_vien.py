from odoo import models, fields, api
from datetime import date

from odoo.exceptions import ValidationError

class NhanVien(models.Model):
    _name = 'nhan_vien'
    _description = 'Bảng chứa thông tin nhân viên'
    _rec_name = 'ho_va_ten'
    _order = 'ten asc, tuoi desc'

    ma_dinh_danh = fields.Char("Mã định danh", required=True)

    ho_ten_dem = fields.Char("Họ tên đệm", required=True)
    ten = fields.Char("Tên", required=True)
    ho_va_ten = fields.Char("Họ và tên", compute="_compute_ho_va_ten", store=True)
    
    ngay_sinh = fields.Date("Ngày sinh")
    que_quan = fields.Char("Quê quán")
    email = fields.Char("Email")
    so_dien_thoai = fields.Char("Số điện thoại")
    user_id = fields.Many2one(
        "res.users",
        string="Tài khoản Odoo",
        ondelete="restrict",
        help="Tài khoản dùng để giao cơ hội CRM và công việc cho nhân viên.",
    )
    active = fields.Boolean(default=True)
    lich_su_cong_tac_ids = fields.One2many(
        "lich_su_cong_tac", 
        inverse_name="nhan_vien_id", 
        string = "Danh sách lịch sử công tác")
    tuoi = fields.Integer("Tuổi", compute="_compute_tuoi", store=True)
    anh = fields.Binary("Ảnh")
    danh_sach_chung_chi_bang_cap_ids = fields.One2many(
        "danh_sach_chung_chi_bang_cap", 
        inverse_name="nhan_vien_id", 
        string = "Danh sách chứng chỉ bằng cấp")
    so_nguoi_bang_tuoi = fields.Integer("Số người bằng tuổi", 
                                        compute="_compute_so_nguoi_bang_tuoi",
                                        store=True
                                        )
    
    @api.depends("tuoi")
    def _compute_so_nguoi_bang_tuoi(self):
        for record in self:
            record.so_nguoi_bang_tuoi = 0
            if record.tuoi:
                records = self.env['nhan_vien'].search(
                    [
                        ('tuoi', '=', record.tuoi),
                        ('ma_dinh_danh', '!=', record.ma_dinh_danh)
                    ]
                )
                record.so_nguoi_bang_tuoi = len(records)
    _sql_constraints = [
        ('ma_dinh_danh_unique', 'unique(ma_dinh_danh)', 'Mã định danh phải là duy nhất'),
        ('user_id_unique', 'unique(user_id)', 'Một tài khoản Odoo chỉ thuộc một nhân viên.'),
    ]

    @api.depends("ho_ten_dem", "ten")
    def _compute_ho_va_ten(self):
        for record in self:
            record.ho_va_ten = False
            if record.ho_ten_dem and record.ten:
                record.ho_va_ten = record.ho_ten_dem + ' ' + record.ten
    
    
    
                
    @api.onchange("ten", "ho_ten_dem")
    def _default_ma_dinh_danh(self):
        for record in self:
            if record.ho_ten_dem and record.ten:
                chu_cai_dau = ''.join([tu[0][0] for tu in record.ho_ten_dem.lower().split()])
                record.ma_dinh_danh = record.ten.lower() + chu_cai_dau
    
    @api.depends("ngay_sinh")
    def _compute_tuoi(self):
        for record in self:
            record.tuoi = 0
            if record.ngay_sinh:
                today = date.today()
                record.tuoi = today.year - record.ngay_sinh.year - (
                    (today.month, today.day) < (record.ngay_sinh.month, record.ngay_sinh.day)
                )

    @api.constrains('tuoi')
    def _check_tuoi(self):
        for record in self:
            if record.ngay_sinh and record.tuoi < 18:
                raise ValidationError("Tuổi không được bé hơn 18")
