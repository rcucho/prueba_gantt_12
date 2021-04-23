# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class ProductTemplate(models.Model) :
    _inherit = 'product.template'
    
    @api.model
    def _get_default_l10n_pe_sunat_product_code(self) :
        res = self.env['einvoice.25'].search([('code','=','85101500')],limit=1)
        return res
    
    l10n_pe_sunat_product_code = fields.Many2one(comodel_name='einvoice.25', string='Código de Producto SUNAT', default=_get_default_l10n_pe_sunat_product_code)
