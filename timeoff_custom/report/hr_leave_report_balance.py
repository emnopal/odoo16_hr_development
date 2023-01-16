from odoo import api, fields, models, tools, _

class HrLeaveReportBalance(models.Model):
    _name = 'hr.leave.report.balance'
    _auto = False

    name = fields.Char(string="Employee Name", readonly=True)
    annual_leave = fields.Integer(string="Annual Leave", readonly=True)
    replacement_day_off = fields.Integer(string="Replacement Day Off", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_leave_report_balance')

        self._cr.execute("""
            create or replace view hr_leave_report_balance as (
                select
                    row_number() OVER () as id,
                    balance.name,
                    sum(case when balance.day_off_type ~* '(?<!\w)(?:annual)(?!\w)' then balance.balance_days end)::integer as annual_leave,
                    sum(case when balance.day_off_type ~* '(?<!\w)(?:replacement)(?!\w)' then balance.balance_days end)::integer as replacement_day_off
                from (
                    select
                        e.name,
                        sum(r.number_of_days) balance_days,
                        (t.name -> 'en_US')::text as day_off_type
                    from hr_leave_report r
                    join hr_employee e
                    on e.id = r.employee_id
                    join hr_leave_type t
                    on t.id = r.holiday_status_id
                    where r.state = 'validate'
                    group by r.holiday_status_id, e.name, t.name
                ) balance
                group by balance.name
            );
        """)
