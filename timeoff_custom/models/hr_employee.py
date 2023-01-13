from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class HrEmployee(models.Model):
    """Inherit HR Employee"""
    _inherit = 'hr.employee'

    employee_status = fields.Selection([
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('part', 'Part Time'),
        ], string="Employee Status", default='contract')

    def write(self, values):
        try:
            permanent_employee_group = self.env.ref('timeoff_custom.hr_employee_permanent_employee')
            if values.get('employee_status') == 'permanent':
                permanent_employee_group.write({
                        'users': [(4, self.user_id.id)]
                })
            else:
                permanent_employee_group.write({
                    'users': [(3, self.user_id.id)]
                })
            return super(HrEmployee, self).write(values)
        except Exception as ex:
            raise ValidationError(_("This employee doesn't have user, please assign or create one!"))


class HrEmployeePublic(models.Model):
    """Inherit HR Employee"""
    _inherit = 'hr.employee.public'

    employee_status = fields.Selection([
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('part', 'Part Time'),
        ], string="Employee Status", default='contract')

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        domain = [('user_id', '=', self._uid)] # '&', ('employee_id', '=', emp.employee_id),
        return super(HrEmployeePublic, self).search_read(domain, fields, offset, limit, order, **read_kwargs)
