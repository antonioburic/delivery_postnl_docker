import base64
from odoo import models, fields, _
from odoo.exceptions import UserError
from .postnl_api import PostNLAPI


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(selection_add=[("postnl", "PostNL")])
    postnl_api_key = fields.Char(string="PostNL API Key")
    postnl_customer_code = fields.Char(string="PostNL Customer Code")
    postnl_customer_number = fields.Char(string="PostNL Customer Number")
    postnl_confirm_shipment = fields.Boolean(string="Confirm Shipment When Sending (PostNL)", default=True)

    def postnl_rate_shipment(self, order):
        """ Compute the price of the order shipment with PostNL.
        PostNL does not offer an API to retrieve rates, but we can maintain the current
        package costs by weight retrieved from the products defined in the module data.

        :param order: record of sale.order
        :return dict: {'success': boolean,
                       'price': a float,
                       'error_message': a string containing an error message,
                       'warning_message': a string containing a warning message}
        """
        self.ensure_one()
        weight = sum([(line.product_id.weight * line.product_qty) for line in order.order_line]) or 0.0
        price = self._get_postnl_pakket_rate(weight)

        # convert from EUR if another currency
        eur_currency = self.env.ref("base.EUR", raise_if_not_found=False)
        if order.currency_id != eur_currency:
            price = eur_currency._convert(price, order.currency_id, order.company_id, order.date_order or fields.Date.today())

        return {
            'success': True,
            'price': price,
            'error_message': False,
            'warning_message': "Please make sure to have the latest PostNL product prices, as the PostNL API does not retrieve them."
        }

    def postnl_send_shipping(self, pickings):
        """ Send the package to PostNL.

        :param pickings: A recordset of pickings
        :return list: A list of dictionaries (one per picking) containing of the form::
                         { 'exact_price': price,
                           'tracking_number': number }
        """
        self.ensure_one()

        ParamObj = self.env["ir.config_parameter"].sudo()
        if self.prod_environment:
            shipping_api_url = ParamObj.get_param("postnl_shipping_api_prod_url", default="https://api.postnl.nl/v1/shipment")
        else:
            shipping_api_url = ParamObj.get_param("postnl_shipping_api_test_url", default="https://api-sandbox.postnl.nl/v1/shipment")

        apikey = self.postnl_api_key
        if not apikey:
            raise UserError(_("PostNL API key is not configured!"))
        postnl = PostNLAPI(shipping_api_url, apikey, self.postnl_confirm_shipment)
        return postnl.send_postnl_package(pickings)

    def postnl_get_tracking_link(self, picking):
        """ Ask the tracking link to PostNL.

        :param picking: record of stock.picking
        :return str: an URL containing the tracking link or False
        """
        self.ensure_one()
        res = ''
        param_obj = self.env["ir.config_parameter"].sudo()
        base_url = param_obj.get_param("postnl_tracking_base_url", default=False)
        if base_url:
            zip_code = picking.partner_id.zip
            carrier_tracking_ref = picking.carrier_tracking_ref
            if zip_code and carrier_tracking_ref:
                res = "{}/{}-NL-{}".format(base_url, carrier_tracking_ref, zip_code)
        return res

    def postnl_cancel_shipment(self, pickings):
        """ Cancel a PostNL shipment, which is not supported via an API.

        :param pickings: A recordset of pickings
        """
        raise NotImplementedError(_("PostNL does not allow canceling the shipment!"))

    def _convert_weight_to_kg(self, weight):
        """ Converts weight into kilograms. """
        weight_uom_id = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()
        return weight_uom_id._compute_quantity(weight, self.env.ref("uom.product_uom_kgm"), round=False)

    def _get_postnl_pakket_rate(self, weight):
        """ Gets the package prices from the predefined service products,
        by taking the total weight:

        'product_product_delivery_postnl_pakket_2' - 0-2kg
        'product_product_delivery_postnl_pakket_10' - 2-10kg
        'product_product_delivery_postnl_pakket_23' - 10-23kg

        """
        weight = self._convert_weight_to_kg(weight)
        if weight <= 2:
            xml_id = "delivery_carrier_label_postnl.product_product_delivery_postnl_pakket_2"
        elif weight <= 10:
            xml_id = "delivery_carrier_label_postnl.product_product_delivery_postnl_pakket_10"
        else:
            xml_id = "delivery_carrier_label_postnl.product_product_delivery_postnl_pakket_23"
        package_product = self.env.ref(xml_id, raise_if_not_found=False)
        return package_product and package_product.list_price or 0.0
