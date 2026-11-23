"""Find the post-reform ward of a Vietnamese address.

On 1 July 2025 Vietnam went from province / district / ward to province / ward:
63 provinces became 34, districts were abolished and about 10,000 wards became
3,321. This module reads an address written with the old units ("P. Phúc Xá,
Q. Ba Đình, Hà Nội") and returns the code(s) of the ward it belongs to now.

No Odoo import here: the matching is plain Python and tested as such.
"""

import csv
import functools
import pathlib
import re
import unicodedata
from collections import namedtuple

OLD_UNITS = pathlib.Path(__file__).parent / "data" / "vn_units_2024.csv"

# How each kind of unit is written in practice ("Phường 1", "P.1", "F1", "p1").
WARD_PREFIXES = {
    "Phường": ("phuong", "p", "f"),
    "Xã": ("xa", "x"),
    "Thị trấn": ("thi tran", "tt"),
    "Đặc khu": ("dac khu",),
}
DISTRICT_PREFIXES = {
    "Quận": ("quan", "q"),
    "Huyện": ("huyen", "h"),
    "Thị xã": ("thi xa", "tx"),
    "Thành phố": ("thanh pho", "tp"),
}
PROVINCE_PREFIXES = ("tinh", "thanh pho", "tp", "t")
PROVINCE_ALIASES = {
    "79": ("hcm", "tphcm", "tp hcm", "sai gon", "saigon", "ho chi minh city"),
    "01": ("hn", "tphn"),
    "46": ("thua thien hue", "thua thien"),
    "77": ("brvt", "ba ria vung tau"),
}
COUNTRY = ("viet nam", "vietnam", "vn")

Unit = namedtuple("Unit", "code kind name")
OldWard = namedtuple("OldWard", "ward district new_codes")
Match = namedtuple("Match", "new_codes consumed")


def fold(text):
    """Lower case without diacritics: "Đắk Lắk" -> "dak lak"."""
    text = unicodedata.normalize("NFD", (text or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def norm(text):
    """Fold and tidy so that "P.01", "p1" and "Phường 1" compare as "p 1" / "phuong 1"."""
    text = re.sub(r"(?<=[a-z])(?=\d)", " ", fold(text))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b0+(?=\d)", "", text)
    return " ".join(text.split())


def split(*lines):
    """Comma separated parts of the address lines, as written."""
    return [part.strip() for line in lines for part in re.split(r"[,;\n]+", line or "") if part.strip()]


@functools.lru_cache(maxsize=None)
def old_units():
    """Wards before the reform, grouped by the province code they had then."""
    by_province = {}
    with open(OLD_UNITS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_province.setdefault(row["province_code"], []).append(OldWard(
                Unit(row["ward_code"], row["ward_type"], row["ward_name"]),
                Unit(row["district_code"], row["district_type"], row["district_name"]),
                tuple(row["new_ward_codes"].split()),
            ))
    return by_province


def unit_from_full_name(code, full_name):
    """("00004", "Phường Ba Đình") -> Unit("00004", "Phường", "Ba Đình")."""
    for kind in WARD_PREFIXES:
        if full_name.startswith(kind + " "):
            return Unit(code, kind, full_name[len(kind) + 1:])
    return Unit(code, "", full_name)


def variants(unit, prefixes):
    """Every normalized way to write the unit with its kind, plus the bare name."""
    name = norm(unit.name)
    return [f"{prefix} {name}" for prefix in prefixes.get(unit.kind, ())], name


def province_variants(name, code=None):
    base = norm(name)
    return {base, *(f"{prefix} {base}" for prefix in PROVINCE_PREFIXES), *PROVINCE_ALIASES.get(code, ())}


def _contains(segment, variant):
    return f" {variant} " in f" {segment} "


def _remove(segment, variants_):
    for variant in sorted(variants_, key=len, reverse=True):
        segment = f" {segment} ".replace(f" {variant} ", " ").strip()
    return segment


def _find(segments, unit, prefixes, bare_segments=None):
    """How `unit` appears in the segments: (score, texts), or (None, []) when it does not.

    Written with its kind ("Phường X", "Q. Y") anywhere in a segment scores 1.
    The bare name ("Ba Đình") scores 0 and only counts as a whole segment of
    `bare_segments`.
    """
    prefixed, bare = variants(unit, prefixes)
    if any(_contains(segment, variant) for segment in segments for variant in prefixed):
        return 1, [*prefixed, bare]
    if bare_segments is not None and not bare.isdigit() and bare in bare_segments:
        return 0, [*prefixed, bare]
    return None, []


def find_province(lines, provinces):
    """Code of the first province named in the address, read from the end.

    `provinces` maps a (pre-reform) province code to its names.
    """
    for segment in reversed([norm(part) for part in split(*lines)]):
        for code, names in provinces.items():
            if any(segment in province_variants(name, code) for name in names):
                return code
    return None


def match_address(lines, old_province_code=None, new_wards=(), provinces=None):
    """Find the current ward(s) of an address.

    lines: the address lines, e.g. (street, street2, city)
    old_province_code: code of the province before the reform
    new_wards: (code, full name) of the wards of the province when it is a
        current one, to recognise addresses already written with new units
    provinces: province names by pre-reform code, to tell them from ward names
        and remove them when cleaning the lines

    Returns Match(new_codes, consumed): the candidate ward codes (one when the
    answer is certain) and the normalized texts that describe the old units,
    which clean_line() removes from the street lines.
    """
    provinces = provinces or {}
    parts = split(*lines)
    segments = [norm(part) for part in parts]
    written = " , ".join(unicodedata.normalize("NFC", part).lower() for part in parts)
    own = set(PROVINCE_ALIASES.get(old_province_code, ()))
    for name in provinces.get(old_province_code, ()):
        own |= province_variants(name, old_province_code)
    consumed = own | set(COUNTRY)
    for code, names in provinces.items():
        consumed |= {variant for name in names for variant in province_variants(name, code)}
    bare_segments = [segment for segment in segments if segment not in own]
    old = old_units().get(old_province_code, [])

    # 1. "Phường X, Quận Y": the district tells which of the same-named wards it is.
    districts, district_texts, district_prefixed = {}, [], []
    for district in {ward.district for ward in old}:
        score, found = _find(segments, district, DISTRICT_PREFIXES, bare_segments)
        if found:
            districts[district.code] = score
            district_texts += found
            district_prefixed += found[:-1]
    if districts:
        # Without "Thị xã Sơn Tây", the segment is not read as "Xã Sơn Tây".
        rest = [_remove(segment, district_prefixed) for segment in segments]
        rest_bare = [segment for segment in rest if segment and segment not in own]
        district_names = {norm(ward.district.name) for ward in old if ward.district.code in districts}
        hits = []
        for ward in old:
            if ward.district.code in districts:
                score, found = _find(rest, ward.ward, WARD_PREFIXES, rest_bare)
                if found:
                    # A bare "Long Biên" is the district before being a ward of it.
                    shadowed = score == 0 and found[-1] in district_names
                    hits.append((2 * score + districts[ward.district.code] - shadowed, ward, found))
        if hits:
            return _result(hits, written, consumed | set(district_texts))

    # 2. Already written with the new units: "Phường Ba Đình, Hà Nội".
    hits = []
    for code, full_name in new_wards:
        unit = unit_from_full_name(code, full_name)
        score, found = _find(segments, unit, WARD_PREFIXES, bare_segments)
        if found:
            hits.append((score, OldWard(unit, None, (code,)), found))
    if hits:
        return _result(hits, written, consumed)

    # 3. An old ward without its district: only when written with its kind ("Xã ...").
    hits = []
    for ward in old:
        score, found = _find(segments, ward.ward, WARD_PREFIXES)
        if found:
            hits.append((score, ward, found))
    return _result(hits, written, consumed | set(district_texts))


def _result(hits, written, consumed):
    """Keep the best written matches, then those with the exact diacritics."""
    best = max((score for score, _ward, _found in hits), default=None)
    hits = [(ward, found) for score, ward, found in hits if score == best]
    # "Xã Ngư Thủy" is also found inside "Xã Ngư Thủy Bắc": keep the longest name.
    names = {norm(ward.ward.name) for ward, _found in hits}
    hits = [(ward, found) for ward, found in hits
            if not any(name != norm(ward.ward.name) and _contains(name, norm(ward.ward.name)) for name in names)]
    # "Minh Quán" and "Minh Quân" fold to the same text: the diacritics decide.
    exact = [(ward, found) for ward, found in hits if ward.ward.name.lower() in written]
    if exact and len({ward.new_codes for ward, _found in hits}) > 1:
        hits = exact
    codes = sorted({code for ward, _found in hits for code in ward.new_codes})
    consumed |= {text for _ward, found in hits for text in found}
    return Match(codes, consumed)


def clean_line(line, consumed):
    """Drop the parts of an address line that only name administrative units."""
    kept = [part for part in split(line) if _remove(norm(part), consumed)]
    return ", ".join(kept)
