from odoo import models, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_generate_carrier_label(self):
        """ Inherited from base_delivery_carrier_label module
            We have already created labels during the delivery_carrier.postnl_send_shipping call,
            so this part is not needed in this step, skipping.
        """
        return super(StockPicking, self.filtered(lambda x: x.carrier_id.delivery_type != "postnl")).action_generate_carrier_label()

    @api.multi
    def generate_shipping_labels(self):
        """ Label generation for PostNL is not needed here, as it's already been done
        with the delivery_carrier.postnl_send_shipping call. """
        self.ensure_one()
        if self.carrier_id.delivery_type == "postnl":
            return super(StockPicking, self.filtered(lambda x: x.carrier_id.delivery_type != "postnl")).generate_shipping_labels()
        return super().generate_shipping_labels()

    def attach_postnl_labels(self, labels):
        """ Sets a default package and attaches labels. """
        self.ensure_one()

        self._set_a_default_package()
        for label in labels:
                self.attach_shipping_label(label)
