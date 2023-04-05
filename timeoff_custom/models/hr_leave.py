from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from datetime import datetime


class HrLeave(models.Model):
    _inherit = "hr.leave"
    _order = 'create_date desc'

    holiday_status_name = fields.Char(related='holiday_status_id.name')
    must_upload_attachment = fields.Boolean(related='holiday_status_id.must_upload_attachment')
    max_date_to_upload = fields.Integer(related='holiday_status_id.max_date_to_upload')
    can_select_past = fields.Boolean(related='holiday_status_id.can_select_past')
    current_user = fields.Boolean(string="Is Current User?", compute='_get_current_user')
    is_hr = fields.Boolean(related='employee_id.is_hr')
    is_manager = fields.Boolean(related='employee_id.is_manager')
    is_superuser = fields.Boolean(compute='_get_superuser')
    state = fields.Selection(selection_add=[('cancel', 'Cancelled')])

    def _get_superuser(self):
        for rec in self:
            rec.is_superuser = (True if rec.env.user.has_group('base.group_system') else False)

    @api.depends('user_id')
    def _get_current_user(self):
        for rec in self:
            rec.current_user = (True if rec.env.user.id == rec.user_id.id and not rec.env.user.has_group('base.group_system') else False)

    # check if user have submitted attachment; attachment validation in user view
    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            holiday_type = self.env['hr.leave.type'].search([('id', '=', value.get('holiday_status_id'))])
            type_name = holiday_type.name
            must_upload_attachment = holiday_type.must_upload_attachment
            max_date_to_upload = holiday_type.max_date_to_upload
            if must_upload_attachment:
                date_to = datetime.strptime(value.get('request_date_to'), "%Y-%m-%d")
                date_from = datetime.strptime(value.get('request_date_from'), "%Y-%m-%d")
                off_duration = abs((date_to - date_from).days) + 1
                if value.get('supported_attachment_ids'):
                    attachment_count = len(value['supported_attachment_ids'][0][2])
                    if attachment_count == 0 and off_duration >= max_date_to_upload:
                        raise UserError(_(f'Your {type_name} is more than {max_date_to_upload} days, you have to upload a document to prove!'))
        return super(HrLeave, self).create(vals_list)

    # this is attachment validation in hr view
    @api.depends('supported_attachment_ids', 'attachment_ids', 'supported_attachment_ids_count', 'leave_type_support_document', 'number_of_days')
    def _constraint_attachment(self):
        if self.number_of_days >= self.max_date_to_upload and \
        self.state not in ['cancel', 'refuse'] and \
        self.supported_attachment_ids_count == 0 and \
        self.leave_type_support_document and \
        self.must_upload_attachment:
            raise UserError(_(f"{self.user_id.name} day's off is more than or equal "
                            f"{self.max_date_to_upload} days, please ask {self.user_id.name} "
                            "to upload a document to prove!"))

    def action_confirm(self):
        self._constraint_attachment()
        return super(HrLeave, self).action_confirm()

    def action_approve(self):
        self._constraint_attachment()
        if self.current_user:
            raise UserError(_('You cannot approve for yourself'))
        return super(HrLeave, self).action_approve()

    def action_validate(self):
        self._constraint_attachment()
        if self.current_user:
            raise UserError(_('You cannot validate for yourself'))
        return super(HrLeave, self).action_validate()

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

    def action_draft(self):
        if any(holiday.state not in ['confirm', 'refuse', 'cancel'] for holiday in self):
            raise UserError(_('Time off request state must be "Refused", "Cancelled" or "To Approve" in order to be reset to draft.'))
        self.write({
            'state': 'draft',
            'first_approver_id': False,
            'second_approver_id': False,
        })
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_draft()
            linked_requests.unlink()
        self.activity_update()
        return True

    def action_cancel(self):
        if self.current_user:
            raise UserError(_('You cannot cancel for yourself'))

        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['confirm', 'validate', 'validate1'] for holiday in self):
            raise UserError(_('Allocation request must be confirmed or validated in order to cancel it.'))

        validated_holidays = self.filtered(lambda hol: hol.state == 'validate1')
        validated_holidays.write({'state': 'cancel', 'first_approver_id': current_employee.id})
        (self - validated_holidays).write({'state': 'cancel', 'second_approver_id': current_employee.id})
        # Delete the meeting
        self.mapped('meeting_id').write({'active': False})
        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_cancel()

        # Post a second message, more verbose than the tracking message
        for holiday in self:
            if holiday.employee_id.user_id:
                holiday.message_post_with_view('timeoff_custom.hr_allocation_template_cancel', values={
                    'reason': 'Time off cancelled by user',
                    'leave_type': holiday.holiday_status_id.display_name,
                    'date': holiday.date_from.date()
                })

        self.activity_update()
        return True

    # Start
    # depreciation draft, before removing in incoming version
    # because it not used anymore
    # why?
    # bug. the logic for selecting timeoff will be broken
    @api.constrains('state', 'number_of_days', 'holiday_status_id')
    def _check_holidays(self):
        can_select_past_day = self.can_select_past

        for holiday in self:
            mapped_days = self.holiday_status_id.get_employees_days((holiday.employee_id | holiday.employee_ids).ids, holiday.date_from.date())

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
                    # not can_select_past_day
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
    # End
