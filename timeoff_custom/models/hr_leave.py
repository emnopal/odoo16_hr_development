from odoo import api, models, fields, _
from odoo.exceptions import UserError

class TimeOffCustom(models.Model):
    _inherit = "hr.leave"

    button_can_approve_or_reject = fields.Boolean(compute="_compute_button_can_approve_or_reject")
    holiday_status_name = fields.Char(related='holiday_status_id.name')
    must_upload_attachment = fields.Boolean(related='holiday_status_id.must_upload_attachment')
    max_date_to_upload = fields.Integer(related='holiday_status_id.max_date_to_upload')

    def _compute_button_can_approve_or_reject(self):
        for field in self:
            if (field.employee_id.leave_manager_id.id == self._uid and field.env.user.has_group('hr_holidays.group_hr_holidays_user'))\
            or field.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                field.button_can_approve_or_reject = True
            else:
                field.button_can_approve_or_reject = False

    @api.depends('supported_attachment_ids_count', 'leave_type_support_document', 'number_of_days')
    def _constraint_attachment(self):

        constrains_condition = all([
            self.number_of_days >= self.max_date_to_upload,
            self.state not in ['draft', 'cancel', 'refuse'],
            self.supported_attachment_ids_count == 0,
            self.leave_type_support_document,
            self.must_upload_attachment,
        ])

        if constrains_condition:
            raise UserError(f"{self.user_id.name} day off is more than 1 day, please ask {self.user_id.name} to upload a document to prove!")

    def action_confirm(self):
        self._constraint_attachment()
        return super(TimeOffCustom, self).action_confirm()

    def action_approve(self):
        self._constraint_attachment()
        return super(TimeOffCustom, self).action_approve()

    def action_validate(self):
        self._constraint_attachment()
        return super(TimeOffCustom, self).action_validate()

    @api.constrains('request_date_from', 'request_date_to')
    def _depends_datepicker(self):
        cannot_future_day = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.cannot_select_future_day_as_time_off")
        if cannot_future_day:
            if any([self.request_date_from > fields.Date.today(), self.request_date_to > fields.Date.today()]):
                raise UserError(f"Based on this company rules, selecting request date in the future is forbidden")

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        select_past_day = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_select_past_day_as_time_off")
        if select_past_day:
            return
        else:
            return super(TimeOffCustom, self)._check_holidays()

    @api.ondelete(at_uninstall=False)
    def _unlink_if_correct_states(self):
        error_message = _('You cannot delete a time off which is in %s state')
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        now = fields.Datetime.now()
        can_delete_validated = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_delete_validated_time_off")
        can_delete_past = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_delete_past_time_off")

        if not self.user_has_groups('hr_holidays.group_hr_holidays_user'):
            for hol in self:
                if hol.state not in ['draft', 'confirm']:
                    raise UserError(error_message % state_description_values.get(self[:1].state))
                if hol.date_from < now:
                    raise UserError(_('You cannot delete a time off which is in the past'))
                if hol.employee_ids and not hol.employee_id:
                    raise UserError(_('You cannot delete a time off assigned to several employees'))
        else:
            if not can_delete_validated:
                for holiday in self.filtered(lambda holiday: holiday.state not in ['draft', 'cancel', 'confirm']):
                    raise UserError(error_message % (state_description_values.get(holiday.state),))
            if not can_delete_past:
                for holiday in self.filtered(lambda holiday: holiday.date_from < now):
                    raise UserError(_('You cannot delete a time off which is in the past'))

class TimeOffCustomAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    holiday_status_name = fields.Char(compute='_computer_holiday_status_name')
    employee_status = fields.Selection(related='employee_id.employee_status')

    @api.onchange('holiday_status_id')
    def _computer_holiday_status_name(self):
        for rec in self:
            rec.holiday_status_name = rec.holiday_status_id.name

    def action_confirm(self):
        if self.filtered(lambda holiday: holiday.holiday_status_name == 'Annual Leave' and holiday.employee_status != 'permanent'):
            raise UserError("You're not eligible to take annual leave")
        return super(TimeOffCustomAllocation, self).action_confirm()

class TimeOffCustomType(models.Model):
    _inherit = 'hr.leave.type'

    need_to_permanent_employee = fields.Boolean(string="Need Permanent Employee to allocate this time off", default=False)
    must_upload_attachment = fields.Boolean(string="User Must Upload Attachment", default=False)
    max_date_to_upload = fields.Integer(string="Maximum Day Off for User to Upload Attachment", default=0)

class TimeOffCustomAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    @api.ondelete(at_uninstall=False)
    def _unlink_if_correct_states(self):
        can_delete_validated = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_delete_validated_allocation")
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        if not can_delete_validated:
            for holiday in self.filtered(lambda holiday: holiday.state not in ['draft', 'cancel', 'confirm']):
                raise UserError(_('You cannot delete an allocation request which is in %s state.') % (state_description_values.get(holiday.state),))
