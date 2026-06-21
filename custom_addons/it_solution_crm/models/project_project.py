from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    is_it_consulting_project = fields.Boolean("Dự án phòng tư vấn IT", default=False, index=True, tracking=True)
    crm_lead_id = fields.Many2one("crm.lead", "Cơ hội QLKH", ondelete="set null", tracking=True, index=True)
    team_member_ids = fields.Many2many("res.users", string="Thành viên dự án", tracking=True)
    hr_employee_ids = fields.Many2many("nhan_vien", compute="_compute_it_metrics", compute_sudo=True, string="Nhân sự HRM")
    member_count = fields.Integer("Số thành viên", compute="_compute_it_metrics", store=True)
    it_task_total = fields.Integer("Tổng công việc", compute="_compute_it_metrics", store=True)
    it_task_done = fields.Integer("Công việc hoàn thành", compute="_compute_it_metrics", store=True)
    it_task_overdue = fields.Integer("Công việc quá hạn", compute="_compute_it_metrics", store=True)
    completion_rate = fields.Float("Tiến độ hoàn thành (%)", compute="_compute_it_metrics", store=True, group_operator="avg")

    @api.depends("team_member_ids", "task_ids.it_status", "task_ids.sla_status", "task_ids.user_ids")
    def _compute_it_metrics(self):
        for project in self:
            tasks = project.task_ids.filtered(lambda task: task.it_task_kind)
            users = project.team_member_ids | tasks.mapped("user_ids")
            project.member_count = len(users)
            project.hr_employee_ids = self.env["nhan_vien"].search([("user_id", "in", users.ids)])
            project.it_task_total = len(tasks)
            project.it_task_done = len(tasks.filtered(lambda task: task.it_status == "done"))
            project.it_task_overdue = len(tasks.filtered(lambda task: task.sla_status in ("overdue", "late")))
            project.completion_rate = 100.0 * project.it_task_done / project.it_task_total if project.it_task_total else 0.0
