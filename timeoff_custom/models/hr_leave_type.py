from odoo import api, models, fields, _


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    need_eligible_employee = fields.Boolean(string="Need Eligible Employee to Allocate This Time Off", default=False)
    only_admin_can_allocate = fields.Boolean(string="Only Admin Can Allocate This Time Off", default=False)
    must_upload_attachment = fields.Boolean(string="User Must Upload Attachment", default=False)
    max_date_to_upload = fields.Integer(string="Maximum Day Off for User to Upload Attachment", default=0)
    can_select_past = fields.Boolean(string="User Can Select Past Day", default=True)
