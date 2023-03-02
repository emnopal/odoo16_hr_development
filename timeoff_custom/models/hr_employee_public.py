from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class HrEmployeePublic(models.Model):
    """Inherit HR Employee"""
    _inherit = 'hr.employee.public'

    employee_eligibility = fields.Boolean(string="Eligible Employee", default=False)

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, **read_kwargs):
        domain = [('user_id', '=', self._uid)]
        return super(HrEmployeePublic, self).search_read(domain, fields, offset, limit, order, **read_kwargs)
