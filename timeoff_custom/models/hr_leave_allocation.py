from lxml import etree
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'

    # need to redeclare, since these method are protected
    def _domain_holiday_status_id(self):
        if self.user_has_groups('hr_holidays.group_hr_holidays_manager'):
            return [(1, '=', 1), ('requires_allocation', '=', 'yes')]
        return [('only_admin_can_allocate', '!=', True), ('employee_requests', '=', 'yes')]

    def _default_holiday_status_id(self):
        if self.user_has_groups('hr_holidays.group_hr_holidays_manager'):
            domain = [(1, '=', 1), ('has_valid_allocation', '=', True), ('requires_allocation', '=', 'yes')]
        else:
            domain = [('only_admin_can_allocate', '!=', True), ('has_valid_allocation', '=', True), ('requires_allocation', '=', 'yes'), ('employee_requests', '=', 'yes')]
        return self.env['hr.leave.type'].search(domain, limit=1)

    holiday_status_name = fields.Char(compute='_computer_holiday_status_name')
    employee_eligibility = fields.Boolean(related='employee_id.employee_eligibility')
    user_id = fields.Many2one(related='employee_id.user_id')
    current_user = fields.Boolean(compute='_get_current_user')
    only_admin_can_allocate = fields.Boolean(related='holiday_status_id.only_admin_can_allocate')

    # need to redeclare or may fail
    holiday_status_id = fields.Many2one(
        "hr.leave.type", compute='_compute_holiday_status_id', store=True, string="Time Off Type", required=True, readonly=False,
        states={'cancel': [('readonly', True)], 'refuse': [('readonly', True)], 'validate1': [('readonly', True)], 'validate': [('readonly', True)]},
        domain=_domain_holiday_status_id,
        default=_default_holiday_status_id)

    @api.depends('accrual_plan_id')
    def _compute_holiday_status_id(self):
        default_holiday_status_id = None
        for holiday in self:
            if not holiday.holiday_status_id:
                if holiday.accrual_plan_id:
                    holiday.holiday_status_id = holiday.accrual_plan_id.time_off_type_id
                else:
                    if not default_holiday_status_id:  # fetch when we need it
                        default_holiday_status_id = self._default_holiday_status_id()
                    holiday.holiday_status_id = default_holiday_status_id

    @api.depends('user_id')
    def _get_current_user(self):
        for rec in self:
            rec.current_user = True if rec.env.user.id == rec.user_id.id and not rec.env.user.has_group('base.group_system') else False

    @api.onchange('holiday_status_id')
    def _computer_holiday_status_name(self):
        for rec in self:
            rec.holiday_status_name = rec.holiday_status_id.name

    def parse_user_list_name(self, list_name):
        if len(list_name) == 1:
            return "".join(list_name)
        if len(list_name) == 2:
            return " and ".join(list_name)
        if len(list_name) > 2:
            return ", ".join(list_name[:-1]) + " and " + list_name[-1]

    # force create record to submit
    @api.model_create_multi
    def create(self, vals_list):
        for value in vals_list:
            value.update({'state': 'confirm'})
        return super(HrLeaveAllocation, self).create(vals_list)

    def action_confirm(self):
        leave_name = self.holiday_status_name

        if self.only_admin_can_allocate and not self.env.user.has_group('hr_holidays.group_hr_holidays_user'):
            raise UserError(_(f"This user not an admin. Only admin can allocate ({leave_name})"))

        # batch confirmation; if user(s) not eligible
        if self.holiday_status_id.need_eligible_employee:
            for rec in self:
                list_user_not_eligible = [empl.name if not empl.employee_eligibility else False for empl in rec.employee_ids ]
                if any(list_user_not_eligible):
                    user_not_eligible = rec.parse_user_list_name([name for name in list_user_not_eligible if name])
                    raise UserError(_(f"Employee(s): {user_not_eligible} not eligible to allocate {leave_name}"))

        res = self.write({'state': 'confirm'})
        self.activity_update()
        self.filtered(lambda holiday: holiday.validation_type == 'no').action_validate()

        return res

    def action_refuse(self, reason):
        for rec in self:
            if rec.current_user:
                raise UserError(_('You cannot refuse for yourself'))

        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['confirm'] for holiday in self):
            raise UserError(_('Allocation request must be confirmed in order to refuse it.'))

        self.write({'state': 'refuse', 'approver_id': current_employee.id})

        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_refuse(reason)

        self.message_post_with_view('timeoff_custom.hr_allocation_template_refuse_reason', values={
            'reason': reason,
            'leave_type': self.holiday_status_id.display_name,
            'user': self.parse_user_list_name([empl.name for empl in self.employee_ids])
        })

        self.activity_update()
        return True

    def action_draft(self):
        if any(holiday.state not in ['confirm', 'refuse', 'cancel'] for holiday in self):
            raise UserError(_('Allocation request state must be "Refused", "Cancelled" or "To Approve" in order to be reset to Draft.'))
        self.write({
            'state': 'draft',
            'approver_id': False,
        })
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_draft()
            linked_requests.unlink()
        self.activity_update()
        return True

    def action_cancel(self):
        current_employee = self.env.user.employee_id
        if any(holiday.state not in ['confirm', 'validate', 'validate1'] for holiday in self):
            raise UserError(_('Allocation request must be confirmed or validated in order to cancel it.'))

        self.write({'state': 'cancel', 'approver_id': current_employee.id})

        # If a category that created several holidays, cancel all related
        linked_requests = self.mapped('linked_request_ids')
        if linked_requests:
            linked_requests.action_cancel()

        self.message_post_with_view('timeoff_custom.hr_allocation_template_cancel', values={
            'reason': _(f"{self.env.user.name} has cancelled allocation"),
            'leave_type': self.holiday_status_id.display_name,
            'user': self.parse_user_list_name([empl.name for empl in self.employee_ids])
        })

        self.activity_update()
        return True

    def action_validate(self):
        for rec in self:
            if rec.current_user:
                raise UserError(_('You cannot validate for yourself'))
        return super(HrLeaveAllocation, self).action_validate()
