from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def raise_for_status(self):
        return True

    def json(self):
        return self.payload


class TestCrmAutomation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env.user.write(
            {
                "groups_id": [
                    (4, self.env.ref("it_solution_crm.group_it_solution_manager").id)
                ]
            }
        )
        self.employee = self.env["nhan_vien"].create(
            {
                "ma_dinh_danh": "test-sales-it",
                "ho_ten_dem": "Nguyễn Văn",
                "ten": "Test",
                "ngay_sinh": "1995-01-01",
                "user_id": self.env.user.id,
            }
        )
        self.partner = self.env["res.partner"].create(
            {"name": "Công ty khách hàng kiểm thử"}
        )

    def _create_lead(self):
        return self.env["crm.lead"].create(
            {
                "name": "Triển khai Wi-Fi văn phòng",
                "type": "opportunity",
                "partner_id": self.partner.id,
                "user_id": self.env.user.id,
                "solution_type": "network",
                "requirements_summary": "Wi-Fi ổn định cho 50 nhân viên",
                "presales_user_id": self.env.user.id,
                "manager_user_id": self.env.user.id,
            }
        )

    def test_new_opportunity_creates_initial_contact_task(self):
        lead = self._create_lead()

        task = lead.it_task_ids.filtered(
            lambda item: item.it_task_kind == "initial_contact"
        )
        self.assertEqual(len(task), 1)
        self.assertEqual(task.crm_lead_id, lead)
        self.assertEqual(task.partner_id, self.partner)
        self.assertIn(self.env.user, task.user_ids)
        self.assertEqual(lead.hr_employee_id, self.employee)

    def test_survey_trigger_is_idempotent(self):
        lead = self._create_lead()
        survey_at = fields.Datetime.now() + timedelta(days=3)

        lead.write({"site_survey_required": True, "site_survey_at": survey_at})
        lead.write({"site_survey_at": survey_at + timedelta(hours=1)})

        tasks = lead.it_task_ids.filtered(
            lambda item: item.it_task_kind == "site_survey"
        )
        self.assertEqual(len(tasks), 1)

    def test_quotation_trigger_sets_two_day_follow_up(self):
        lead = self._create_lead()
        sent_at = fields.Datetime.now()

        lead.write({"quotation_sent_at": sent_at})

        task = lead.it_task_ids.filtered(
            lambda item: item.it_task_kind == "quotation_followup"
        )
        self.assertEqual(len(task), 1)
        self.assertEqual(task.date_deadline, sent_at.date() + timedelta(days=2))

    def test_full_presales_workflow_creates_expected_tasks(self):
        lead = self._create_lead()

        lead.action_confirm_requirements()
        self.assertEqual(lead.consulting_state, "solution")
        self.assertEqual(
            len(lead.it_task_ids.filtered(lambda task: task.it_task_kind == "solution_design")),
            1,
        )

        lead.solution_summary = "Hai access point Wi-Fi 6 và một gateway quản trị."
        lead.action_submit_for_approval()
        self.assertEqual(lead.approval_state, "pending")

        lead.action_approve_solution()
        self.assertEqual(lead.approval_state, "approved")
        self.assertEqual(
            len(lead.it_task_ids.filtered(lambda task: task.it_task_kind == "quotation")),
            1,
        )

        lead.action_mark_quotation_sent()
        self.assertEqual(lead.consulting_state, "quotation")
        lead.action_confirm_customer_acceptance()
        self.assertEqual(lead.consulting_state, "won")
        self.assertEqual(
            len(lead.it_task_ids.filtered(lambda task: task.it_task_kind == "handover")),
            1,
        )

    def test_completing_survey_creates_solution_design_task(self):
        lead = self._create_lead()
        lead.write(
            {
                "site_survey_required": True,
                "site_survey_at": fields.Datetime.now() + timedelta(days=2),
            }
        )
        lead.action_confirm_requirements()

        survey_task = lead.it_task_ids.filtered(
            lambda task: task.it_task_kind == "site_survey"
        )
        survey_task.action_complete_it_task()

        self.assertEqual(survey_task.it_status, "done")
        self.assertEqual(lead.consulting_state, "solution")
        self.assertEqual(
            len(lead.it_task_ids.filtered(lambda task: task.it_task_kind == "solution_design")),
            1,
        )

    def test_overdue_cron_schedules_one_alert(self):
        lead = self._create_lead()
        task = lead.it_task_ids.filtered(
            lambda item: item.it_task_kind == "initial_contact"
        )
        task.date_deadline = fields.Date.context_today(task) - timedelta(days=1)

        self.env["project.task"]._cron_schedule_overdue_alerts()
        self.env["project.task"]._cron_schedule_overdue_alerts()

        self.assertTrue(task.sla_alerted)
        self.assertEqual(task.sla_status, "overdue")
        activities = task.activity_ids.filtered(
            lambda activity: activity.summary == "Công việc tư vấn IT đã quá hạn"
        )
        self.assertEqual(len(activities), 1)

    def test_ai_analysis_uses_local_fallback_without_api_config(self):
        lead = self._create_lead()
        lead.write(
            {
                "ai_requirement_input": "Khach can Wi-Fi on dinh cho van phong 80 nguoi"
            }
        )

        lead.action_ai_analyze_requirement()

        self.assertEqual(lead.solution_type, "network")
        self.assertEqual(lead.ai_provider_status, "fallback")
        self.assertTrue(lead.site_survey_required)

    def test_ai_analysis_calls_configured_external_api(self):
        lead = self._create_lead()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("it_solution_crm.ai_endpoint", "https://ai.example.test/chat")
        params.set_param("it_solution_crm.ai_api_key", "test-key")
        ai_payload = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"solution_type":"server","requirements_summary":"Server NAS",'
                            '"site_survey_required":true,'
                            '"solution_summary":"<p>NAS + backup</p>",'
                            '"confidence":0.91}'
                        )
                    }
                }
            ]
        }

        with patch(
            "odoo.addons.it_solution_crm.models.crm_lead.requests.post",
            return_value=FakeResponse(ai_payload),
        ) as post:
            lead.action_ai_analyze_requirement()

        self.assertTrue(post.called)
        self.assertEqual(lead.solution_type, "server")
        self.assertEqual(lead.ai_provider_status, "success")
        self.assertAlmostEqual(lead.ai_confidence, 0.91)

    def test_google_calendar_sync_posts_site_survey_event(self):
        lead = self._create_lead()
        lead.write(
            {
                "site_survey_required": True,
                "site_survey_at": fields.Datetime.now() + timedelta(days=2),
            }
        )
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("it_solution_crm.google_access_token", "calendar-token")
        params.set_param("it_solution_crm.google_calendar_id", "primary")

        with patch(
            "odoo.addons.it_solution_crm.models.crm_lead.requests.post",
            return_value=FakeResponse(
                {"id": "event-01", "htmlLink": "https://calendar.example/event-01"}
            ),
        ) as post:
            lead.action_sync_site_survey_calendar()

        self.assertTrue(post.called)
        self.assertEqual(lead.calendar_event_id, "event-01")
        self.assertTrue(lead.calendar_synced_at)

    def test_telegram_notification_is_sent_when_configured(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("it_solution_crm.telegram_bot_token", "bot-token")
        params.set_param("it_solution_crm.telegram_chat_id", "chat-01")

        with patch(
            "odoo.addons.it_solution_crm.models.project_task.requests.post",
            return_value=FakeResponse({"ok": True}),
        ) as post:
            lead = self._create_lead()

        task = lead.it_task_ids.filtered(
            lambda item: item.it_task_kind == "initial_contact"
        )
        self.assertTrue(post.called)
        self.assertTrue(task.telegram_notified_at)
