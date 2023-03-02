from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class HrEmployee(models.Model):
    """Inherit HR Employee"""
    _inherit = 'hr.employee'

    employee_eligibility = fields.Boolean(string="Eligible Employee", default=False)
    is_hr = fields.Boolean(compute='_compute_is_hr')
    is_manager = fields.Boolean(compute='_compute_is_manager')

    def _compute_is_hr(self):
        for rec in self:
            if rec.env.user.has_group('hr_holidays.group_hr_holidays_user'):
                rec.is_hr = True
            else:
                rec.is_hr = False

    def _compute_is_manager(self):
        for rec in self:
            if rec.env.user.has_group('hr_holidays.group_hr_holidays_manager'):
                rec.is_manager = True
            else:
                rec.is_manager = False

    def write(self, values):
        try:
            eligible_employee_group = self.env.ref('timeoff_custom.eligible_employee')
            # it supposed to be use match case, but odoo 16 currently doesn't support python 3.10 or above
            if values.get('employee_eligibility') == True:
                eligible_employee_group.write({
                        'users': [(4, self.user_id.id)]
                })
            elif values.get('employee_eligibility') == False:
                eligible_employee_group.write({
                    'users': [(3, self.user_id.id)]
                })
            else:
                pass
            return super(HrEmployee, self).write(values)
        except Exception as ex:
            raise ValidationError(_("This employee doesn't have user, please assign or create one!"))
