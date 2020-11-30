# Copyright 2019 Ecosoft Co., Ltd (http://ecosoft.co.th/)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html)
import logging
from logging import CRITICAL, INFO
import re
from re import T
from typing import Dict
import requests

from requests.sessions import OrderedDict

from odoo import api, fields, models, _, exceptions
from odoo.api import onchange

from requests import Session
from zeep import Client, Transport, helpers
from os import path
from pathlib import Path
import pprint


_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    branch = fields.Char(string="Tax Branch",
                         help="Branch ID, e.g., 0000, 0001, ...",
                         default="00000")
    rd_webservices = fields.Boolean(string="Verify and pull data from Revenue Department's web services.")
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

    @staticmethod
    def check_rd_tin_service(tin):
        """Return bool after verifiying Tax Identification Number (TIN) or Personal Identification Number (PIN) 
           by using Revenue Department's web service to prevent forging.

           :param tin: a string for TIN or PIN
        """

        tin_web_service_url = "https://rdws.rd.go.th/serviceRD3/checktinpinservice.asmx?wsdl"
        sess = Session()
        mod_dir = path.dirname(path.realpath(__file__))
        cert_path = str(Path(mod_dir).parents[0]) + '/static/cert/adhq1_ADHQ5.cer'
        sess.verify = cert_path
        transp = Transport(session=sess)
        try:
            cl = Client(tin_web_service_url, transport=transp)
        except requests.exceptions.SSLError:
            _logger.log(INFO, 'Fall back to unverifed HTTPS request.')
            sess.verify = False
            transp = Transport(session=sess)
            cl = Client(tin_web_service_url, transport=transp)
        result = cl.service.ServiceTIN('anonymous', 'anonymous', tin)
        res_ord_dict = helpers.serialize_object(result)
        _logger.log(INFO, pprint.pformat( res_ord_dict))
        return res_ord_dict['vIsExist'] is not None

    @staticmethod
    def get_info_rd_vat_service(tin, branch = 0):
        """Return ordered dict with necessary result from Revenue Department's web service.

           :param tin: a string for TIN or PIN

           :param branch: one digit of branch number
        """
        branch = int(branch)
        vat_web_service_url = "https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx?wsdl"
        sess = Session()
        mod_dir = path.dirname(path.realpath(__file__))
        cert_path = str(Path(mod_dir).parents[0]) + '/static/cert/adhq1_ADHQ5.cer'
        sess.verify = cert_path
        transp = Transport(session=sess)
        try:
            cl = Client(vat_web_service_url, transport=transp)
        except requests.exceptions.SSLError:
            _logger.log(INFO, 'Fall back to unverifed HTTPS request.')
            sess.verify = False
            transp = Transport(session=sess)
            cl = Client(vat_web_service_url, transport=transp)
        result = cl.service.Service(
            'anonymous',
            'anonymous',
            TIN=tin,
            ProvinceCode=0,
            BranchNumber=branch,
            AmphurCode=0,
        )
        odata = helpers.serialize_object(result)
        _logger.log(INFO, pprint.pformat(odata))
        data = OrderedDict()
        if odata['vmsgerr'] is None:           
            for key, value in odata.items():
                if value is None or value['anyType'][0] == '-' or key in {'vNID', 'vtitleName','vName','vBusinessFirstDate'}:
                    continue
                data[key] = value['anyType'][0]
        _logger.log(INFO, pprint.pformat( data ))
        return data
        
    # def action_view_partner_check_tax_id(self):
    #     _logger.log(INFO, self.vat)
    #     if len(self.vat) == 13:
    #         sess = Session()
    #         sess.verify = False
    #         transp = Transport(session=sess)
    #         cl = Client(
    #             "https://rdws.rd.go.th/serviceRD3/vatserviceRD3.asmx?wsdl",
    #             transport=transp,
    #         )
    #         result = cl.service.Service(
    #             username="anonymous",
    #             password="anonymous",
    #             TIN=self.vat,
    #             ProvinceCode=0,
    #             BranchNumber=0,
    #             AmphurCode=9,
    #         )
    #         result = zeep.helpers.serialize_object(result)
    #         _logger.log(INFO, result)
    #         name_company = (
    #             result["vtitleName"].get("anyType", None)[0]
    #             + result["vName"].get("anyType", None)[0]
    #         )
    #         street = (
    #             result["vBuildingName"].get("anyType", None)[0]
    #             + result["vFloorNumber"].get("anyType", None)[0]
    #             + result["vVillageName"].get("anyType", None)[0]
    #             + result["vBuildingName"].get("anyType", None)[0]
    #         )
    #         self.update({"name_company": name_company, "street": street})

    @api.constrains('branch')
    def _validate_branch(self):
        if self.branch is not None and re.match(r'\d{5}',self.branch) is None:
            raise exceptions.ValidationError(_("Branch number must be 5 digits."))

    @api.onchange("vat")
    def _onchange_vat(self):
        _logger.log(INFO, self.vat)
        word_map = {
            'vBuildingName' : 'อาคาร ',
            'vFloorNumber' : 'ชั้นที่ ',
            'vVillageName' : 'หมู่บ้าน ',
            'vRoomNumber' : 'ห้องเลขที่ ',
            'vHouseNumber' : 'เลขที่ ',
            'vMooNumber' : 'หมู่ที่ ',
            'vSoiName' : 'ซอย ',
            'vStreetName' : 'ถนน ',
            'vThambol' : 'ตำบล',
            'vAmphur' : 'อำเภอ',
            'vProvince' : 'จังหวัด',
            'vPostCode' : '',
        }
        map_street = ['vBuildingName', 'vRoomNumber', 'vFloorNumber', 'vHouseNumber','vStreetName', 'vSoiName' ]
        map_street2 = ['vThambol']
        map_city = ['vAmphur']
        map_state = ['vProvince']
        map_zip = ['vPostCode']

        if self.vat == False or len(self.vat) != 13:
            return {}
        else:
            if ResPartner.check_rd_tin_service(self.vat):
                data = ResPartner.get_info_rd_vat_service(self.vat, self.branch)
                street = ''
                for i in map_street:
                    if i in data.keys():
                        street += word_map[i] + data[i] + ' '
                thambol  = word_map['vThambol'] + data['vThambol'] if data['vProvince'] != 'กรุงเทพมหานคร' else 'แขวง' + data['vThambol']
                amphur  = word_map['vAmphur'] + data['vAmphur'] if data['vProvince'] != 'กรุงเทพมหานคร' else 'เขต' + data['vAmphur']
                self.update({
                    'name_company' : data['vBranchTitleName'] + ' ' + data['vBranchName'],
                    'street' : street,
                    'street2' : thambol,
                    'city' : amphur,
                    'zip' : data['vPostCode'],
                    # 'state' : data['vProvince']
                })
                # if data['vmsgerr'] is None:
                #     self.update({
                #         'name_company' : data['vtitleName'] + " " + data['vName'],
                #         'street' : data['vBuildingName'],
                #          })
            else:
                warning_mess = {
                    'title': _("The TIN %s is not valid." % self.vat),
                    'message': _("Connected to RD's web service and failed to verify TIN or PIN %s." % self.vat)
                }
                return {'warning': warning_mess}
