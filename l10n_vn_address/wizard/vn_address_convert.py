from odoo import Command, _, api, fields, models

from ..vn_address import clean_line, find_province, match_address, old_provinces, old_units

# Addresses prepared per run; the rest show up the next time the tool is opened.
BATCH = 500


class VnAddressConvert(models.TransientModel):
    _name = "vn.address.convert"
    _description = "Move Vietnamese addresses to the 2025 administrative units"

    line_ids = fields.One2many("vn.address.convert.line", "wizard_id")
    remaining = fields.Integer(readonly=True)

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        if "line_ids" not in fields_list:
            return result
        partners = self._partners_to_convert()
        context = self._match_context()
        lines = []
        for index, partner in enumerate(partners):
            if len(lines) == BATCH:
                result["remaining"] = len(partners) - index
                break
            line = self._prepare_line(partner, context)
            if line:
                lines.append(Command.create(line))
        result["line_ids"] = lines
        return result

    def _partners_to_convert(self):
        vn = self.env.ref("base.vn")
        domain = [
            ("city_id", "=", False),
            # Without a country, the address is checked for a Vietnamese province.
            "|", ("country_id", "=", vn.id),
            "&", ("country_id", "=", False), "|", ("state_id", "=", False), ("state_id.country_id", "=", vn.id),
            # Contacts of a company share its address: converting the company converts them.
            "!", "&", ("type", "=", "contact"), ("parent_id", "!=", False),
        ]
        if self.env.context.get("active_model") == "res.partner" and self.env.context.get("active_ids"):
            domain.append(("id", "in", self.env.context["active_ids"]))
        return self.env["res.partner"].search(domain)

    def _match_context(self):
        # Odoo 19 keeps only the 34 current provinces: the old ones are known by their code,
        # and each one belongs to the current province its wards went to.
        state_by_ward = {city.vn_code: city.state_id for city in self.env["res.city"].search([("vn_code", "!=", False)])}
        state_by_old_code = {}
        for code, wards in old_units().items():
            for ward in wards:
                state = next((state_by_ward[c] for c in ward.new_codes if c in state_by_ward), None)
                if state:
                    state_by_old_code[code] = state
                    break
        old_codes_by_state = {}
        for code, state in state_by_old_code.items():
            old_codes_by_state.setdefault(state.id, []).append(code)
        provinces = {code: [name] for code, name in old_provinces().items()}
        for state in self.env["res.country.state"].search([("vn_old_code", "!=", False)]):
            provinces.setdefault(state.vn_old_code, []).append(state.name)
            # The province that kept its name is tried first.
            codes = old_codes_by_state.setdefault(state.id, [])
            if state.vn_old_code in codes:
                codes.insert(0, codes.pop(codes.index(state.vn_old_code)))
        return {
            "provinces": provinces,
            "state_by_old_code": state_by_old_code,
            "old_codes_by_state": old_codes_by_state,
            "wards": {},
        }

    def _prepare_line(self, partner, context):
        lines = (partner.street, partner.street2, partner.city)
        state = partner.state_id if partner.state_id.id in context["old_codes_by_state"] else self.env["res.country.state"]
        if not any(lines) and not state:
            return None  # no address to move
        if state:
            old_codes = context["old_codes_by_state"][state.id]
        else:
            code = find_province(lines, context["provinces"])
            state = context["state_by_old_code"].get(code, state)
            if not state and not partner.country_id:
                return None  # probably not in Vietnam
            old_codes = [code] if code else []
        new_wards = ()
        if state:
            if state.id not in context["wards"]:
                cities = self.env["res.city"].search([("state_id", "=", state.id), ("vn_code", "!=", False)])
                context["wards"][state.id] = [(city.vn_code, city.name) for city in cities]
            new_wards = context["wards"][state.id]

        # A contact on a merged province is read with each of the old provinces it took in.
        match = None
        for code in old_codes or [None]:
            match = match_address(lines, code, new_wards, context["provinces"])
            if match.new_codes:
                break
        candidates = self.env["res.city"].search([("vn_code", "in", match.new_codes)]) if match.new_codes else []
        found = len(candidates) == 1
        return {
            "partner_id": partner.id,
            "old_address": ", ".join(filter(None, [*lines, partner.state_id.name])),
            "candidate_ids": [Command.set(candidates.ids if candidates else [])],
            "status": "found" if found else "choose" if candidates else "not_found",
            "city_id": found and candidates.id,
            "street": clean_line(partner.street, match.consumed) or False,
            "street2": clean_line(partner.street2, match.consumed) or False,
            "apply": found,
        }

    def action_apply(self):
        lines = self.line_ids.filtered(lambda line: line.apply and line.city_id)
        for line in lines:
            city = line.city_id
            line.partner_id.write({
                "street": line.street,
                "street2": line.street2,
                "city_id": city.id,
                "city": city.name,
                "state_id": city.state_id.id,
                "zip": city.zipcode or line.partner_id.zip,
                "country_id": city.country_id.id,
            })
            line.partner_id.message_post(body=_("Address moved to the 2025 administrative units. It was: %s", line.old_address))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": _("%s addresses updated.", len(lines)),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class VnAddressConvertLine(models.TransientModel):
    _name = "vn.address.convert.line"
    _description = "Address to move to the 2025 administrative units"

    wizard_id = fields.Many2one("vn.address.convert", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", "Contact", required=True, readonly=True)
    old_address = fields.Char("Current address", readonly=True)
    status = fields.Selection(
        [("found", "Found"), ("choose", "Pick one"), ("not_found", "Not found")],
        readonly=True,
    )
    candidate_ids = fields.Many2many(
        "res.city", "vn_address_convert_line_candidate_rel", "line_id", "city_id",
        string="Possible wards", readonly=True,
        help="The old ward was split between these wards: pick the one of this address.",
    )
    city_id = fields.Many2one("res.city", "New ward")
    street = fields.Char()
    street2 = fields.Char()
    apply = fields.Boolean()

    @api.onchange("city_id")
    def _onchange_city_id(self):
        self.apply = bool(self.city_id)
