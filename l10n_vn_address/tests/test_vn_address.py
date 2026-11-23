from odoo.tests.common import BaseCase

from ..vn_address import clean_line, find_province, match_address, norm

PROVINCES = {"01": ["Hà Nội"], "79": ["Hồ Chí Minh"], "74": ["Bình Dương"], "26": ["Vĩnh Phúc"]}


class TestMatchAddress(BaseCase):
    def match(self, lines, province, new_wards=()):
        return match_address(lines, province, new_wards, PROVINCES)

    def test_norm(self):
        self.assertEqual(norm("P.01"), "p 1")
        self.assertEqual(norm("F1"), "f 1")
        self.assertEqual(norm("TP.HCM"), "tp hcm")
        self.assertEqual(norm("Đắk Lắk"), "dak lak")

    def test_ward_and_district(self):
        match = self.match(["12 Hàng Bún", "Phường Phúc Xá", "Quận Ba Đình"], "01")
        self.assertEqual(match.new_codes, ["00097"])  # Phường Hồng Hà
        self.assertEqual(clean_line("Phường Phúc Xá, Quận Ba Đình, Hà Nội", match.consumed), "")
        self.assertEqual(clean_line("12 Hàng Bún", match.consumed), "12 Hàng Bún")

    def test_abbreviations(self):
        match = self.match(["8 Nguyễn Huệ, P.Bến Nghé, Q.1, TP.HCM"], "79")
        self.assertEqual(match.new_codes, ["26740"])  # Phường Sài Gòn
        self.assertEqual(clean_line("8 Nguyễn Huệ, P.Bến Nghé, Q.1, TP.HCM", match.consumed), "8 Nguyễn Huệ")

    def test_numbered_ward_needs_its_district(self):
        # "Phường 1" exists in many districts of Hồ Chí Minh City.
        self.assertEqual(self.match(["45 Lê Lợi", "P1, Q3"], "79").new_codes, ["27154"])
        self.assertGreater(len(self.match(["45 Lê Lợi", "Phường 1"], "79").new_codes), 5)

    def test_split_ward(self):
        # Phường Cống Vị was split between Phường Ngọc Hà and Phường Giảng Võ.
        self.assertEqual(self.match(["P. Cống Vị, Ba Đình"], "01").new_codes, ["00008", "00025"])

    def test_merged_province(self):
        # Bình Dương (74) is part of Hồ Chí Minh City now.
        self.assertEqual(self.match(["Phú Cường", "TP Thủ Dầu Một"], "74").new_codes, ["25747"])

    def test_town_is_not_a_commune(self):
        # "Thị xã Sơn Tây" must not be read as "Xã Sơn Tây".
        self.assertEqual(self.match(["Phường Ngô Quyền", "Thị xã Sơn Tây"], "01").new_codes, ["09574"])

    def test_without_district(self):
        # Two "Xã Phú Cường" in Hà Nội: both are offered.
        self.assertEqual(self.match(["12 Đường ABC", "Xã Phú Cường"], "01").new_codes, ["00433", "09634"])

    def test_already_new(self):
        new_wards = [("00004", "Phường Ba Đình"), ("00008", "Phường Ngọc Hà")]
        self.assertEqual(self.match(["5 Kim Mã", "Phường Ngọc Hà"], "01", new_wards).new_codes, ["00008"])

    def test_names_that_differ_by_diacritics(self):
        # Huyện Trấn Yên had both Xã Minh Quán and Xã Minh Quân.
        self.assertEqual(self.match(["Xã Minh Quán", "Huyện Trấn Yên"], "15").new_codes, ["04498"])
        self.assertEqual(self.match(["Xã Minh Quân", "Huyện Trấn Yên"], "15").new_codes, ["04543"])

    def test_ward_named_like_its_district_or_a_province(self):
        self.assertEqual(self.match(["X. Chi Lăng, H. Chi Lăng"], "20").new_codes, ["06463"])
        self.assertEqual(self.match(["Long Biên", "Long Biên", "Hà Nội"], "01").new_codes, ["00118", "00145"])
        # Phường Vĩnh Phúc (Ba Đình) is not the province of Vĩnh Phúc.
        self.assertEqual(self.match(["Vĩnh Phúc", "Ba Đình", "Hà Nội"], "01").new_codes, ["00008"])

    def test_not_found(self):
        self.assertEqual(self.match(["5 Kim Mã"], "01").new_codes, [])

    def test_find_province(self):
        self.assertEqual(find_province(["1 Lê Lợi", "Q1", "TP.HCM"], PROVINCES), "79")
        self.assertEqual(find_province(["Phú Cường", "Thủ Dầu Một", "Tỉnh Bình Dương"], PROVINCES), "74")
        self.assertIsNone(find_province(["1 Lê Lợi"], PROVINCES))
