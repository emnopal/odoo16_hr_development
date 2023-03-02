from odoo import api, fields, models, tools, _

class HrLeaveReportUsed(models.Model):
    _name = 'hr.leave.report.used'
    _auto = False

    name = fields.Char(string="Employee Name", readonly=True)
    annual_leave = fields.Integer(string="Annual Leave", readonly=True)
    replacement_day_off = fields.Integer(string="Replacement Day Off", readonly=True)
    sick = fields.Integer(string="Sick", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_leave_report_used')

        self._cr.execute("""
            create or replace view hr_leave_report_used as (
                select
                    row_number() OVER () as id,
                    used.name,
                    sum(case when used.day_off_type ~* '(?<!\w)(?:annual)(?!\w)' then used.used_days end)::integer as annual_leave,
                    sum(case when used.day_off_type ~* '(?<!\w)(?:replacement)(?!\w)' then used.used_days end)::integer as replacement_day_off,
                    sum(case when used.day_off_type ~* '(?<!\w)(?:sick)(?!\w)' then used.used_days end)::integer as sick
                from (
                select
                    e.name,
                    sum(abs(r.number_of_days)) used_days,
                    (t.name -> 'en_US')::text as day_off_type
                from hr_leave_report r
                join hr_employee e
                on e.id = r.employee_id
                join hr_leave_type t
                on t.id = r.holiday_status_id
                where r.state = 'validate' and r.leave_type = 'request'
                group by e.name, r.number_of_days, day_off_type) used
                group by used.name
            );
        """)
