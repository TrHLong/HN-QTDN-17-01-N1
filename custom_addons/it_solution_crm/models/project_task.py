import requests

from odoo import _, api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="Cơ hội CRM",
        ondelete="set null",
        index=True,
        tracking=True,
    )
    it_task_kind = fields.Selection(
        [
            ("initial_contact", "Liên hệ ban đầu"),
            ("consultation_followup", "Tư vấn tiếp theo"),
            ("site_survey", "Khảo sát hiện trạng"),
            ("solution_design", "Thiết kế giải pháp"),
            ("quotation", "Lập báo giá"),
            ("quotation_followup", "Theo dõi báo giá"),
            ("approval", "Phê duyệt"),
            ("handover", "Bàn giao kỹ thuật"),
        ],
        string="Loại công việc IT",
        index=True,
        tracking=True,
    )
    crm_customer_id = fields.Many2one(
        related="crm_lead_id.partner_id",
        string="Khách hàng CRM",
        store=True,
    )
    hr_employee_ids = fields.Many2many(
        "nhan_vien",
        compute="_compute_hr_employee_ids",
        string="Nhân viên HRM",
    )
    it_status = fields.Selection(
        [
            ("pending", "Chờ xử lý"),
            ("in_progress", "Đang xử lý"),
            ("done", "Hoàn thành"),
            ("cancelled", "Đã hủy"),
        ],
        string="Trạng thái nghiệp vụ",
        default="pending",
        required=True,
        tracking=True,
    )
    it_completed_at = fields.Datetime("Hoàn thành lúc", readonly=True, tracking=True)
    sla_status = fields.Selection(
        [
            ("pending", "Trong hạn"),
            ("overdue", "Quá hạn"),
            ("on_time", "Đúng hạn"),
            ("late", "Hoàn thành trễ"),
        ],
        compute="_compute_sla_status",
        string="SLA",
        store=True,
    )
    sla_alerted = fields.Boolean("Đã cảnh báo SLA", copy=False)
    telegram_notified_at = fields.Datetime("Thời điểm báo Telegram", readonly=True, copy=False)
    telegram_last_error = fields.Text("Lỗi Telegram gần nhất", readonly=True, copy=False)

    _sql_constraints = [
        (
            "crm_lead_task_kind_unique",
            "unique(crm_lead_id, it_task_kind)",
            "Mỗi cơ hội chỉ có một công việc cho từng loại nghiệp vụ IT.",
        )
    ]

    @api.depends("user_ids")
    def _compute_hr_employee_ids(self):
        for task in self:
            task.hr_employee_ids = self.env["nhan_vien"].search(
                [("user_id", "in", task.user_ids.ids)]
            )

    def _config_param(self, key):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("it_solution_crm.%s" % key)
        )

    def _send_telegram_message(self, message):
        token = self._config_param("telegram_bot_token")
        chat_id = self._config_param("telegram_chat_id")
        if not token or not chat_id:
            return False
        response = requests.post(
            "https://api.telegram.org/bot%s/sendMessage" % token,
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
        response.raise_for_status()
        return True

    def _notify_telegram(self, message):
        for task in self:
            try:
                sent = task._send_telegram_message(message)
                if sent:
                    task.write(
                        {
                            "telegram_notified_at": fields.Datetime.now(),
                            "telegram_last_error": False,
                        }
                    )
            except Exception as error:
                task.telegram_last_error = str(error)

    @api.model_create_multi
    def create(self, values_list):
        tasks = super().create(values_list)
        for task in tasks.filtered(lambda item: item.it_task_kind):
            self.env["it.operation.log"].log(task, "create", {"it_task_kind": task.it_task_kind})
            task._notify_telegram(_("Công việc tư vấn IT mới: %s") % task.display_name)
        return tasks

    def write(self, values):
        result = super().write(values)
        if not self.env.context.get("skip_operation_log"):
            for task in self.filtered(lambda item: item.it_task_kind):
                self.env["it.operation.log"].log(task, "state" if "it_status" in values else "update", values)
        return result

    @api.depends("date_deadline", "it_status", "it_completed_at")
    def _compute_sla_status(self):
        today = fields.Date.context_today(self)
        for task in self:
            if task.it_status == "done":
                completed_date = (
                    fields.Datetime.to_datetime(task.it_completed_at).date()
                    if task.it_completed_at
                    else today
                )
                task.sla_status = (
                    "late"
                    if task.date_deadline and completed_date > task.date_deadline
                    else "on_time"
                )
            elif task.date_deadline and task.date_deadline < today:
                task.sla_status = "overdue"
            else:
                task.sla_status = "pending"

    def action_start_it_task(self):
        self.write({"it_status": "in_progress"})
        return True

    def action_complete_it_task(self):
        for task in self:
            task.write(
                {"it_status": "done", "it_completed_at": fields.Datetime.now()}
            )
            if task.crm_lead_id and task.it_task_kind == "site_survey":
                task.crm_lead_id.action_request_solution_design()
        return True

    @api.model
    def _cron_schedule_overdue_alerts(self):
        overdue_tasks = self.search(
            [
                ("it_task_kind", "!=", False),
                ("it_status", "not in", ("done", "cancelled")),
                ("date_deadline", "<", fields.Date.context_today(self)),
                ("user_ids", "!=", False),
                ("sla_alerted", "=", False),
            ]
        )
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for task in overdue_tasks:
            for user in task.user_ids:
                task.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=_("Công việc tư vấn IT đã quá hạn"),
                    note=_("Công việc '%s' đã quá hạn và cần được xử lý.") % task.display_name,
                )
            task._notify_telegram(
                _("Công việc tư vấn IT quá hạn: %s") % task.display_name
            )
            task.sla_alerted = True
