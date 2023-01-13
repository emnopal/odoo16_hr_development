from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

class TimeOffCustom(models.Model):
    _inherit = "hr.leave"

    holiday_status_name = fields.Char(related='holiday_status_id.name')
    must_upload_attachment = fields.Boolean(related='holiday_status_id.must_upload_attachment')
    max_date_to_upload = fields.Integer(related='holiday_status_id.max_date_to_upload')
    current_user = fields.Boolean(string="Is Current User?", compute='_get_current_user')

    @api.depends('user_id')
    def _get_current_user(self):
        for rec in self:
            rec.current_user = (True if rec.env.user.id == rec.user_id.id and not rec.env.user.has_group('base.group_system') else False)

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
            raise UserError(_(f"{self.user_id.name} day off is more than or equal"
                            f"{self.max_date_to_upload} days, please ask {self.user_id.name} to upload a document to prove!"))

    def action_confirm(self):
        self._constraint_attachment()
        return super(TimeOffCustom, self).action_confirm()

    def action_approve(self):
        self._constraint_attachment()
        if self.current_user:
            raise UserError(_('You cannot approve for yourself'))
        return super(TimeOffCustom, self).action_approve()

    def action_validate(self):
        self._constraint_attachment()
        if self.current_user:
            raise UserError(_('You cannot validate for yourself'))
        return super(TimeOffCustom, self).action_validate()

    def action_refuse(self):
        if self.current_user:
            raise UserError(_('You cannot refuse for yourself'))
        return super(TimeOffCustom, self).action_refuse()

    @api.constrains('request_date_from', 'request_date_to')
    def _depends_datepicker(self):
        cannot_future_day = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.cannot_select_future_day_as_time_off")
        cannot_future_day_sick = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.cannot_select_future_day_as_sick_time_off")

        if cannot_future_day:
            if any([self.request_date_from > fields.Date.today(), self.request_date_to > fields.Date.today()]):
                raise UserError(_(f"Based on this company rules, selecting request date in the future is forbidden"))

        if cannot_future_day_sick and self.holiday_status_name == 'Sick':
            if any([self.request_date_from > fields.Date.today(), self.request_date_to > fields.Date.today()]):
                raise UserError(_(f"Based on this company rules, selecting request date in the future as sick day off is forbidden"))

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        can_select_past_day = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_select_past_day_as_time_off")
        is_sick = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_select_past_day_as_sick_time_off")

        for holiday in self:
            mapped_days = self.holiday_status_id.get_employees_days((holiday.employee_id | holiday.employee_ids).ids, holiday.date_from.date())

            if is_sick and holiday.holiday_status_name == 'Sick':
                can_select_past_day = True

            no_allocation_type = any([
                holiday.holiday_type != 'employee',
                all([not holiday.employee_id, not holiday.employee_ids]),
                holiday.holiday_status_id.requires_allocation == 'no'
            ])

            if no_allocation_type:
                continue

            if holiday.employee_id:

                leave_days = mapped_days[holiday.employee_id.id][holiday.holiday_status_id.id]
                leave_days_compare = all([
                    any([
                        float_compare(leave_days['remaining_leaves'], 0, precision_digits=2) == -1,
                        float_compare(leave_days['virtual_remaining_leaves'], 0, precision_digits=2) == -1
                    ]),
                    not can_select_past_day
                ])

                if leave_days_compare:
                    raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                                            'Please also check the time off waiting for validation.'))
            else:
                unallocated_employees = []

                for employee in holiday.employee_ids:
                    leave_days = mapped_days[employee.id][holiday.holiday_status_id.id]
                    leave_days_compare = any([
                        float_compare(leave_days['remaining_leaves'], self.number_of_days, precision_digits=2) == -1,
                        float_compare(leave_days['virtual_remaining_leaves'], self.number_of_days, precision_digits=2) == -1
                    ])
                    if leave_days_compare:
                        unallocated_employees.append(employee.name)

                if unallocated_employees:
                    raise ValidationError(_('The number of remaining time off is not sufficient for this time off type.\n'
                                            'Please also check the time off waiting for validation.')
                                        + _('\nThe employees that lack allocation days are:\n%s',
                                            (', '.join(unallocated_employees))))

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
    user_id = fields.Many2one(related='employee_id.user_id')
    current_user = fields.Boolean(string="Is Current User?", compute='_get_current_user')

    @api.depends('user_id')
    def _get_current_user(self):
        for rec in self:
            rec.current_user = (True if rec.env.user.id == rec.user_id.id and not rec.env.user.has_group('base.group_system') else False)

    @api.onchange('holiday_status_id')
    def _computer_holiday_status_name(self):
        for rec in self:
            rec.holiday_status_name = rec.holiday_status_id.name

    def action_confirm(self):
        if self.holiday_status_name == 'Annual Leave' and self.employee_status != 'permanent':
            raise UserError(_("You're not eligible to take annual leave"))
        return super(TimeOffCustomAllocation, self).action_confirm()

    def action_refuse(self):
        if self.current_user:
            raise UserError(_('You cannot refuse for yourself'))
        return super(TimeOffCustomAllocation, self).action_refuse()

    def action_validate(self):
        if self.current_user:
            raise UserError(_('You cannot validate for yourself'))
        return super(TimeOffCustomAllocation, self).action_validate()

    @api.ondelete(at_uninstall=False)
    def _unlink_if_correct_states(self):
        can_delete_validated = self.env["ir.config_parameter"].sudo().get_param("hr_holidays.can_delete_validated_allocation")
        state_description_values = {elem[0]: elem[1] for elem in self._fields['state']._description_selection(self.env)}
        if not can_delete_validated:
            for holiday in self.filtered(lambda holiday: holiday.state not in ['draft', 'cancel', 'confirm']):
                raise UserError(_('You cannot delete an allocation request which is in %s state.') % (state_description_values.get(holiday.state),))

class TimeOffCustomType(models.Model):
    _inherit = 'hr.leave.type'

    need_to_permanent_employee = fields.Boolean(string="Need Permanent Employee to allocate this time off", default=False)
    must_upload_attachment = fields.Boolean(string="User Must Upload Attachment", default=False)
    max_date_to_upload = fields.Integer(string="Maximum Day Off for User to Upload Attachment", default=0)
