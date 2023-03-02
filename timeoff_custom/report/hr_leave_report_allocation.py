# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.osv import expression


class LeaveReportAllocation(models.Model):
    _name = "hr.leave.report.allocation"
    _description = 'Allocation Summary / Report'
    _auto = False
    _order = "date_from DESC, employee_id"

    active = fields.Boolean(readonly=True)
    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    leave_id = fields.Many2one('hr.leave', string="Leave Request", readonly=True)
    allocation_id = fields.Many2one('hr.leave.allocation', string="Allocation Request", readonly=True)
    active_employee = fields.Boolean(readonly=True)
    name = fields.Char('Description', readonly=True)
    number_of_days = fields.Float('Number of Days', readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    category_id = fields.Many2one('hr.employee.category', string='Employee Tag', readonly=True)
    holiday_status_id = fields.Many2one("hr.leave.type", string="Leave Type", readonly=True)
    state = fields.Selection([
        ('draft', 'To Submit'),
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
        ], string='Status', readonly=True)
    holiday_type = fields.Selection([
        ('employee', 'By Employee'),
        ('category', 'By Employee Tag')
    ], string='Allocation Mode', readonly=True)
    date_from = fields.Datetime('Start Date', readonly=True)
    date_to = fields.Datetime('End Date', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_leave_report_allocation')

        self._cr.execute("""
            CREATE or REPLACE view hr_leave_report_allocation as (
                SELECT row_number() over(ORDER BY allocations.employee_id) as id,
                allocations.allocation_id as allocation_id,
                allocations.leave_id as leave_id,
                allocations.employee_id as employee_id,
                allocations.name as name,
                allocations.active_employee as active_employee,
                allocations.active as active,
                allocations.number_of_days as number_of_days,
                allocations.category_id as category_id,
                allocations.department_id as department_id,
                allocations.holiday_status_id as holiday_status_id,
                allocations.state as state,
                allocations.holiday_type as holiday_type,
                allocations.date_from as date_from,
                allocations.date_to as date_to,
                allocations.company_id
                from (select
                    allocation.active as active,
                    allocation.id as allocation_id,
                    null as leave_id,
                    allocation.employee_id as employee_id,
                    employee.active as active_employee,
                    allocation.private_name as name,
                    allocation.number_of_days as number_of_days,
                    allocation.category_id as category_id,
                    allocation.department_id as department_id,
                    allocation.holiday_status_id as holiday_status_id,
                    allocation.state as state,
                    allocation.holiday_type,
                    allocation.date_from as date_from,
                    allocation.date_to as date_to,
                    allocation.employee_company_id as company_id
                from hr_leave_allocation as allocation
                inner join hr_employee as employee on (allocation.employee_id = employee.id)) allocations
            );
        """)

    @api.model
    def action_time_off_analysis(self):
        domain = [('holiday_type', '=', 'employee')]

        if self.env.context.get('active_ids'):
            domain = expression.AND([
                domain,
                [('employee_id', 'in', self.env.context.get('active_ids', []))]
            ])

        return {
            'name': _('Allocation Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.report.allocation',
            'view_mode': 'tree,pivot,form',
            'search_view_id': [self.env.ref('timeoff_custom.view_hr_holidays_filter_report_allocation').id],
            'domain': domain,
            'context': {
                'search_default_group_employee': True,
                'search_default_year': True,
                'search_default_validated': True,
                'search_default_active_employee': True,
            }
        }

    def action_open_record(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_id': self.leave_id.id if self.leave_id else self.allocation_id.id,
            'res_model': 'hr.leave' if self.leave_id else 'hr.leave.allocation',
        }
