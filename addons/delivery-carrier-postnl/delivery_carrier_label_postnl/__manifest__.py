# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "PostNL Carrier Implementation",
    "summary": """
        Implements a new delivery carrier: PostNL
    """,
    "category": "Stock",
    "version": "12.0.1.0.0",
    "website": "https://github.com/OCA/delivery-carrier",
    "author": "antonio.burich@gmail.com",
    "license": "AGPL-3",
    "depends": [
        "base_address_extended",
        "base_delivery_carrier_label",
    ],
    "data": [
        "data/delivery_carrier_label_postnl_data.xml",
        "data/ir_config_parameter.xml",
        "views/delivery_carrier_views.xml",
    ],
    "installable": True,
}
