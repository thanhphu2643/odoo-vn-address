{
    "name": "Vietnam Addresses 2025",
    "summary": "The 34 provinces and 3,321 wards in effect since 1 July 2025, "
    "and a tool to move existing addresses to them",
    "version": "16.0.1.0.0",
    "category": "Localization",
    "author": "Nguyen Thanh Phu",
    "website": "https://github.com/thanhphu2643/odoo-vn-address",
    "license": "LGPL-3",
    "depends": ["base_address_extended", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "data/res.country.state.csv",
        "data/res.city.csv",
        "views/res_partner_views.xml",
        "views/res_country_views.xml",
        "data/res_country_data.xml",
        "wizard/vn_address_convert_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
}
