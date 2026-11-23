from odoo import api, fields, models
from odoo.osv import expression

from ..vn_address import fold


class ResCity(models.Model):
    _inherit = "res.city"

    vn_code = fields.Char("GSO Code", index=True, help="Ward code of the General Statistics Office of Vietnam.")
    vn_search_name = fields.Char(compute="_compute_vn_search_name", store=True)

    @api.depends("name", "vn_code")
    def _compute_vn_search_name(self):
        for city in self:
            city.vn_search_name = fold(city.name) if city.vn_code else False

    @api.model
    def _name_search(self, name, args=None, operator="ilike", limit=100, name_get_uid=None):
        ids = list(super()._name_search(name, args, operator, limit, name_get_uid))
        if name and operator == "ilike" and (not limit or len(ids) < limit):
            # People often type Vietnamese without diacritics: "ba dinh" finds "Phường Ba Đình".
            domain = expression.AND([args or [], [("vn_search_name", "ilike", fold(name)), ("id", "not in", ids)]])
            ids += self._search(domain, limit=limit and limit - len(ids), access_rights_uid=name_get_uid)
        return ids

    def name_get(self):
        # Vietnamese wards are picked within their province: the ZIP is shown in its own field.
        vn_wards = self.filtered("vn_code")
        return [(city.id, city.name) for city in vn_wards] + super(ResCity, self - vn_wards).name_get()
