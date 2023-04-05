from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError

class HrEmployee(models.Model):
    """Inherit HR Employee"""
    _inherit = 'hr.employee'

    employee_eligibility = fields.Boolean(string="Eligible Employee to Take Annual Leave", default=False)
    is_hr = fields.Boolean(compute='_compute_is_hr')
    is_manager = fields.Boolean(compute='_compute_is_manager')
    position = fields.Selection(selection=[
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('hr', 'HR'),
        ('ceo', 'CEO'),
        ('superuser', 'Superuser'),
    ], string='Position', default='employee')

    def _compute_is_hr(self):
        for rec in self:
            if rec.env.user.has_group('timeoff_custom.hr'):
                rec.is_hr = True
            else:
                rec.is_hr = False

    def _compute_is_manager(self):
        for rec in self:
            if rec.env.user.has_group('timeoff_custom.manager'):
                rec.is_manager = True
            else:
                rec.is_manager = False

    def _handle_group_position(self, perm_employee, perm_manager, perm_hr, perm_ceo):
        self.env.ref(f"timeoff_custom.employee").write({
            'users': [(perm_employee, self.user_id.id)]
        })
        self.env.ref(f"timeoff_custom.manager").write({
            'users': [(perm_manager, self.user_id.id)]
        })
        self.env.ref(f"timeoff_custom.hr").write({
            'users': [(perm_hr, self.user_id.id)]
        })
        self.env.ref(f"timeoff_custom.ceo").write({
            'users': [(perm_ceo, self.user_id.id)]
        })


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

            if values.get('position') == 'employee':
                self._handle_group_position(4,3,3,3)
            elif values.get('position') == 'manager':
                self._handle_group_position(4,4,3,3)
            elif values.get('position') == 'hr':
                self._handle_group_position(4,3,4,3)
            elif values.get('position') == 'ceo':
                self._handle_group_position(4,4,4,4)
            elif values.get('position') == 'superuser':
                self._handle_group_position(4,4,4,3)
            else:
                pass

            return super(HrEmployee, self).write(values)
        except Exception as ex:
            raise ValidationError(_("This employee doesn't have user, please assign or create one!"))
