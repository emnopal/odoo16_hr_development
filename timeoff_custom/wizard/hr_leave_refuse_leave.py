from odoo import fields, models, _, api


class HrLeaveRefuseLeaveWizard(models.TransientModel):
    _name = 'hr.leave.refuse.leave.wizard'
    _description = 'Refuse Leave Wizard'

    def _default_leave_id(self):
        active_ids = self.env.context.get('active_ids', [])
        return self.env['hr.leave'].search([('id', '=', active_ids)], limit=1).id

    leave_id = fields.Many2one('hr.leave', required=True, default=_default_leave_id)
    reason = fields.Text(required=True)

    def action_refuse_leave(self):
        self.ensure_one()
        self.leave_id.action_refuse(self.reason)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Your time off has been refused."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
