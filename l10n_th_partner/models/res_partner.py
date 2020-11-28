# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
import logging
from logging import CRITICAL, INFO

import zeep
from zeep import client

from odoo import api, fields, models
from requests import Session
from zeep import Client
from zeep.transports import Transport

from odoo.api import onchange

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    branch = fields.Char(string="Tax Branch",
                         help="Branch ID, e.g., 0000, 0001, ...")
    check_tax_id = fields.Boolean(string="Check Tax ID with Revenue Department")
    name_company = fields.Char(
        string="Name Company", inverse="_inverse_name_company", index=True
    )

    @api.model
    def create(self, vals):
        """Add inverted company names at creation if unavailable."""
        context = dict(self.env.context)
        name = vals.get("name", context.get("default_name"))
        if vals.get("is_company", False) and name:
            vals["name_company"] = name
        return super().create(vals)

    def _inverse_name_company(self):
        for rec in self:
            if not rec.is_company or not rec.name:
                rec.name_company = False
            else:
                rec.name_company = rec.name

    @api.model
    def _get_computed_name(self, lastname, firstname):
        name = super()._get_computed_name(lastname, firstname)
        title = self.title.name
        if name and title:
            return " ".join(p for p in (title, name) if p)
        return name

    @api.depends(
        "title", "firstname", "lastname", "name_company", "partner_company_type_id"
    )
    def _compute_name(self):
        for rec in self:
            if not rec.is_company:
                super()._compute_name()
                continue
            prefix = rec.partner_company_type_id.prefix
            suffix = rec.partner_company_type_id.suffix
            rec.name = " ".join(p for p in (
                prefix, rec.name_company, suffix) if p)
            rec._inverse_name()

    @api.onchange("company_type")
    def _onchange_company_type(self):
        if self.company_type == "company":
            self.title = False
        else:
            self.partner_company_type_id = False

    @api.model
    def _install_l10n_th_partner(self):
        records = self.search([("name_company", "=", False)])
        records._inverse_name_company()
        _logger.info("%d partners updated installing module.", len(records))

    def action_view_partner_check_tax_id(self):
        _logger.log(INFO, self.vat)
        if len(self.vat) == 13:
            sess = Session()
            sess.verify = False
            transp = Transport(session=sess)
            cl = Client('https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx?wsdl',
                        transport=transp)
            result = cl.service.Service(
                username='anonymous',
                password='anonymous',
                TIN=self.vat,
                ProvinceCode=0,
                BranchNumber=0,
                AmphurCode=9)
            result = zeep.helpers.serialize_object(result)
            _logger.log(INFO, result)
            name_company = result['vtitleName'].get(
                'anyType', None)[0] + result['vName'].get('anyType', None)[0]
            street = result['vBuildingName'].get('anyType', None)[0] + result['vFloorNumber'].get('anyType', None)[
                0] + result['vVillageName'].get('anyType', None)[0] + result['vBuildingName'].get('anyType', None)[0]
            self.update({"name_company": name_company, "street": street})

    @api.onchange("vat")
    def _onchange_vat(self):
        _logger.log(INFO, self.vat)
        if self.vat != False and len(self.vat) == 13:
            sess = Session()
            sess.verify = False
            transp = Transport(session=sess)
            cl = Client('https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx?wsdl',
                        transport=transp)
            result = cl.service.Service(
                username='anonymous',
                password='anonymous',
                TIN=self.vat,
                ProvinceCode=0,
                BranchNumber=0,
                AmphurCode=9)
            result = zeep.helpers.serialize_object(result)
            _logger.log(INFO, result)
            name_company = result['vtitleName'].get(
                'anyType', None)[0] + result['vName'].get('anyType', None)[0]
            street = result['vBuildingName'].get('anyType', None)[0] + result['vFloorNumber'].get('anyType', None)[
                0] + result['vVillageName'].get('anyType', None)[0] + result['vBuildingName'].get('anyType', None)[0]
            self.update({"name_company": name_company, "street": street})
