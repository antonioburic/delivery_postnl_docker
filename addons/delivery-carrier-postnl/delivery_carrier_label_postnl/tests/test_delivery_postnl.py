import base64
import requests
import uuid
from contextlib import contextmanager
from unittest.mock import patch
from unittest import mock
from odoo.tests.common import SavepointCase
from odoo.tests import tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestDeliveryPostNL(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super(TestDeliveryPostNL, cls).setUpClass()

        # set up the company and a partner/customer
        cls.company = cls.env.ref("base.main_partner")
        cls.company.write(
            {
                'name': 'NL Company',
                'street': 'Vondelstraat 87',
                'city': 'Amsterdam',
                'zip': '1054 GT',
                'phone': '+315566778899',
                'vat': 'NL123456782B90',
                'country_id': cls.env.ref('base.nl').id,
            }
        )

        cls.partner = cls.env["res.partner"].create(
            {
                'name': 'NL Partner',
                'street': 'Spaarbankstraat 5',
                'street2': False,
                'state_id': False,
                'city': 'Rotterdam',
                'zip': '3011 HX',
                'country_id': cls.env.ref('base.nl').id,
                'phone': '+31454534231'
            }
        )

        # set up the test product data
        product_category = cls.env["product.category"].create(
            {"name": "Test product category"}
        )
        product_template = cls.env["product.template"].create(
            {
                "name": "Test product",
                "type": "product",
                "categ_id": product_category.id,
                "is_product_variant": False,
                "weight": 1,
                "list_price": 10,
            }
        )
        product_barcode = str(uuid.uuid4())
        cls.product_variant = cls.env["product.product"].create(
            {
                "product_tmpl_id": product_template.id, 
                "barcode": product_barcode,
                "weight": 1,
            }
        )

    def test_01_postnl_ok_flow(self):
        orderline_vals = [
            (0, 0, {
                "product_id": self.product_variant.id,
                "product_uom_qty": 1.0,
                "price_unit": self.product_variant.lst_price
                })
            ]
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": orderline_vals,
                "carrier_id": self.env.ref('delivery_carrier_label_postnl.delivery_carrier_postnl_pakket').id,
            }
        )
        sale_order.get_delivery_price()
        self.assertTrue(sale_order.delivery_rating_success, "Postnl has not been able to rate this order (%s)" % sale_order.delivery_message)
        self.assertEquals(sale_order.delivery_price, 4.1, "PostNL shipping price is not correct.")
        sale_order.set_delivery_line()

        sale_order.action_confirm()
        self.assertEquals(len(sale_order.picking_ids), 1, "The Sales Order did not generate a picking.")

        picking = sale_order.picking_ids[0]
        self.assertEquals(picking.carrier_id.id, sale_order.carrier_id.id, "Carrier is not the same on Picking and on SO.")

        picking.move_lines[0].quantity_done = 1.0
        self.assertEquals(picking.shipping_weight, 1.0, "Picking weight should be 1.")

        test_barcode = "12345"
        with self._setup_mock_ok_request(barcode=test_barcode):
            picking.action_done()

        self.assertEquals(picking.carrier_tracking_ref, test_barcode, "Incorrect tracking reference.")

    def test_02_postnl_error_invalid_apikey(self):
        orderline_vals = [
            (0, 0, {
                "product_id": self.product_variant.id,
                "product_uom_qty": 1.0,
                "price_unit": self.product_variant.lst_price
                })
            ]
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": orderline_vals,
                "carrier_id": self.env.ref("delivery_carrier_label_postnl.delivery_carrier_postnl_pakket").id,
            }
        )
        sale_order.get_delivery_price()
        sale_order.set_delivery_line()
        sale_order.action_confirm()
        picking = sale_order.picking_ids[0]
        picking.move_lines[0].quantity_done = 1.0

        # setting an invalid API key
        sale_order.carrier_id.postnl_api_key = "1234567"

        with self.assertRaises(UserError), self._setup_mock_invalid_apikey_request():
            picking.action_done()

    def test_03_postnl_tracking_link(self):
        orderline_vals = [
            (0, 0, {
                "product_id": self.product_variant.id,
                "product_uom_qty": 25.0,
                "price_unit": self.product_variant.lst_price
                })
            ]
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": orderline_vals,
                "carrier_id": self.env.ref("delivery_carrier_label_postnl.delivery_carrier_postnl_pakket").id,
            }
        )
        sale_order.get_delivery_price()
        sale_order.set_delivery_line()
        sale_order.action_confirm()
        picking = sale_order.picking_ids[0]
        picking.move_lines[0].quantity_done = 1.0

        test_barcode = "12345"
        with self._setup_mock_ok_request(barcode=test_barcode):
            picking.action_done()

        tracking_link = sale_order.carrier_id.get_tracking_link(picking)
        param_obj = self.env["ir.config_parameter"].sudo()
        base_url = param_obj.get_param("postnl_tracking_base_url", default=False)
        self.assertEquals(tracking_link, "{}/{}-NL-{}".format(base_url, test_barcode, self.partner.zip), "Incorrect tracking URL.")

    @staticmethod
    @contextmanager
    def _setup_mock_ok_request(barcode):
        with patch("odoo.addons.delivery_carrier_label_postnl.models.postnl_api.requests") as mock_requests:
            response_mock = mock.Mock()
            type(response_mock).status_code = mock.PropertyMock(return_value=205)
            response_mock.json.return_value =  {
                "ResponseShipments": [
                    {
                        "Barcode": barcode,
                        "Labels": [
                            {
                                "Content": base64.b64encode(b"3SDEVC6659149"),
                                "Labeltype": "Label",
                            }
                        ],
                    }
                ]
            }
            mock_requests.request.return_value = response_mock
            yield mock_requests

    @staticmethod
    @contextmanager
    def _setup_mock_invalid_apikey_request():
        with patch("odoo.addons.delivery_carrier_label_postnl.models.postnl_api.requests") as mock_requests:
            response_mock = mock.Mock()
            type(response_mock).status_code = mock.PropertyMock(return_value=401)
            response_mock.json.return_value =  {
                "fault": {
                    "faultstring": "Invalid ApiKey",
                    "detail": {
                        "errorcode": "oauth.v2.InvalidApiKey"
                    }
                }
            }
            response_mock.raise_for_status.side_effect = requests.exceptions.HTTPError
            mock_requests.request.return_value = response_mock
            yield mock_requests

