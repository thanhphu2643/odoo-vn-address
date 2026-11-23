#!/usr/bin/env python3
"""Rebuild the data files of l10n_vn_address from the published datasets.

    python3 tools/build_data.py

Sources (all MIT licensed, pinned to a commit so the output is reproducible):

- Current units (34 provinces, wards with postal codes):
  thanglequoc/vietnamese-provinces-database v5.2.0 (up to 388/NQ-UBTVQH16)
- Units before 1 July 2025 (63 provinces, districts, wards):
  thanglequoc/vietnamese-provinces-database v2.4.1
- Which new ward(s) each old ward became:
  dvhcvn/20250701 mapping/splits.json
"""

import csv
import json
import pathlib
import unicodedata
import urllib.request

NEW_URL = (
    "https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/"
    "62b1abdfe39625289c37a58ef6678e9db3d37f84/json/simplified_json_generated_data_vn_units.json"
)
OLD_URL = (
    "https://raw.githubusercontent.com/ThangLeQuoc/vietnamese-provinces-database/"
    "fc33b7411ec4e3697817fab8118718a8d39ef090/json/simplified_json_generated_data_vn_units.json"
)
SPLITS_URL = (
    "https://raw.githubusercontent.com/dvhcvn/20250701/"
    "dd94887ce32324380bc5bb0a76fe39867dafc73b/mapping/splits.json"
)

# Odoo 16 ships the 63 provinces from before the 2025 reform as base.state_vn_*.
# Their code (pre-2025, from the General Statistics Office) in the old dataset:
ODOO_STATES = {
    "state_vn_VN-HN": "01", "state_vn_VN-03": "02", "state_vn_VN-04": "04", "state_vn_VN-53": "06",
    "state_vn_VN-07": "08", "state_vn_VN-02": "10", "state_vn_VN-71": "11", "state_vn_VN-01": "12",
    "state_vn_VN-05": "14", "state_vn_VN-06": "15", "state_vn_VN-14": "17", "state_vn_VN-69": "19",
    "state_vn_VN-09": "20", "state_vn_VN-13": "22", "state_vn_VN-54": "24", "state_vn_VN-68": "25",
    "state_vn_VN-70": "26", "state_vn_VN-56": "27", "state_vn_VN-61": "30", "state_vn_VN-HP": "31",
    "state_vn_VN-66": "33", "state_vn_VN-20": "34", "state_vn_VN-63": "35", "state_vn_VN-67": "36",
    "state_vn_VN-18": "37", "state_vn_VN-21": "38", "state_vn_VN-22": "40", "state_vn_VN-23": "42",
    "state_vn_VN-24": "44", "state_vn_VN-25": "45", "state_vn_VN-26": "46", "state_vn_VN-DN": "48",
    "state_vn_VN-27": "49", "state_vn_VN-29": "51", "state_vn_VN-31": "52", "state_vn_VN-32": "54",
    "state_vn_VN-34": "56", "state_vn_VN-36": "58", "state_vn_VN-40": "60", "state_vn_VN-28": "62",
    "state_vn_VN-30": "64", "state_vn_VN-33": "66", "state_vn_VN-72": "67", "state_vn_VN-35": "68",
    "state_vn_VN-58": "70", "state_vn_VN-37": "72", "state_vn_VN-57": "74", "state_vn_VN-39": "75",
    "state_vn_VN-43": "77", "state_vn_VN-SG": "79", "state_vn_VN-41": "80", "state_vn_VN-46": "82",
    "state_vn_VN-50": "83", "state_vn_VN-51": "84", "state_vn_VN-49": "86", "state_vn_VN-45": "87",
    "state_vn_VN-44": "89", "state_vn_VN-47": "91", "state_vn_VN-CT": "92", "state_vn_VN-73": "93",
    "state_vn_VN-52": "94", "state_vn_VN-55": "95", "state_vn_VN-59": "96",
}

MODULE = pathlib.Path(__file__).resolve().parent.parent / "l10n_vn_address"


def fetch(url):
    with urllib.request.urlopen(url) as response:
        return json.load(response)


def key(name):
    """Compare names regardless of tone mark placement (Hoà / Hòa)."""
    text = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def unit_type(full_name, name):
    kind = full_name[: -len(name)].strip()
    return kind[:1].upper() + kind[1:]


def main():
    new, old, splits = fetch(NEW_URL), fetch(OLD_URL), fetch(SPLITS_URL)

    # Every new province kept the name of one of the old ones: reuse that Odoo state.
    old_name_to_code = {key(p["Name"]): p["Code"] for p in old}
    xmlid_by_old_code = {code: xmlid for xmlid, code in ODOO_STATES.items()}
    xmlid_by_new_code = {}
    states = {xmlid: {"name": "", "vn_code": "", "vn_old_code": code} for xmlid, code in ODOO_STATES.items()}
    old_names = {p["Code"]: p["Name"] for p in old}
    for province in new:
        xmlid = xmlid_by_old_code[old_name_to_code[key(province["Name"])]]
        xmlid_by_new_code[province["Code"]] = xmlid
        states[xmlid].update(name=province["Name"], vn_code=province["Code"])
    assert len(xmlid_by_new_code) == 34, len(xmlid_by_new_code)

    with open(MODULE / "data" / "res.country.state.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "name", "vn_code", "vn_old_code", "vn_replaced"])
        for xmlid, state in sorted(states.items(), key=lambda item: item[1]["vn_old_code"]):
            replaced = not state["vn_code"]
            name = old_names[state["vn_old_code"]] if replaced else state["name"]
            writer.writerow([f"base.{xmlid}", name, state["vn_code"], state["vn_old_code"], replaced])

    wards = set()
    with open(MODULE / "data" / "res.city.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "name", "vn_code", "zipcode", "country_id:id", "state_id:id"])
        for province in new:
            for ward in province["Wards"]:
                name = unit_type(ward["FullName"], ward["Name"]) + " " + ward["Name"]
                wards.add(ward["Code"])
                writer.writerow([
                    f"ward_{ward['Code']}", name, ward["Code"], ward["PostalCode"],
                    "base.vn", f"base.{xmlid_by_new_code[province['Code']]}",
                ])

    new_codes = {
        ward["level3_id"]: [s["new_id"] for s in ward["splits"] if s["new_id"] in wards]
        for province in splits["data"]
        for ward in province["level3s"]
    }
    rows, unmapped = [], 0
    for province in old:
        for district in province["District"]:
            for ward in district.get("Ward") or []:
                targets = new_codes.get(ward["Code"], [])
                unmapped += not targets
                rows.append([
                    ward["Code"], unit_type(ward["FullName"], ward["Name"]), ward["Name"],
                    district["Code"], unit_type(district["FullName"], district["Name"]), district["Name"],
                    province["Code"], " ".join(targets),
                ])
    with open(MODULE / "data" / "vn_units_2024.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["ward_code", "ward_type", "ward_name", "district_code", "district_type",
                         "district_name", "province_code", "new_ward_codes"])
        writer.writerows(rows)

    print(f"{len(xmlid_by_new_code)} provinces, {len(wards)} wards, "
          f"{len(rows)} old wards ({unmapped} without a new ward)")


if __name__ == "__main__":
    main()
