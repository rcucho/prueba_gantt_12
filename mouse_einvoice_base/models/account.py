# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AccountJournal(models.Model):
    _inherit = "account.journal"
    
    edocument_credit = fields.Many2one('einvoice.catalog.01', string='Credit document type', help='Catalog 01: Type of electronic document')
    edocument_debit = fields.Many2one('einvoice.catalog.01', string='Debit document type', help='Catalog 01: Type of electronic document')
    edocument_type = fields.Many2one('einvoice.catalog.01', string='Electronic document type', help='Catalog 01: Type of electronic document')
    shop_id = fields.Many2one('einvoice.shop', string='Shop')
    
class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    einv_type_tax = fields.Many2one('einvoice.catalog.05', string='Tax type code', help='Catalog 05: Tax type code')
