from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from datetime import datetime

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

    @api.depends('supported_attachment_ids', 'attachment_ids', 'supported_attachment_ids_count', 'leave_type_support_document', 'number_of_days')
    def _constraint_attachment(self):
        constrains_condition = all([
            self.number_of_days >= self.max_date_to_upload,
            self.state not in ['draft', 'cancel', 'refuse'],
            self.supported_attachment_ids_count == 0,
            self.leave_type_support_document,
            self.must_upload_attachment,
        ])

        if constrains_condition:
            raise UserError(_(f"{self.user_id.name} day's off is more than or equal "
                            f"{self.max_date_to_upload} days, please ask {self.user_id.name} "
                            "to upload a document to prove!"))

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

    def action_refuse(self, reason):
        if self.current_user:
            raise UserError(_('You cannot refuse for yourself'))

        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['draft', 'confirm', 'validate', 'validate1'] for holiday in self):
            raise UserError(_('Time off request must be confirmed or validated in order to refuse it.'))

        validated_holidays = self.filtered(lambda hol: hol.state == 'validate1')
        validated_holidays.write({'state': 'refuse', 'first_approver_id': current_employee.id})
        (self - validated_holidays).write({'state': 'refuse', 'second_approver_id': current_employee.id})
        # Delete the meeting
        self.mapped('meeting_id').write({'active': False})
        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse(reason)

        # Post a second message, more verbose than the tracking message
        for holiday in self:
            if holiday.employee_id.user_id:
                holiday.message_post_with_view('timeoff_custom.hr_leave_template_refuse_reason', values={
                    'reason': reason,
                    'leave_type': holiday.holiday_status_id.display_name,
                    'date': holiday.date_from.date()
                })

        self.activity_update()
        return True

    @api.constrains('request_date_from', 'request_date_to')
    def _depends_datepicker(self):
        if self.holiday_status_name == 'Sick':
            if any([self.request_date_from > fields.Date.today(), self.request_date_to > fields.Date.today()]):
                raise UserError(_(f"Based on this company rules, selecting request date in the future as sick day off is forbidden"))

    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        can_select_past_day = False

        for holiday in self:
            mapped_days = self.holiday_status_id.get_employees_days((holiday.employee_id | holiday.employee_ids).ids, holiday.date_from.date())

            if holiday.holiday_status_name == 'Sick':
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

    def action_refuse(self, reason):
        if self.current_user:
            raise UserError(_('You cannot refuse for yourself'))
        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['confirm', 'validate', 'validate1'] for holiday in self):
            raise UserError(_('Allocation request must be confirmed or validated in order to refuse it.'))

        self.write({'state': 'refuse', 'approver_id': current_employee.id})
        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse(reason)

        for holiday in self:
            if holiday.employee_id.user_id:
                holiday.message_post_with_view('timeoff_custom.hr_allocation_template_refuse_reason', values={
                    'reason': reason,
                    'leave_type': holiday.holiday_status_id.display_name
                })

        self.activity_update()
        return True

    def action_validate(self):
        if self.current_user:
            raise UserError(_('You cannot validate for yourself'))
        return super(TimeOffCustomAllocation, self).action_validate()

class TimeOffCustomType(models.Model):
    _inherit = 'hr.leave.type'

    need_to_permanent_employee = fields.Boolean(string="Need Permanent Employee to allocate this time off", default=False)
    must_upload_attachment = fields.Boolean(string="User Must Upload Attachment", default=False)
    max_date_to_upload = fields.Integer(string="Maximum Day Off for User to Upload Attachment", default=0)
