from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    can_select_past_day_as_time_off = fields.Boolean(string="Can Select Past Day as Time Off", default=False, config_parameter='hr_holidays.can_select_past_day_as_time_off')
    can_select_past_day_as_sick_time_off = fields.Boolean(string="Can Select Past Day as Sick Time Off", default=False, config_parameter='hr_holidays.can_select_past_day_as_sick_time_off')
    cannot_select_future_day_as_time_off = fields.Boolean(string="Cannot Select Future Day as Time Off", default=False, config_parameter='hr_holidays.cannot_select_future_day_as_time_off')
    cannot_select_future_day_as_sick_time_off = fields.Boolean(string="Cannot Select Future Day as Sick Time Off", default=False, config_parameter='hr_holidays.cannot_select_future_day_as_sick_time_off')
    can_delete_past_time_off = fields.Boolean(string="Can Delete Past Time Off", default=False, config_parameter='hr_holidays.can_delete_past_time_off')
    can_delete_validated_time_off = fields.Boolean(string="Can Delete Validated Time Off", default=False, config_parameter='hr_holidays.can_delete_validated_time_off')
    can_delete_validated_allocation = fields.Boolean(string="Can Delete Validated Allocation", default=False, config_parameter='hr_holidays.can_delete_validated_allocation')
