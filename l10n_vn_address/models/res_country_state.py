from odoo import api, fields, models
from odoo.osv import expression

from ..vn_address import fold


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    vn_code = fields.Char("GSO Code", help="Province code of the General Statistics Office of Vietnam.")
    vn_old_code = fields.Char("GSO Code before 2025", help="Province code before 1 July 2025.")
    vn_replaced = fields.Boolean(
        "Merged in 2025",
        help="This province was merged into another one on 1 July 2025. It stays so that "
        "existing addresses still show it, but it is no longer offered when picking a province.",
    )
    vn_search_name = fields.Char(compute="_compute_vn_search_name", store=True)

    @api.depends("name", "vn_old_code")
    def _compute_vn_search_name(self):
        for state in self:
            state.vn_search_name = fold(state.name) if state.vn_old_code else False

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value and operator == "ilike":
            domain = expression.OR([domain, [("vn_search_name", "ilike", fold(value))]])
        if not self.env.context.get("vn_show_merged"):
            domain = expression.AND([domain, [("vn_replaced", "=", False)]])
        return domain
