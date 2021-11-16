import json
import requests
from requests import Response

from odoo import fields, _
from odoo.exceptions import UserError

POSTNL_MESSAGE_PRINTER_TYPE = "GraphicFile|PDF"
POSTNL_CUSTOMER_ADDRESS_TYPE = "02"
POSTNL_SHIPMENTS_ADDRESS_TYPE = "01"
POSTNL_CONTACT_ADDRESS_TYPE = "01"


class PostNLAPI():

    def __init__(self, shipping_api_url, apikey, confirm_shipment):
        self.apikey = apikey
        if confirm_shipment:
            confirm_param = "?confirm=true"
        else:
            confirm_param = "?confirm=false"
        self.shipping_api_url = "{}{}".format(shipping_api_url, confirm_param)

    def send_postnl_package(self, pickings):
        """ Generates the shipment towards PostNL
            Using the Shipping webservice (/v1/shipment endpoint).
        """
        result = []
        for picking in pickings:
            self._validate_address(picking)

            response = requests.request(
                method="POST",
                url=self.shipping_api_url,
                headers={"apikey": self.apikey},
                data=self._get_shipment_request_body(picking))
            try:
                response.raise_for_status()
                response_body = response.json()
            except Exception as e:
                raise UserError(
                    _("PostNL API - invalid response! %s" % str(e))
                )
            carrier_tracking_ref = self._get_shipment_barcode(response_body)
            labels = self._get_shipment_labels(response_body, picking)
            picking.attach_postnl_labels(labels)

            shipping_data = {
                "exact_price": 0,  # PostNL does not provide the cost
                "tracking_number": carrier_tracking_ref,
                "labels": labels,
            }
            result.append(shipping_data)
        return result

    def _validate_address(self, picking):
        """ Validates the address before suppplying it to PostNL """
        if not picking.partner_id.country_id:
            raise UserError(
                    _("Partner address does not have a country set! ")
                )
        elif picking.partner_id.country_id.code != 'NL':
            raise UserError(
                    _("PostNL integration is only supported for packages to NL! ")
                )
        elif not picking.partner_id.city:
            raise UserError(
                    _("Partner address does not have mandatory information - city! ")
                )
        elif not picking.partner_id.zip:
            raise UserError(
                    _("Partner address does not have mandatory information - zip! ")
                )

    def _get_shipment_request_body(self, picking):
        """ Composes the request body/payload for the /v1/shipment call. """
        shipment = {
            "Customer": {
                "Address": {
                        "AddressType": POSTNL_CUSTOMER_ADDRESS_TYPE,  # sender address type
                        "City": picking.company_id.city,
                        "CompanyName": picking.company_id.name,
                        "Countrycode": picking.company_id.country_id.code,
                        "HouseNr": "42",
                        "Street": picking.company_id.street,
                        "Zipcode": picking.company_id.zip
                    },
                "CollectionLocation": "",
                "ContactPerson": "",
                "CustomerCode": picking.carrier_id.postnl_customer_code,
                "CustomerNumber": picking.carrier_id.postnl_customer_number,
                "Email": picking.company_id.email,
                "Name": picking.company_id.name,
            },
            "Message": {
                "MessageID": str(picking.id),
                "MessageTimeStamp": fields.Datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
                "Printertype": POSTNL_MESSAGE_PRINTER_TYPE,
            },
            "Shipments": {
                "Addresses": [
                {
                    "AddressType": POSTNL_SHIPMENTS_ADDRESS_TYPE,  # receiver address type
                    "City": picking.partner_id.city,
                    "Countrycode": picking.partner_id.country_id.code,
                    "FirstName": "",
                    "HouseNr": picking.partner_id.street_number,
                    "HouseNrExt": picking.partner_id.street_number2,
                    "Name": picking.partner_id.name,
                    "Street": picking.partner_id.street,
                    "Zipcode": picking.partner_id.zip,
                }
                ],
                "Contacts": [
                {
                    "ContactType": POSTNL_CONTACT_ADDRESS_TYPE,
                    "Email": picking.partner_id.email,
                    "SMSNr": picking.partner_id.mobile,
                    "TelNr": picking.partner_id.phone,
                }
                ],
                "Dimension": {
                    "Weight": str(picking.carrier_id._convert_weight_to_kg(picking.shipping_weight) * 1000)
                },  # weight in grams
                "ProductCodeDelivery": "3085"  # Standard shipment
            }
        }
        return shipment

    def _get_shipment_barcode(self, response_body):
        """ Retrieves the barcode from the response. """
        result = ""
        if response_body:
            response_body = response_body.get("ResponseShipments", [])
            result = response_body[0].get("Barcode")  # take the first shipment
        return result

    def _get_shipment_labels(self, response_body, picking):
        """ Retrieves the labels from the response. """
        result =[]
        if response_body:
            response_body = response_body.get("ResponseShipments", [])
            labels = response_body[0].get("Labels", [])
            file_type = "pdf"
            for label in labels:
                res_label = {
                    "name": picking.name,
                    "file": label["Content"],
                    "filename": "{}.{}".format(picking.name, file_type),
                    "file_type": file_type,
                }
                result.append(res_label)
        return result
