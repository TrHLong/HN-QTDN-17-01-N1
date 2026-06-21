from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    it_ai_endpoint = fields.Char(
        string="AI endpoint",
        config_parameter="it_solution_crm.ai_endpoint",
    )
    it_ai_api_key = fields.Char(
        string="AI API key",
        config_parameter="it_solution_crm.ai_api_key",
    )
    it_ai_model = fields.Char(
        string="AI model",
        config_parameter="it_solution_crm.ai_model",
        default="gpt-4o-mini",
    )
    it_google_calendar_id = fields.Char(
        string="Google Calendar ID",
        config_parameter="it_solution_crm.google_calendar_id",
    )
    it_google_access_token = fields.Char(
        string="Google access token",
        config_parameter="it_solution_crm.google_access_token",
    )
    it_telegram_bot_token = fields.Char(
        string="Telegram bot token",
        config_parameter="it_solution_crm.telegram_bot_token",
    )
    it_telegram_chat_id = fields.Char(
        string="Telegram chat ID",
        config_parameter="it_solution_crm.telegram_chat_id",
    )
