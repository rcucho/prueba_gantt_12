# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class SaleOrder(models.Model) :
    _inherit = 'sale.order'
    
    invoice_ids = fields.Many2many(store=True, compute='_get_invoiced', readonly=False)

class AccountInvoice(models.Model) :
    _inherit = 'account.invoice'
    
    cod_sunat = fields.Char(copy=False)
    sent_sunat = fields.Boolean(copy=False)
    sunat_answer = fields.Char(copy=False)
