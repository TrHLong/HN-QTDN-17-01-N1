from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ItConsultationSession(models.Model):
    _name = "it.consultation.session"
    _description = "Phiên tư vấn giải pháp IT"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "consulted_at desc, id desc"

    name = fields.Char("Mã phiên tư vấn", required=True, copy=False, readonly=True, default=lambda self: _("Mới"))
    lead_id = fields.Many2one("crm.lead", "Cơ hội QLKH", required=True, ondelete="cascade", tracking=True, index=True)
    partner_id = fields.Many2one(related="lead_id.partner_id", string="Khách hàng", store=True, index=True)
    consultant_user_id = fields.Many2one("res.users", "Nhân viên tư vấn", required=True, default=lambda self: self.env.user, tracking=True, index=True)
    employee_id = fields.Many2one("nhan_vien", "Nhân viên HRM", compute="_compute_employee", store=True, index=True)
    consulted_at = fields.Datetime("Thời điểm tư vấn", required=True, default=fields.Datetime.now, tracking=True)
    channel = fields.Selection(
        [("phone", "Điện thoại"), ("email", "Email"), ("online", "Họp trực tuyến"), ("onsite", "Trực tiếp tại khách hàng"), ("chat", "Chat/Zalo")],
        string="Kênh tư vấn", required=True, default="phone", tracking=True,
    )
    duration_minutes = fields.Integer("Thời lượng (phút)", default=30, tracking=True)
    customer_need = fields.Text("Nhu cầu ghi nhận", required=True, tracking=True)
    advice_summary = fields.Text("Nội dung đã tư vấn", required=True, tracking=True)
    outcome = fields.Selection(
        [("successful", "Tư vấn đạt yêu cầu"), ("followup", "Cần tư vấn tiếp"), ("unsuitable", "Giải pháp chưa phù hợp"), ("no_response", "Không liên hệ được")],
        string="Kết quả tư vấn", required=True, default="followup", tracking=True, index=True,
    )
    purchase_outcome = fields.Selection(
        [("pending", "Chưa quyết định"), ("ordered", "Đã đồng ý mua"), ("not_ordered", "Tư vấn thành công nhưng chưa mua"), ("rejected", "Từ chối mua")],
        string="Kết quả mua hàng", required=True, default="pending", tracking=True, index=True,
    )
    customer_rating = fields.Selection([(str(i), "%s/5" % i) for i in range(1, 6)], string="Khách hàng đánh giá", tracking=True, index=True)
    feedback_note = fields.Text("Ý kiến khách hàng", tracking=True)
    next_action_at = fields.Datetime("Hẹn xử lý tiếp", tracking=True)
    state = fields.Selection([("draft", "Nháp"), ("done", "Đã hoàn tất"), ("cancelled", "Đã hủy")], default="draft", required=True, tracking=True, index=True)
    session_count = fields.Integer("Số phiên tư vấn", default=1, readonly=True)
    successful_count = fields.Integer("Số phiên tư vấn đạt", compute="_compute_kpi_counts", store=True)
    ordered_count = fields.Integer("Số khách đã mua", compute="_compute_kpi_counts", store=True)
    successful_no_order_count = fields.Integer("Đạt nhưng chưa mua", compute="_compute_kpi_counts", store=True)
    good_rating_count = fields.Integer("Số đánh giá tốt", compute="_compute_kpi_counts", store=True)

    @api.depends("consultant_user_id")
    def _compute_employee(self):
        employees = self.env["nhan_vien"].search([("user_id", "in", self.mapped("consultant_user_id").ids)])
        by_user = {employee.user_id.id: employee for employee in employees}
        for session in self:
            session.employee_id = by_user.get(session.consultant_user_id.id)

    @api.depends("outcome", "purchase_outcome", "customer_rating")
    def _compute_kpi_counts(self):
        for session in self:
            session.successful_count = 1 if session.outcome == "successful" else 0
            session.ordered_count = 1 if session.purchase_outcome == "ordered" else 0
            session.successful_no_order_count = 1 if session.outcome == "successful" and session.purchase_outcome == "not_ordered" else 0
            session.good_rating_count = 1 if session.customer_rating in ("4", "5") else 0

    @api.constrains("duration_minutes")
    def _check_duration(self):
        if any(session.duration_minutes <= 0 for session in self):
            raise ValidationError(_("Thời lượng tư vấn phải lớn hơn 0 phút."))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get("name", _("Mới")) == _("Mới"):
                values["name"] = self.env["ir.sequence"].next_by_code("it.consultation.session") or _("Mới")
        records = super().create(values_list)
        for record in records:
            self.env["it.operation.log"].log(record, "create", {"lead_id": record.lead_id.id})
        return records

    def write(self, values):
        result = super().write(values)
        if not self.env.context.get("skip_operation_log"):
            for record in self:
                self.env["it.operation.log"].log(record, "state" if "state" in values else "update", values)
        return result

    def action_complete(self):
        for session in self:
            if session.outcome == "successful" and not session.customer_rating:
                raise UserError(_("Hãy ghi nhận đánh giá khách hàng trước khi hoàn tất phiên tư vấn thành công."))
            session.write({"state": "done"})
            session.lead_id.message_post(body=_("Hoàn tất %s - kết quả: %s; mua hàng: %s") % (
                session.display_name,
                dict(session._fields["outcome"].selection).get(session.outcome),
                dict(session._fields["purchase_outcome"].selection).get(session.purchase_outcome),
            ))
            if session.next_action_at and session.outcome == "followup":
                session.lead_id._create_it_task(
                    "consultation_followup",
                    _("Tư vấn tiếp sau %s") % session.display_name,
                    fields.Datetime.to_datetime(session.next_action_at).date(),
                )
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True
