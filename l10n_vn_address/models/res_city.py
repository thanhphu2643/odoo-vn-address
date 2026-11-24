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
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        if value and operator == "ilike":
            # People often type Vietnamese without diacritics: "ba dinh" finds "Phường Ba Đình".
            domain = expression.OR([domain, [("vn_search_name", "ilike", fold(value))]])
        return domain

    @api.depends("name", "zipcode", "vn_code")
    def _compute_display_name(self):
        # Vietnamese wards are picked within their province: the ZIP is shown in its own field.
        vn_wards = self.filtered("vn_code")
        for city in vn_wards:
            city.display_name = city.name
        super(ResCity, self - vn_wards)._compute_display_name()
