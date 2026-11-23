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
    def _name_search(self, name, args=None, operator="ilike", limit=100, name_get_uid=None):
        if not self.env.context.get("vn_show_merged"):
            args = expression.AND([args or [], [("vn_replaced", "=", False)]])
        ids = list(super()._name_search(name, args, operator, limit, name_get_uid))
        if name and operator == "ilike" and (not limit or len(ids) < limit):
            domain = expression.AND([args, [("vn_search_name", "ilike", fold(name)), ("id", "not in", ids)]])
            ids += self._search(domain, limit=limit and limit - len(ids), access_rights_uid=name_get_uid)
        return ids
