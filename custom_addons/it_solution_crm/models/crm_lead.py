import json
from datetime import timedelta

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    solution_type = fields.Selection(
        [
            ("network", "Mạng LAN/Wi-Fi"),
            ("camera", "Camera giám sát"),
            ("server", "Máy chủ/Lưu trữ"),
            ("device", "Thiết bị văn phòng"),
            ("maintenance", "Bảo trì hệ thống"),
            ("other", "Khác"),
        ],
        string="Nhóm giải pháp",
        tracking=True,
    )
    requirements_summary = fields.Text("Nhu cầu kỹ thuật", tracking=True)
    site_address = fields.Char("Địa điểm khảo sát")
    site_survey_required = fields.Boolean("Cần khảo sát hiện trạng", tracking=True)
    site_survey_at = fields.Datetime("Lịch khảo sát", tracking=True)
    quotation_sent_at = fields.Datetime("Thời điểm gửi báo giá", tracking=True)
    consulting_state = fields.Selection(
        [
            ("new", "Mới"),
            ("qualified", "Đã xác minh"),
            ("survey", "Khảo sát"),
            ("solution", "Thiết kế giải pháp"),
            ("approval", "Chờ phê duyệt"),
            ("quotation", "Đã gửi báo giá"),
            ("won", "Khách đồng ý"),
            ("lost", "Thất bại"),
        ],
        string="Quy trình tư vấn",
        default="new",
        required=True,
        tracking=True,
    )
    solution_summary = fields.Html("Phương án kỹ thuật", tracking=True)
    presales_user_id = fields.Many2one(
        "res.users", string="Nhân viên Presales", tracking=True
    )
    manager_user_id = fields.Many2one(
        "res.users", string="Trưởng phòng phê duyệt", tracking=True
    )
    approval_state = fields.Selection(
        [
            ("draft", "Chưa gửi"),
            ("pending", "Chờ duyệt"),
            ("approved", "Đã duyệt"),
            ("rejected", "Từ chối"),
        ],
        string="Trạng thái phê duyệt",
        default="draft",
        required=True,
        tracking=True,
    )
    approval_note = fields.Text("Ý kiến phê duyệt", tracking=True)
    approved_by_id = fields.Many2one("res.users", string="Người phê duyệt", readonly=True)
    approved_at = fields.Datetime("Thời điểm phê duyệt", readonly=True)
    hr_employee_id = fields.Many2one(
        "nhan_vien",
        string="Nhân viên HRM phụ trách",
        compute="_compute_hr_employee_id",
        store=True,
    )
    it_task_ids = fields.One2many("project.task", "crm_lead_id", string="Công việc")
    it_task_count = fields.Integer(compute="_compute_it_task_count")
    consultation_session_ids = fields.One2many("it.consultation.session", "lead_id", string="Lịch sử tư vấn")
    consultation_count = fields.Integer("Số lần tư vấn", compute="_compute_consultation_metrics", store=True)
    successful_consultation_count = fields.Integer("Số lần tư vấn đạt", compute="_compute_consultation_metrics", store=True)
    good_rating_count = fields.Integer("Số đánh giá tốt", compute="_compute_consultation_metrics", store=True)
    successful_no_order_count = fields.Integer("Tư vấn đạt nhưng chưa mua", compute="_compute_consultation_metrics", store=True)
    ai_requirement_input = fields.Text("Nội dung khách hàng để AI phân tích")
    ai_analysis_json = fields.Text("JSON phân tích AI", readonly=True)
    ai_provider_status = fields.Selection(
        [
            ("none", "Chưa phân tích"),
            ("fallback", "AI nội bộ mô phỏng"),
            ("success", "LLM/API ngoài thành công"),
            ("failed", "API lỗi, dùng AI nội bộ"),
        ],
        string="Trạng thái AI",
        default="none",
        readonly=True,
    )
    ai_confidence = fields.Float("Độ tin cậy AI", readonly=True)
    ai_last_analyzed_at = fields.Datetime("Thời điểm AI phân tích", readonly=True)
    ai_error_message = fields.Text("Lỗi AI/API", readonly=True)
    calendar_event_id = fields.Char("Google Calendar Event ID", readonly=True)
    calendar_event_url = fields.Char("Google Calendar URL", readonly=True)
    calendar_synced_at = fields.Datetime("Calendar synced at", readonly=True)

    @api.depends("user_id")
    def _compute_hr_employee_id(self):
        employees = self.env["nhan_vien"].search(
            [("user_id", "in", self.mapped("user_id").ids)]
        )
        employee_by_user = {employee.user_id.id: employee for employee in employees}
        for lead in self:
            lead.hr_employee_id = employee_by_user.get(lead.user_id.id) or False

    def _compute_it_task_count(self):
        grouped = self.env["project.task"].read_group(
            [("crm_lead_id", "in", self.ids)], ["crm_lead_id"], ["crm_lead_id"]
        )
        counts = {item["crm_lead_id"][0]: item["crm_lead_id_count"] for item in grouped}
        for lead in self:
            lead.it_task_count = counts.get(lead.id, 0)

    @api.depends("consultation_session_ids.state", "consultation_session_ids.outcome", "consultation_session_ids.purchase_outcome", "consultation_session_ids.customer_rating")
    def _compute_consultation_metrics(self):
        for lead in self:
            sessions = lead.consultation_session_ids.filtered(lambda session: session.state == "done")
            lead.consultation_count = len(sessions)
            lead.successful_consultation_count = len(sessions.filtered(lambda session: session.outcome == "successful"))
            lead.good_rating_count = len(sessions.filtered(lambda session: session.customer_rating in ("4", "5")))
            lead.successful_no_order_count = len(sessions.filtered(lambda session: session.outcome == "successful" and session.purchase_outcome == "not_ordered"))

    def _config_param(self, key):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("it_solution_crm.%s" % key)
        )

    def _fallback_ai_analysis(self, text):
        lowered = (text or "").lower()
        solution_type = "other"
        if any(keyword in lowered for keyword in ("wifi", "wi-fi", "lan", "network")):
            solution_type = "network"
        elif any(keyword in lowered for keyword in ("camera", "cctv")):
            solution_type = "camera"
        elif any(keyword in lowered for keyword in ("server", "storage", "nas")):
            solution_type = "server"
        elif any(keyword in lowered for keyword in ("printer", "pc", "laptop", "device")):
            solution_type = "device"
        elif any(keyword in lowered for keyword in ("maintenance", "support", "bao tri")):
            solution_type = "maintenance"

        return {
            "solution_type": solution_type,
            "requirements_summary": text,
            "site_survey_required": solution_type in ("network", "camera", "server"),
            "solution_summary": _(
                "<p>AI gợi ý: xác nhận mục tiêu kinh doanh, hiện trạng hạ tầng, "
                "số lượng người dùng/thiết bị, yêu cầu bảo mật và SLA mong muốn "
                "trước khi lập phương án kỹ thuật cuối cùng.</p>"
            ),
            "confidence": 0.55,
        }

    def _call_ai_analysis_api(self, text):
        endpoint = self._config_param("ai_endpoint")
        api_key = self._config_param("ai_api_key")
        model = self._config_param("ai_model") or "gpt-4o-mini"
        if not endpoint or not api_key:
            return self._fallback_ai_analysis(text), "fallback", False

        payload = {
            "model": model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract an IT solution CRM requirement as JSON with keys: "
                        "solution_type, requirements_summary, site_survey_required, "
                        "solution_summary, confidence. solution_type must be one of "
                        "network,camera,server,device,maintenance,other."
                    ),
                },
                {"role": "user", "content": text},
            ],
        }
        response = requests.post(
            endpoint,
            headers={
                "Authorization": "Bearer %s" % api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        return json.loads(content), "success", data

    def action_ai_analyze_requirement(self):
        valid_types = dict(self._fields["solution_type"].selection)
        for lead in self:
            source_text = lead.ai_requirement_input or lead.requirements_summary
            if not source_text:
                raise UserError(_("Please enter a customer requirement for AI analysis."))
            try:
                analysis, status, raw_response = lead._call_ai_analysis_api(source_text)
                solution_type = analysis.get("solution_type") or "other"
                if solution_type not in valid_types:
                    solution_type = "other"
                lead.write(
                    {
                        "solution_type": solution_type,
                        "requirements_summary": analysis.get("requirements_summary")
                        or source_text,
                        "site_survey_required": bool(
                            analysis.get("site_survey_required")
                        ),
                        "solution_summary": analysis.get("solution_summary")
                        or lead.solution_summary,
                        "ai_analysis_json": json.dumps(
                            analysis, ensure_ascii=False, indent=2
                        ),
                        "ai_provider_status": status,
                        "ai_confidence": float(analysis.get("confidence") or 0.0),
                        "ai_last_analyzed_at": fields.Datetime.now(),
                        "ai_error_message": False,
                    }
                )
                if raw_response:
                    lead.message_post(
                        body=_("AI/API analyzed the requirement and updated this opportunity.")
                    )
            except Exception as error:
                fallback = lead._fallback_ai_analysis(source_text)
                lead.write(
                    {
                        "solution_type": fallback["solution_type"],
                        "requirements_summary": fallback["requirements_summary"],
                        "site_survey_required": fallback["site_survey_required"],
                        "solution_summary": fallback["solution_summary"],
                        "ai_analysis_json": json.dumps(
                            fallback, ensure_ascii=False, indent=2
                        ),
                        "ai_provider_status": "failed",
                        "ai_confidence": fallback["confidence"],
                        "ai_last_analyzed_at": fields.Datetime.now(),
                        "ai_error_message": str(error),
                    }
                )
        return True

    def action_sync_site_survey_calendar(self):
        calendar_id = self._config_param("google_calendar_id") or "primary"
        token = self._config_param("google_access_token")
        if not token:
            raise UserError(_("Google access token is not configured."))
        for lead in self:
            if not lead.site_survey_at:
                raise UserError(_("Please set the site survey schedule first."))
            start = fields.Datetime.to_datetime(lead.site_survey_at)
            stop = start + timedelta(hours=1)
            payload = {
                "summary": _("IT site survey - %s") % lead.name,
                "location": lead.site_address or "",
                "description": lead.requirements_summary or "",
                "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
                "end": {"dateTime": stop.isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
            }
            response = requests.post(
                "https://www.googleapis.com/calendar/v3/calendars/%s/events"
                % calendar_id,
                headers={
                    "Authorization": "Bearer %s" % token,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            event = response.json()
            lead.write(
                {
                    "calendar_event_id": event.get("id"),
                    "calendar_event_url": event.get("htmlLink"),
                    "calendar_synced_at": fields.Datetime.now(),
                }
            )
            lead.message_post(body=_("Site survey was synced to Google Calendar."))
        return True

    def _task_assignee(self, kind):
        self.ensure_one()
        if kind in ("site_survey", "solution_design"):
            return self.presales_user_id or self.user_id
        if kind == "approval":
            return self.manager_user_id or self.user_id
        return self.user_id

    def _create_it_task(self, kind, name, deadline=None):
        self.ensure_one()
        existing = self.env["project.task"].with_context(active_test=False).search(
            [("crm_lead_id", "=", self.id), ("it_task_kind", "=", kind)], limit=1
        )
        if existing:
            updates = {"name": name, "partner_id": self.partner_id.id}
            if deadline:
                updates["date_deadline"] = deadline
            assignee = self._task_assignee(kind)
            if assignee:
                updates["user_ids"] = [(6, 0, assignee.ids)]
            existing.write(updates)
            return existing
        values = {
            "name": name,
            "crm_lead_id": self.id,
            "it_task_kind": kind,
            "partner_id": self.partner_id.id,
            "date_deadline": deadline,
        }
        assignee = self._task_assignee(kind)
        if assignee:
            values["user_ids"] = [(6, 0, assignee.ids)]
        return self.env["project.task"].create(values)

    def _complete_it_tasks(self, kind, status="done"):
        self.ensure_one()
        tasks = self.it_task_ids.filtered(
            lambda task: task.it_task_kind == kind
            and task.it_status not in ("done", "cancelled")
        )
        values = {"it_status": status}
        if status == "done":
            values["it_completed_at"] = fields.Datetime.now()
        tasks.write(values)
        return tasks

    @api.model_create_multi
    def create(self, values_list):
        leads = super().create(values_list)
        if self.env.context.get("skip_initial_it_task"):
            return leads
        deadline = fields.Date.context_today(self) + timedelta(days=1)
        for lead in leads.filtered(lambda item: item.type == "opportunity"):
            self.env["it.operation.log"].log(lead, "create", {"consulting_state": lead.consulting_state})
            lead._create_it_task(
                "initial_contact",
                _("Liên hệ xác minh nhu cầu - %s") % lead.name,
                deadline,
            )
        return leads

    def write(self, values):
        result = super().write(values)
        for lead in self:
            if not self.env.context.get("skip_operation_log") and any(key in values for key in ("consulting_state", "approval_state", "user_id", "presales_user_id", "manager_user_id")):
                self.env["it.operation.log"].log(lead, "state" if "consulting_state" in values else "update", values)
            if values.get("site_survey_at"):
                survey_date = fields.Datetime.to_datetime(lead.site_survey_at).date()
                lead._create_it_task(
                    "site_survey",
                    _("Khảo sát hiện trạng - %s") % lead.name,
                    survey_date,
                )
            if values.get("quotation_sent_at"):
                sent_at = fields.Datetime.to_datetime(lead.quotation_sent_at)
                lead._create_it_task(
                    "quotation_followup",
                    _("Theo dõi báo giá - %s") % lead.name,
                    sent_at.date() + timedelta(days=2),
                )
        return result

    def action_view_it_tasks(self):
        self.ensure_one()
        action = self.env.ref("project.action_view_task").read()[0]
        action["domain"] = [("crm_lead_id", "=", self.id)]
        action["context"] = {
            "default_crm_lead_id": self.id,
            "default_partner_id": self.partner_id.id,
        }
        return action

    def action_view_consultations(self):
        self.ensure_one()
        action = self.env.ref("it_solution_crm.action_it_consultation_session").read()[0]
        action["domain"] = [("lead_id", "=", self.id)]
        action["context"] = {"default_lead_id": self.id}
        return action

    def action_confirm_requirements(self):
        for lead in self:
            if not lead.solution_type or not lead.requirements_summary:
                raise UserError(
                    _("Hãy nhập nhóm giải pháp và nhu cầu kỹ thuật trước khi xác minh.")
                )
            lead._complete_it_tasks("initial_contact")
            lead.consulting_state = "qualified"
            if lead.site_survey_required:
                if not lead.site_survey_at:
                    raise UserError(_("Hãy nhập lịch khảo sát hiện trạng."))
                lead.consulting_state = "survey"
                survey_date = fields.Datetime.to_datetime(lead.site_survey_at).date()
                lead._create_it_task(
                    "site_survey",
                    _("Khảo sát hiện trạng - %s") % lead.name,
                    survey_date,
                )
            else:
                lead.action_request_solution_design()
        return True

    @api.model
    def _create_it_solution_demo_data(self):
        project = self.env["project.project"].search(
            [("name", "=", "Demo - Tư vấn giải pháp CNTT")], limit=1
        )
        if not project:
            project = self.env["project.project"].search(
                [("name", "=", "Demo - Tu van giai phap CNTT")], limit=1
            )
        if not project:
            project = self.env["project.project"].create(
                {"name": "Demo - Tư vấn giải pháp CNTT"}
            )
        else:
            project.write({"name": "Demo - Tư vấn giải pháp CNTT"})

        def user(login, name, groups):
            record = self.env["res.users"].search([("login", "=", login)], limit=1)
            group_ids = [self.env.ref(xmlid).id for xmlid in groups]
            values = {
                "name": name,
                "login": login,
                "email": login,
                "groups_id": [(6, 0, group_ids)],
            }
            if record:
                record.write(values)
                return record
            return self.env["res.users"].create(values)

        sales = user(
            "demo.sales.it@itsolution.local",
            "Nguyễn Minh Anh - Sales IT",
            ["it_solution_crm.group_it_solution_user"],
        )
        presales = user(
            "demo.presales@itsolution.local",
            "Trần Hoàng Nam - Presales",
            ["it_solution_crm.group_it_solution_presales"],
        )
        manager = user(
            "demo.manager@itsolution.local",
            "Lê Thu Hà - Trưởng phòng",
            ["it_solution_crm.group_it_solution_manager"],
        )
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin_user:
            admin_user.write(
                {
                    "groups_id": [
                        (4, self.env.ref("it_solution_crm.group_it_solution_manager").id),
                    ]
                }
            )
        sales_2 = user(
            "demo.sales2.it@itsolution.local", "Phạm Quỳnh Trang - Tư vấn IT",
            ["it_solution_crm.group_it_solution_user"],
        )
        sales_3 = user(
            "demo.sales3.it@itsolution.local", "Vũ Đức Huy - Tư vấn IT",
            ["it_solution_crm.group_it_solution_user"],
        )
        presales_2 = user(
            "demo.presales2@itsolution.local", "Đặng Quốc Bảo - Presales",
            ["it_solution_crm.group_it_solution_presales"],
        )
        coordinator = user(
            "demo.coordinator@itsolution.local", "Bùi Ngọc Linh - Điều phối",
            ["it_solution_crm.group_it_solution_presales"],
        )

        employee_specs = [
            (sales, "NV-SALES-01", "Nguyễn Minh", "Anh", "1994-04-12", "Hà Nội", "0901123456"),
            (presales, "NV-KT-01", "Trần Hoàng", "Nam", "1991-09-03", "Đà Nẵng", "0902234567"),
            (manager, "NV-TP-01", "Lê Thu", "Hà", "1988-02-20", "TP.HCM", "0903345678"),
            (sales_2, "NV-SALES-02", "Phạm Quỳnh", "Trang", "1996-07-18", "Hải Phòng", "0904456789"),
            (sales_3, "NV-SALES-03", "Vũ Đức", "Huy", "1993-11-09", "Bắc Ninh", "0905567890"),
            (presales_2, "NV-KT-02", "Đặng Quốc", "Bảo", "1992-05-24", "Huế", "0906678901"),
            (coordinator, "NV-DP-01", "Bùi Ngọc", "Linh", "1995-08-30", "Hà Nội", "0907789012"),
        ]
        don_vi_kinh_doanh = self.env["don_vi"].search([("ma_don_vi", "=", "KD-IT")], limit=1)
        if not don_vi_kinh_doanh:
            don_vi_kinh_doanh = self.env["don_vi"].create(
                {"ma_don_vi": "KD-IT", "ten_don_vi": "Phòng Kinh doanh giải pháp IT"}
            )
        don_vi_ky_thuat = self.env["don_vi"].search([("ma_don_vi", "=", "KT-GP")], limit=1)
        if not don_vi_ky_thuat:
            don_vi_ky_thuat = self.env["don_vi"].create(
                {"ma_don_vi": "KT-GP", "ten_don_vi": "Phòng Kỹ thuật Presales"}
            )
        chuc_vu_sales = self.env["chuc_vu"].search([("ma_chuc_vu", "=", "CV-SALES")], limit=1)
        if not chuc_vu_sales:
            chuc_vu_sales = self.env["chuc_vu"].create(
                {"ma_chuc_vu": "CV-SALES", "ten_chuc_vu": "Chuyên viên kinh doanh IT"}
            )
        chuc_vu_presales = self.env["chuc_vu"].search([("ma_chuc_vu", "=", "CV-PRESALES")], limit=1)
        if not chuc_vu_presales:
            chuc_vu_presales = self.env["chuc_vu"].create(
                {"ma_chuc_vu": "CV-PRESALES", "ten_chuc_vu": "Kỹ sư Presales"}
            )
        chuc_vu_manager = self.env["chuc_vu"].search([("ma_chuc_vu", "=", "CV-TP")], limit=1)
        if not chuc_vu_manager:
            chuc_vu_manager = self.env["chuc_vu"].create(
                {"ma_chuc_vu": "CV-TP", "ten_chuc_vu": "Trưởng phòng giải pháp IT"}
            )
        cert_sales = self.env["chung_chi_bang_cap"].search([("ma_chung_chi_bang_cap", "=", "CERT-CRM")], limit=1)
        if not cert_sales:
            cert_sales = self.env["chung_chi_bang_cap"].create(
                {"ma_chung_chi_bang_cap": "CERT-CRM", "ten_chung_chi_bang_cap": "Chứng chỉ tư vấn CRM và bán hàng B2B"}
            )
        cert_network = self.env["chung_chi_bang_cap"].search([("ma_chung_chi_bang_cap", "=", "CERT-NET")], limit=1)
        if not cert_network:
            cert_network = self.env["chung_chi_bang_cap"].create(
                {"ma_chung_chi_bang_cap": "CERT-NET", "ten_chung_chi_bang_cap": "Chứng chỉ mạng doanh nghiệp CCNA"}
            )

        employee_role_map = {
            "NV-SALES-01": (don_vi_kinh_doanh, chuc_vu_sales, cert_sales),
            "NV-KT-01": (don_vi_ky_thuat, chuc_vu_presales, cert_network),
            "NV-TP-01": (don_vi_kinh_doanh, chuc_vu_manager, cert_sales),
            "NV-SALES-02": (don_vi_kinh_doanh, chuc_vu_sales, cert_sales),
            "NV-SALES-03": (don_vi_kinh_doanh, chuc_vu_sales, cert_sales),
            "NV-KT-02": (don_vi_ky_thuat, chuc_vu_presales, cert_network),
            "NV-DP-01": (don_vi_ky_thuat, chuc_vu_presales, cert_network),
        }

        for user_record, code, last_name, first_name, birthday, hometown, phone in employee_specs:
            employee = self.env["nhan_vien"].search(
                ["|", ("ma_dinh_danh", "=", code), ("user_id", "=", user_record.id)], limit=1
            )
            values = {
                "ma_dinh_danh": code,
                "ho_ten_dem": last_name,
                "ten": first_name,
                "ngay_sinh": birthday,
                "que_quan": hometown,
                "email": user_record.email,
                "so_dien_thoai": phone,
                "user_id": user_record.id,
            }
            if employee:
                employee.write(values)
            else:
                employee = self.env["nhan_vien"].create(values)
            don_vi, chuc_vu, cert = employee_role_map[code]
            history = self.env["lich_su_cong_tac"].search(
                [("nhan_vien_id", "=", employee.id), ("chuc_vu_id", "=", chuc_vu.id)],
                limit=1,
            )
            history_values = {
                "nhan_vien_id": employee.id,
                "don_vi_id": don_vi.id,
                "chuc_vu_id": chuc_vu.id,
                "loai_chuc_vu": "Chính",
            }
            if history:
                history.write(history_values)
            else:
                self.env["lich_su_cong_tac"].create(history_values)
            cert_line = self.env["danh_sach_chung_chi_bang_cap"].search(
                [
                    ("nhan_vien_id", "=", employee.id),
                    ("chung_chi_bang_cap_id", "=", cert.id),
                ],
                limit=1,
            )
            cert_values = {
                "nhan_vien_id": employee.id,
                "chung_chi_bang_cap_id": cert.id,
                "ghi_chu": "Dữ liệu demo gắn với nghiệp vụ QLKH/QLCV IT",
            }
            if cert_line:
                cert_line.write(cert_values)
            else:
                self.env["danh_sach_chung_chi_bang_cap"].create(cert_values)

        today = fields.Date.context_today(self)
        now = fields.Datetime.now()

        def partner(name, phone):
            record = self.env["res.partner"].search([("phone", "=", phone)], limit=1)
            if not record:
                record = self.env["res.partner"].search([("name", "=", name)], limit=1)
            values = {"name": name, "phone": phone, "is_company": True}
            if record:
                record.write(values)
                return record
            return self.env["res.partner"].create(values)

        def lead(values):
            legacy_names = values.pop("_legacy_names", [])
            record = self.search([("name", "=", values["name"])], limit=1)
            if not record and legacy_names:
                record = self.search([("name", "in", legacy_names)], limit=1)
            if record:
                record.write(values)
                return record
            return self.with_context(skip_initial_it_task=True).create(values)

        def task(lead_record, kind, name, user_record, deadline, status="pending", completed=False):
            record = self.env["project.task"].search(
                [("crm_lead_id", "=", lead_record.id), ("it_task_kind", "=", kind)],
                limit=1,
            )
            values = {
                "name": name,
                "project_id": project.id,
                "crm_lead_id": lead_record.id,
                "it_task_kind": kind,
                "partner_id": lead_record.partner_id.id,
                "date_deadline": deadline,
                "user_ids": [(6, 0, user_record.ids)],
                "it_status": status,
                "it_completed_at": completed or False,
            }
            if record:
                record.write(values)
                return record
            return self.env["project.task"].create(values)

        vietcare = partner("Công ty Cổ phần Phòng khám ViệtCare", "02873000001")
        lead_vietcare = lead(
            {
                "name": "Demo - Wi-Fi 6 cho chuỗi phòng khám ViệtCare",
                "_legacy_names": ["Demo - Wi-Fi 6 cho chuoi phong kham VietCare"],
                "type": "opportunity",
                "partner_id": vietcare.id,
                "user_id": sales.id,
                "presales_user_id": presales.id,
                "manager_user_id": manager.id,
                "solution_type": "network",
                "requirements_summary": "4 phòng khám, 120 người dùng, cần Wi-Fi khách riêng và roaming ổn định.",
                "site_address": "Quận 3, TP.HCM",
                "site_survey_required": True,
                "site_survey_at": now - timedelta(days=18),
                "solution_summary": "<p>Đề xuất gateway, controller cloud và 12 AP Wi-Fi 6 tách VLAN nội bộ/khách.</p>",
                "approval_state": "approved",
                "consulting_state": "won",
                "probability": 100,
                "quotation_sent_at": now - timedelta(days=13),
                "ai_provider_status": "success",
                "ai_confidence": 0.89,
                "ai_last_analyzed_at": now - timedelta(days=21),
            }
        )
        for kind, title, owner, due, done in [
            ("initial_contact", "Liên hệ xác minh nhu cầu - ViệtCare", sales, -21, -21),
            ("site_survey", "Khảo sát hiện trạng - ViệtCare", presales, -18, -18),
            ("solution_design", "Thiết kế giải pháp Wi-Fi 6 - ViệtCare", presales, -16, -16),
            ("approval", "Phê duyệt phương án - ViệtCare", manager, -14, -14),
            ("quotation", "Lập và gửi báo giá - ViệtCare", sales, -13, -13),
            ("quotation_followup", "Theo dõi báo giá - ViệtCare", sales, -11, -11),
            ("handover", "Bàn giao hồ sơ kỹ thuật - ViệtCare", presales, -10, -10),
        ]:
            task(lead_vietcare, kind, title, owner, today + timedelta(days=due), "done", now + timedelta(days=done))

        anphu = partner("Nhà máy Thực phẩm An Phú", "02743700002")
        lead_anphu = lead(
            {
                "name": "Demo - Camera CCTV nhà xưởng An Phú Foods",
                "_legacy_names": ["Demo - Camera CCTV nha xuong An Phu Foods"],
                "type": "opportunity",
                "partner_id": anphu.id,
                "user_id": sales_2.id,
                "presales_user_id": presales_2.id,
                "manager_user_id": manager.id,
                "solution_type": "camera",
                "requirements_summary": "Nhà xưởng 2 tầng, 32 camera, lưu trữ 30 ngày, xem tập trung từ văn phòng.",
                "site_address": "KCN VSIP 2, Bình Dương",
                "site_survey_required": True,
                "site_survey_at": now - timedelta(days=8),
                "solution_summary": "<p>32 IP camera PoE, 2 NVR, switch PoE riêng và VLAN camera.</p>",
                "approval_state": "approved",
                "consulting_state": "quotation",
                "quotation_sent_at": now - timedelta(days=1),
                "ai_provider_status": "fallback",
                "ai_confidence": 0.62,
                "ai_last_analyzed_at": now - timedelta(days=10),
            }
        )
        for kind, title, owner, due, status, done in [
            ("initial_contact", "Liên hệ xác minh nhu cầu - An Phú Foods", sales_2, -10, "done", -10),
            ("site_survey", "Khảo sát nhà xưởng - An Phú Foods", presales_2, -8, "done", -8),
            ("solution_design", "Thiết kế CCTV - An Phú Foods", presales_2, -6, "done", -6),
            ("approval", "Phê duyệt phương án CCTV - An Phú Foods", manager, -4, "done", -4),
            ("quotation", "Gửi báo giá CCTV - An Phú Foods", sales_2, -1, "done", -1),
            ("quotation_followup", "Theo dõi báo giá CCTV - An Phú Foods", sales_2, 1, "pending", False),
        ]:
            task(lead_anphu, kind, title, owner, today + timedelta(days=due), status, now + timedelta(days=done) if done else False)

        logistics = partner("Công ty Logistics Minh Long", "02873000003")
        lead_logistics = lead(
            {
                "name": "Demo - Server và NAS backup cho Logistics Minh Long",
                "_legacy_names": ["Demo - Server va NAS backup cho Minh Long Logistics"],
                "type": "opportunity",
                "partner_id": logistics.id,
                "user_id": sales_3.id,
                "presales_user_id": presales.id,
                "manager_user_id": manager.id,
                "solution_type": "server",
                "requirements_summary": "Cần máy chủ file, NAS backup 20TB, phân quyền theo phòng ban và lịch backup hằng đêm.",
                "site_address": "Quận Bình Thạnh, TP.HCM",
                "site_survey_required": True,
                "site_survey_at": now - timedelta(days=3),
                "solution_summary": "<p>01 server file, 01 NAS RAID6, chính sách backup 3-2-1 và phân quyền AD.</p>",
                "approval_state": "pending",
                "consulting_state": "approval",
                "ai_provider_status": "success",
                "ai_confidence": 0.93,
                "ai_last_analyzed_at": now - timedelta(days=5),
            }
        )
        for kind, title, owner, due, status, done in [
            ("initial_contact", "Liên hệ xác minh nhu cầu - Minh Long", sales_3, -5, "done", -5),
            ("site_survey", "Khảo sát hạ tầng server - Minh Long", presales, -3, "done", -3),
            ("solution_design", "Thiết kế server NAS - Minh Long", presales, -1, "done", -1),
            ("approval", "Chờ phê duyệt phương án server NAS - Minh Long", manager, 0, "pending", False),
        ]:
            task(lead_logistics, kind, title, owner, today + timedelta(days=due), status, now + timedelta(days=done) if done else False)

        greenlake = partner("Khách sạn GreenLake Nha Trang", "02583700004")
        lead_greenlake = lead(
            {
                "name": "Demo - Nâng cấp Wi-Fi khách sạn GreenLake",
                "_legacy_names": ["Demo - Nang cap Wi-Fi khach san GreenLake"],
                "type": "opportunity",
                "partner_id": greenlake.id,
                "user_id": sales_2.id,
                "presales_user_id": presales_2.id,
                "manager_user_id": manager.id,
                "solution_type": "network",
                "requirements_summary": "Khách sạn 80 phòng, Wi-Fi yếu ở tầng 5-7, cần portal khách và tách mạng nội bộ.",
                "site_address": "Nha Trang, Khánh Hòa",
                "site_survey_required": True,
                "site_survey_at": now - timedelta(days=2),
                "approval_state": "draft",
                "consulting_state": "survey",
                "ai_provider_status": "fallback",
                "ai_confidence": 0.58,
                "ai_last_analyzed_at": now - timedelta(days=4),
            }
        )
        task(lead_greenlake, "initial_contact", "Liên hệ xác minh nhu cầu - GreenLake", sales_2, today - timedelta(days=4), "done", now - timedelta(days=4))
        task(lead_greenlake, "site_survey", "Khảo sát Wi-Fi khách sạn - GreenLake", presales_2, today - timedelta(days=2), "pending", False)

        dainam = partner("Công ty Văn phòng Đại Nam", "02873000005")
        lead_dainam = lead(
            {
                "name": "Demo - Gói bảo trì IT định kỳ Đại Nam Office",
                "_legacy_names": ["Demo - Goi bao tri IT dinh ky Dai Nam Office"],
                "type": "opportunity",
                "partner_id": dainam.id,
                "user_id": sales_3.id,
                "presales_user_id": presales.id,
                "manager_user_id": manager.id,
                "solution_type": "maintenance",
                "requirements_summary": "50 máy tính văn phòng, cần bảo trì định kỳ, hotline hỗ trợ và SLA xử lý sự cố.",
                "site_survey_required": False,
                "approval_state": "draft",
                "consulting_state": "solution",
                "solution_summary": "<p>Gói bảo trì 2 lần/tháng, remote support giờ hành chính, onsite trong 8h.</p>",
                "ai_provider_status": "fallback",
                "ai_confidence": 0.57,
                "ai_last_analyzed_at": now - timedelta(days=2),
            }
        )
        task(lead_dainam, "initial_contact", "Liên hệ xác minh nhu cầu - Đại Nam", sales_3, today - timedelta(days=2), "done", now - timedelta(days=2))
        task(lead_dainam, "solution_design", "Thiết kế gói bảo trì - Đại Nam", presales, today + timedelta(days=1), "in_progress", False)

        startup = partner("Công ty Công nghệ BlueStart", "02873000006")
        lead_startup = lead(
            {
                "name": "Demo - Thiết bị văn phòng BlueStart",
                "_legacy_names": ["Demo - Thiet bi van phong BlueStart"],
                "type": "opportunity",
                "partner_id": startup.id,
                "user_id": sales.id,
                "presales_user_id": presales.id,
                "manager_user_id": manager.id,
                "solution_type": "device",
                "requirements_summary": "Cần 20 laptop, 2 máy in mạng và gói cài đặt ban đầu cho nhân viên mới.",
                "site_survey_required": False,
                "approval_state": "draft",
                "consulting_state": "new",
                "ai_provider_status": "none",
            }
        )
        task(lead_startup, "initial_contact", "Liên hệ lần đầu - BlueStart", sales, today - timedelta(days=3), "pending", False)

        def consultation(code, lead_record, consultant, days_ago, channel, outcome, purchase, rating, need, advice):
            record = self.env["it.consultation.session"].search([("name", "=", code)], limit=1)
            values = {
                "name": code,
                "lead_id": lead_record.id,
                "consultant_user_id": consultant.id,
                "consulted_at": now - timedelta(days=days_ago),
                "channel": channel,
                "duration_minutes": 45 if channel in ("online", "onsite") else 25,
                "customer_need": need,
                "advice_summary": advice,
                "outcome": outcome,
                "purchase_outcome": purchase,
                "customer_rating": rating or False,
                "feedback_note": "Dữ liệu phản hồi được ghi nhận sau phiên tư vấn.",
                "state": "done",
            }
            if record:
                record.with_context(skip_operation_log=True).write(values)
                return record
            return self.env["it.consultation.session"].create(values)

        consultation("TV-DEMO-001", lead_vietcare, sales, 24, "phone", "followup", "pending", False, "Mạng thường mất kết nối giờ cao điểm.", "Thu thập số người dùng, sơ đồ tầng và hẹn khảo sát.")
        consultation("TV-DEMO-002", lead_vietcare, sales, 20, "onsite", "successful", "ordered", "5", "Cần roaming và tách VLAN khách.", "Chốt kiến trúc Wi-Fi 6 và phạm vi 12 access point.")
        consultation("TV-DEMO-003", lead_anphu, sales_2, 12, "online", "successful", "not_ordered", "4", "Camera 32 điểm, lưu 30 ngày.", "Phương án phù hợp; khách đang chờ duyệt ngân sách quý.")
        consultation("TV-DEMO-004", lead_anphu, sales_2, 3, "phone", "followup", "pending", False, "Cần làm rõ tiến độ phê duyệt.", "Hẹn gọi lại sau cuộc họp ban giám đốc.")
        consultation("TV-DEMO-005", lead_logistics, sales_3, 7, "onsite", "successful", "not_ordered", "5", "NAS 20TB và backup đêm.", "Khách xác nhận giải pháp kỹ thuật, chờ so sánh báo giá.")
        consultation("TV-DEMO-006", lead_greenlake, sales_2, 6, "phone", "followup", "pending", False, "Wi-Fi yếu tầng 5-7.", "Hẹn khảo sát đo phủ sóng tại khách sạn.")
        consultation("TV-DEMO-007", lead_greenlake, sales_2, 2, "onsite", "successful", "pending", "4", "Xác nhận vùng chết sóng và tải đồng thời.", "Đề xuất bố trí lại AP và captive portal.")
        consultation("TV-DEMO-008", lead_dainam, sales_3, 4, "online", "successful", "not_ordered", "5", "Gói bảo trì 50 máy và SLA.", "Khách hài lòng phạm vi dịch vụ nhưng chưa chốt ngân sách.")
        consultation("TV-DEMO-009", lead_startup, sales, 3, "email", "unsuitable", "rejected", "2", "20 laptop cấu hình cao trong ngân sách thấp.", "Giải thích chênh lệch cấu hình và đề xuất phương án thuê thiết bị.")

        def consulting_project(lead_record, members):
            record = self.env["project.project"].search([("crm_lead_id", "=", lead_record.id), ("is_it_consulting_project", "=", True)], limit=1)
            values = {
                "name": "Dự án - %s" % lead_record.partner_id.name,
                "partner_id": lead_record.partner_id.id,
                "crm_lead_id": lead_record.id,
                "is_it_consulting_project": True,
                "team_member_ids": [(6, 0, members.ids)],
            }
            if record:
                record.write(values)
            else:
                record = self.env["project.project"].create(values)
            lead_record.it_task_ids.write({"project_id": record.id})
            return record

        consulting_project(lead_vietcare, sales | presales | manager | coordinator)
        consulting_project(lead_anphu, sales_2 | presales_2 | manager)
        consulting_project(lead_logistics, sales_3 | presales | manager)
        consulting_project(lead_greenlake, sales_2 | presales_2 | coordinator)
        consulting_project(lead_dainam, sales_3 | presales | coordinator)
        consulting_project(lead_startup, sales | coordinator)

        return True

    def action_request_solution_design(self):
        deadline = fields.Date.context_today(self) + timedelta(days=2)
        for lead in self:
            if not lead.requirements_summary:
                raise UserError(
                    _("Hãy hoàn thiện nhu cầu kỹ thuật trước khi thiết kế giải pháp.")
                )
            lead.consulting_state = "solution"
            lead._create_it_task(
                "solution_design",
                _("Thiết kế giải pháp - %s") % lead.name,
                deadline,
            )
        return True

    def action_submit_for_approval(self):
        deadline = fields.Date.context_today(self) + timedelta(days=1)
        for lead in self:
            if not lead.solution_summary:
                raise UserError(_("Hãy nhập phương án kỹ thuật trước khi gửi phê duyệt."))
            if not lead.manager_user_id:
                raise UserError(_("Hãy chọn trưởng phòng phê duyệt."))
            lead.write({"consulting_state": "approval", "approval_state": "pending"})
            approval_task = lead._create_it_task(
                "approval",
                _("Phê duyệt phương án - %s") % lead.name,
                deadline,
            )
            approval_task.write({"it_status": "pending", "it_completed_at": False})
        return True

    def action_approve_solution(self):
        if not self.env.user.has_group("it_solution_crm.group_it_solution_manager"):
            raise UserError(_("Chỉ quản lý tư vấn giải pháp IT được phê duyệt."))
        for lead in self:
            if lead.approval_state != "pending":
                raise UserError(_("Phương án chưa ở trạng thái chờ phê duyệt."))
            if lead.manager_user_id != self.env.user:
                raise UserError(_("Bạn không phải trưởng phòng được chỉ định cho cơ hội này."))
            lead.write(
                {
                    "approval_state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                }
            )
            lead._complete_it_tasks("approval")
            lead._create_it_task(
                "quotation",
                _("Lập và gửi báo giá - %s") % lead.name,
                fields.Date.context_today(lead) + timedelta(days=1),
            )
        return True

    def action_reject_solution(self):
        if not self.env.user.has_group("it_solution_crm.group_it_solution_manager"):
            raise UserError(_("Chỉ quản lý tư vấn giải pháp IT được từ chối phương án."))
        for lead in self:
            if not lead.approval_note:
                raise UserError(_("Hãy nhập ý kiến trước khi từ chối phương án."))
            if lead.manager_user_id != self.env.user:
                raise UserError(_("Bạn không phải trưởng phòng được chỉ định cho cơ hội này."))
            lead.write({"approval_state": "rejected", "consulting_state": "solution"})
            lead._complete_it_tasks("approval", status="cancelled")
            revision_task = lead._create_it_task(
                "solution_design",
                _("Điều chỉnh phương án - %s") % lead.name,
                fields.Date.context_today(lead) + timedelta(days=1),
            )
            revision_task.write({"it_status": "pending", "it_completed_at": False})
        return True

    def action_mark_quotation_sent(self):
        for lead in self:
            if lead.approval_state != "approved":
                raise UserError(_("Phương án phải được phê duyệt trước khi gửi báo giá."))
            lead.write(
                {
                    "quotation_sent_at": fields.Datetime.now(),
                    "consulting_state": "quotation",
                }
            )
            lead._complete_it_tasks("quotation")
        return True

    def action_confirm_customer_acceptance(self):
        for lead in self:
            if not lead.quotation_sent_at:
                raise UserError(_("Chưa ghi nhận thời điểm gửi báo giá."))
            lead.write({"consulting_state": "won", "probability": 100})
            lead._complete_it_tasks("quotation_followup")
            lead._create_it_task(
                "handover",
                _("Bàn giao hồ sơ cho kỹ thuật - %s") % lead.name,
                fields.Date.context_today(lead) + timedelta(days=1),
            )
        return True
