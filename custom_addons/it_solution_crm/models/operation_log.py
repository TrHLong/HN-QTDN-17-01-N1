import json

from odoo import api, fields, models


class ItOperationLog(models.Model):
    _name = "it.operation.log"
    _description = "Nhật ký thao tác nghiệp vụ phòng tư vấn IT"
    _order = "occurred_at desc, id desc"

    occurred_at = fields.Datetime("Thời điểm", required=True, readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", "Người thao tác", required=True, readonly=True)
    employee_id = fields.Many2one("nhan_vien", "Nhân viên HRM", readonly=True)
    action = fields.Selection(
        [("create", "Tạo mới"), ("update", "Cập nhật"), ("state", "Chuyển trạng thái"), ("complete", "Hoàn thành")],
        string="Thao tác", required=True, readonly=True,
    )
    model_name = fields.Char("Mô hình", required=True, readonly=True, index=True)
    record_id = fields.Integer("ID bản ghi", required=True, readonly=True, index=True)
    record_name = fields.Char("Tên bản ghi", readonly=True)
    detail = fields.Text("Chi tiết", readonly=True)

    @api.model
    def log(self, record, action, changes=None):
        employee = self.env["nhan_vien"].sudo().search([("user_id", "=", self.env.user.id)], limit=1)
        detail = changes if isinstance(changes, str) else json.dumps(changes or {}, ensure_ascii=False, default=str)
        return self.sudo().create({
            "user_id": self.env.user.id,
            "employee_id": employee.id,
            "action": action,
            "model_name": record._name,
            "record_id": record.id,
            "record_name": record.display_name,
            "detail": detail,
        })

    def write(self, values):
        if not self.env.context.get("allow_audit_write"):
            return False
        return super().write(values)

    def unlink(self):
        return False
