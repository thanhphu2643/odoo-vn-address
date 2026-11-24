from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVnAddress(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref("base.vn")
        cls.hanoi = cls.env.ref("base.state_vn_VN-HN")
        cls.hcm = cls.env.ref("base.state_vn_VN-SG")

    def ward(self, code):
        return self.env.ref(f"l10n_vn_address.ward_{code}")

    def test_data(self):
        states = self.env["res.country.state"].search([("country_id", "=", self.vn.id)])
        # Odoo 19 ships the 34 current provinces; the module adds their codes and the wards.
        self.assertEqual(len(states), 34)
        self.assertEqual(len(states.filtered("vn_code")), 34)
        self.assertEqual(self.env["res.city"].search_count([("vn_code", "!=", False)]), 3321)
        self.assertTrue(self.vn.enforce_cities)
        self.assertEqual(self.ward("25747").state_id, self.hcm)  # Thủ Dầu Một is in Hồ Chí Minh City now

    def test_province_search(self):
        State = self.env["res.country.state"].with_context(country_id=self.vn.id)
        names = [name for _id, name in State.name_search("ho chi minh")]
        self.assertEqual(names, ["Hồ Chí Minh (VN)"])
        self.assertFalse(State.name_search("Bình Dương"))  # merged into Hồ Chí Minh City

    def test_ward_search_without_diacritics(self):
        ids = [id_ for id_, _name in self.env["res.city"].name_search("phuong ba dinh")]
        self.assertIn(self.ward("00004").id, ids)

    def test_picking_a_ward_sets_the_province(self):
        with Form(self.env["res.partner"]) as form:
            form.name = "Khách lẻ"
            form.country_id = self.vn
            form.city_id = self.ward("00004")
        partner = form.save()
        self.assertEqual(partner.state_id, self.hanoi)
        self.assertEqual(partner.city, "Phường Ba Đình")
        self.assertEqual(partner.zip, "11120")

    def test_convert(self):
        Partner = self.env["res.partner"]
        found = Partner.create({
            "name": "Found", "street": "12 Hàng Bún", "street2": "Phường Phúc Xá",
            "city": "Quận Ba Đình", "state_id": self.hanoi.id, "country_id": self.vn.id,
        })
        # Already on the new province, but the street still names the old Bình Dương units.
        merged = Partner.create({
            "name": "Merged", "street": "1 Yersin, P. Phú Cường, TP. Thủ Dầu Một",
            "state_id": self.hcm.id, "country_id": self.vn.id,
        })
        old_province = Partner.create({"name": "Old province", "street": "1 Yersin, P. Phú Cường, Thủ Dầu Một, Bình Dương"})
        no_state = Partner.create({"name": "No state", "street": "8 Nguyễn Huệ, P.Bến Nghé, Q.1, TP.HCM"})
        split = Partner.create({
            "name": "Split", "street": "3 Giảng Võ", "street2": "P. Cống Vị",
            "city": "Ba Đình", "state_id": self.hanoi.id, "country_id": self.vn.id,
        })
        employee = Partner.create({"name": "Employee", "parent_id": found.id, "type": "contact"})
        partners = found | merged | old_province | no_state | split | employee

        wizard = Form(self.env["vn.address.convert"].with_context(active_model="res.partner", active_ids=partners.ids))
        lines = {line.partner_id: line for line in wizard.save().line_ids}
        self.assertNotIn(employee, lines)  # follows its company
        self.assertEqual(lines[found].status, "found")
        self.assertEqual(lines[found].city_id, self.ward("00097"))
        self.assertEqual(lines[merged].city_id, self.ward("25747"))
        self.assertEqual(lines[merged].street, "1 Yersin")
        self.assertEqual(lines[old_province].city_id, self.ward("25747"))
        self.assertEqual(lines[no_state].city_id, self.ward("26740"))
        self.assertEqual(lines[split].status, "choose")
        self.assertEqual(lines[split].candidate_ids, self.ward("00008") | self.ward("00025"))
        self.assertFalse(lines[split].apply)

        lines[split].write({"city_id": self.ward("00025").id, "apply": True})
        lines[found].wizard_id.action_apply()

        self.assertRecordValues(found, [{
            "street": "12 Hàng Bún", "street2": False, "city": "Phường Hồng Hà",
            "city_id": self.ward("00097").id, "state_id": self.hanoi.id, "zip": "11025",
        }])
        self.assertEqual(employee.city_id, self.ward("00097"))
        self.assertEqual(merged.state_id, self.hcm)
        self.assertEqual(no_state.country_id, self.vn)
        self.assertEqual(split.city_id, self.ward("00025"))
        self.assertIn("Phường Phúc Xá", found.message_ids[0].body)
