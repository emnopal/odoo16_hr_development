from odoo import fields, models, _, api
from odoo.exceptions import UserError


class HrLeaveRefuseAllocationWizard(models.TransientModel):
    _name = 'hr.leave.refuse.allocation.wizard'
    _description = 'Refuse Allocation Wizard'

    def _default_allocation_id(self):
        active_ids = self.env.context.get('active_ids', [])
        return self.env['hr.leave.allocation'].search([('id', '=', active_ids)], limit=1).id

    allocation_id = fields.Many2one('hr.leave.allocation', required=True, default=_default_allocation_id)
    reason = fields.Text(required=True)

    def action_refuse_allocation(self):
        self.allocation_id.action_refuse(self.reason)
