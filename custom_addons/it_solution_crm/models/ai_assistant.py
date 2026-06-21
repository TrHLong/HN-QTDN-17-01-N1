import json

from odoo import _, fields, models


class ItSolutionAiAssistant(models.TransientModel):
    _name = "it.solution.ai.assistant"
    _description = "Trợ lý AI nội bộ tư vấn giải pháp IT"

    customer_note = fields.Text(
        "Nội dung trao đổi với khách hàng",
        required=True,
        default=(
            "Khách hàng có 80 nhân sự, Wi-Fi tầng 4 yếu, cần tách mạng khách "
            "và mạng nội bộ, muốn có báo giá trong tuần này."
        ),
    )
    result_summary = fields.Html("Kết quả phân tích", readonly=True)
    solution_type = fields.Selection(
        selection=lambda self: self.env["crm.lead"]._fields["solution_type"].selection,
        string="Nhóm giải pháp đề xuất",
        readonly=True,
    )
    site_survey_required = fields.Boolean("Cần khảo sát hiện trạng", readonly=True)
    confidence = fields.Float("Độ tin cậy AI", readonly=True)
    provider_status = fields.Selection(
        [
            ("fallback", "AI nội bộ mô phỏng"),
            ("success", "LLM/API ngoài"),
            ("failed", "API lỗi, dùng AI nội bộ"),
        ],
        string="Nguồn xử lý",
        readonly=True,
    )
    raw_json = fields.Text("JSON nghiệp vụ", readonly=True)

    def action_analyze(self):
        self.ensure_one()
        lead_model = self.env["crm.lead"]
        try:
            analysis, status, raw_response = lead_model._call_ai_analysis_api(
                self.customer_note
            )
            provider_status = status if raw_response else "fallback"
        except Exception as error:
            analysis = lead_model._fallback_ai_analysis(self.customer_note)
            analysis["error"] = str(error)
            provider_status = "failed"

        solution_type = analysis.get("solution_type") or "other"
        valid_types = dict(lead_model._fields["solution_type"].selection)
        if solution_type not in valid_types:
            solution_type = "other"

        self.write(
            {
                "solution_type": solution_type,
                "site_survey_required": bool(analysis.get("site_survey_required")),
                "confidence": float(analysis.get("confidence") or 0.0),
                "provider_status": provider_status,
                "result_summary": _(
                    "<p><b>Nhóm giải pháp:</b> %s</p>"
                    "<p><b>Nhu cầu tóm tắt:</b> %s</p>"
                    "<p><b>Gợi ý xử lý:</b> %s</p>"
                )
                % (
                    valid_types.get(solution_type, solution_type),
                    analysis.get("requirements_summary") or self.customer_note,
                    analysis.get("solution_summary") or "",
                ),
                "raw_json": json.dumps(analysis, ensure_ascii=False, indent=2),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }
