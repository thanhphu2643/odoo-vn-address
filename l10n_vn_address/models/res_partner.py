from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Wards offered in the address: those of the province, unless it was merged in 2025.
    vn_ward_state_id = fields.Many2one("res.country.state", compute="_compute_vn_ward_state_id")

    @api.depends("state_id")
    def _compute_vn_ward_state_id(self):
        for partner in self:
            partner.vn_ward_state_id = not partner.state_id.vn_replaced and partner.state_id
