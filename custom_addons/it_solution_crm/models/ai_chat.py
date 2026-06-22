import json
import unicodedata

import requests
from markupsafe import Markup, escape

from odoo import _, fields, models
from odoo.exceptions import UserError


class ItSolutionAiChat(models.TransientModel):
    _name = "it.solution.ai.chat"
    _description = "Trợ lý AI hỏi nhanh dữ liệu QLKH và QLCV"

    question = fields.Char("Câu hỏi")
    answer = fields.Html("Câu trả lời", readonly=True)
    conversation_html = fields.Html("Lịch sử hội thoại", readonly=True)
    provider_status = fields.Selection(
        [
            ("local", "Dữ liệu nội bộ"),
            ("success", "LLM/API ngoài"),
            ("failed", "API lỗi - dùng dữ liệu nội bộ"),
        ],
        string="Nguồn trả lời",
        default="local",
        readonly=True,
    )
    context_json = fields.Text("Ngữ cảnh nghiệp vụ đã dùng", readonly=True)
    message_count = fields.Integer("Số câu đã hỏi", default=0, readonly=True)

    def _config_param(self, key):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("it_solution_crm.%s" % key)
        )

    @staticmethod
    def _normalize(text):
        value = unicodedata.normalize("NFD", (text or "").lower())
        return "".join(char for char in value if unicodedata.category(char) != "Mn")

    @staticmethod
    def _selection_label(record, field_name, value):
        return dict(record._fields[field_name].selection).get(value, value or "Chưa xác định")

    def _build_business_context(self):
        leads = self.env["crm.lead"].search(
            [("type", "=", "opportunity"), ("solution_type", "!=", False)],
            order="write_date desc",
        )
        tasks = self.env["project.task"].search(
            [("it_task_kind", "!=", False)], order="date_deadline asc, id desc"
        )
        employees = self.env["nhan_vien"].search([])

        state_counts = {}
        for lead in leads:
            label = self._selection_label(lead, "consulting_state", lead.consulting_state)
            state_counts[label] = state_counts.get(label, 0) + 1

        task_counts = {}
        sla_counts = {}
        for task in tasks:
            status_label = self._selection_label(task, "it_status", task.it_status)
            sla_label = self._selection_label(task, "sla_status", task.sla_status)
            task_counts[status_label] = task_counts.get(status_label, 0) + 1
            sla_counts[sla_label] = sla_counts.get(sla_label, 0) + 1

        overdue_tasks = tasks.filtered(lambda item: item.sla_status == "overdue")[:8]
        pending_approvals = leads.filtered(
            lambda item: item.approval_state == "pending"
        )[:8]

        return {
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "summary": {
                "opportunity_count": len(leads),
                "expected_revenue": sum(leads.mapped("expected_revenue")),
                "task_count": len(tasks),
                "employee_count": len(employees),
                "opportunity_states": state_counts,
                "task_states": task_counts,
                "sla_states": sla_counts,
            },
            "pending_approvals": [
                {
                    "opportunity": lead.name,
                    "customer": lead.partner_id.display_name,
                    "manager": lead.manager_user_id.display_name,
                }
                for lead in pending_approvals
            ],
            "overdue_tasks": [
                {
                    "task": task.name,
                    "opportunity": task.crm_lead_id.name,
                    "assignees": ", ".join(task.user_ids.mapped("name")),
                    "deadline": fields.Date.to_string(task.date_deadline)
                    if task.date_deadline
                    else "",
                }
                for task in overdue_tasks
            ],
            "opportunities": [
                {
                    "name": lead.name,
                    "customer": lead.partner_id.display_name,
                    "state": self._selection_label(
                        lead, "consulting_state", lead.consulting_state
                    ),
                    "solution_type": self._selection_label(
                        lead, "solution_type", lead.solution_type
                    ),
                    "expected_revenue": lead.expected_revenue,
                    "salesperson": lead.user_id.display_name,
                    "presales": lead.presales_user_id.display_name,
                    "manager": lead.manager_user_id.display_name,
                }
                for lead in leads[:12]
            ],
        }

    @staticmethod
    def _format_money(amount):
        return ("{:,.0f}".format(amount or 0)).replace(",", ".")

    def _find_mentioned_opportunity(self, question, opportunities):
        normalized_question = self._normalize(question)
        for opportunity in opportunities:
            candidates = (opportunity["name"], opportunity["customer"])
            for candidate in candidates:
                normalized_candidate = self._normalize(candidate)
                important_words = [
                    word
                    for word in normalized_candidate.split()
                    if len(word) >= 5 and word not in ("cong", "demo", "khach")
                ]
                if any(word in normalized_question for word in important_words):
                    return opportunity
        return False

    def _local_answer(self, question, context):
        normalized = self._normalize(question)
        summary = context["summary"]
        opportunity = self._find_mentioned_opportunity(
            question, context["opportunities"]
        )

        if opportunity and any(
            phrase in normalized
            for phrase in ("phu trach", "ai lam", "sales", "presales", "trang thai")
        ):
            return _(
                "<p><b>%s</b> đang ở bước <b>%s</b>.</p>"
                "<ul><li>Sales: %s</li><li>Presales: %s</li>"
                "<li>Trưởng phòng: %s</li></ul>"
            ) % (
                escape(opportunity["name"]),
                escape(opportunity["state"]),
                escape(opportunity["salesperson"] or "Chưa phân công"),
                escape(opportunity["presales"] or "Chưa phân công"),
                escape(opportunity["manager"] or "Chưa phân công"),
            )

        if "qua han" in normalized or "tre han" in normalized:
            items = context["overdue_tasks"]
            details = "".join(
                "<li>%s - %s - hạn %s</li>"
                % (
                    escape(item["task"]),
                    escape(item["assignees"] or "Chưa phân công"),
                    escape(item["deadline"] or "Chưa có"),
                )
                for item in items
            )
            return _("<p>Có <b>%s công việc quá hạn</b>.</p><ul>%s</ul>") % (
                summary["sla_states"].get("Quá hạn", 0),
                details or "<li>Không có công việc quá hạn.</li>",
            )

        if "phe duyet" in normalized or "cho duyet" in normalized:
            items = context["pending_approvals"]
            details = "".join(
                "<li>%s - người duyệt: %s</li>"
                % (
                    escape(item["opportunity"]),
                    escape(item["manager"] or "Chưa phân công"),
                )
                for item in items
            )
            return _("<p>Có <b>%s cơ hội chờ phê duyệt</b>.</p><ul>%s</ul>") % (
                len(items),
                details or "<li>Không có cơ hội đang chờ phê duyệt.</li>",
            )

        if "doanh thu" in normalized or "gia tri" in normalized:
            return _(
                "<p>Tổng doanh thu kỳ vọng hiện tại là <b>%s</b> "
                "trên <b>%s cơ hội</b>.</p>"
            ) % (
                self._format_money(summary["expected_revenue"]),
                summary["opportunity_count"],
            )

        if "cong viec" in normalized or "task" in normalized:
            states = ", ".join(
                "%s: %s" % (escape(label), count)
                for label, count in summary["task_states"].items()
            )
            return _("<p>Có <b>%s công việc IT</b>. %s.</p>") % (
                summary["task_count"],
                states,
            )

        if "co hoi" in normalized or "khach hang" in normalized:
            states = ", ".join(
                "%s: %s" % (escape(label), count)
                for label, count in summary["opportunity_states"].items()
            )
            return _("<p>Có <b>%s cơ hội tư vấn IT</b>. %s.</p>") % (
                summary["opportunity_count"],
                states,
            )

        return _(
            "<p><b>Tóm tắt nhanh:</b> %s cơ hội, %s công việc IT, %s nhân viên HRM, "
            "%s công việc quá hạn.</p>"
            "<p>Bạn có thể hỏi: 'Công việc nào quá hạn?', 'Cơ hội nào chờ phê duyệt?', "
            "'Ai phụ trách GreenLake?' hoặc 'Tổng doanh thu kỳ vọng?'.</p>"
        ) % (
            summary["opportunity_count"],
            summary["task_count"],
            summary["employee_count"],
            summary["sla_states"].get("Quá hạn", 0),
        )

    def _call_llm(self, question, context):
        endpoint = self._config_param("ai_endpoint")
        api_key = self._config_param("ai_api_key")
        model = self._config_param("ai_model") or "gpt-4o-mini"
        if not endpoint or not api_key:
            return False

        payload = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý quản trị phòng tư vấn giải pháp IT. Chỉ trả lời "
                        "bằng dữ liệu JSON được cung cấp, không suy đoán. Trả lời tiếng Việt "
                        "ngắn gọn, nêu số liệu và tên bản ghi liên quan."
                    ),
                },
                {
                    "role": "user",
                    "content": "Câu hỏi: %s\nDữ liệu nghiệp vụ: %s"
                    % (question, json.dumps(context, ensure_ascii=False)),
                },
            ],
        }
        response = requests.post(
            endpoint,
            headers={
                "Authorization": "Bearer %s" % api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content")

    @staticmethod
    def _plain_text_to_html(text):
        return Markup("<p>%s</p>") % escape(text or "").replace("\n", Markup("<br/>"))

    def action_ask(self):
        self.ensure_one()
        question = (self.question or "").strip()
        if not question:
            raise UserError(_("Hãy nhập câu hỏi cần tra cứu."))

        context = self._build_business_context()
        provider_status = "local"
        try:
            llm_answer = self._call_llm(question, context)
            if llm_answer:
                answer = self._plain_text_to_html(llm_answer)
                provider_status = "success"
            else:
                answer = self._local_answer(question, context)
        except Exception:
            answer = self._local_answer(question, context)
            provider_status = "failed"

        history = Markup(self.conversation_html or "")
        history += Markup(
            '<div class="alert alert-secondary"><b>Bạn:</b> %s</div>'
        ) % escape(question)
        history += Markup(
            '<div class="alert alert-info"><b>Trợ lý:</b> %s</div>'
        ) % Markup(answer)
        self.write(
            {
                "question": False,
                "answer": answer,
                "conversation_html": history,
                "provider_status": provider_status,
                "context_json": json.dumps(context, ensure_ascii=False, indent=2),
                "message_count": self.message_count + 1,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_clear(self):
        self.write(
            {
                "question": False,
                "answer": False,
                "conversation_html": False,
                "provider_status": "local",
                "context_json": False,
                "message_count": 0,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
