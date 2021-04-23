# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning

class Einvoice25(models.Model) :
    _name = "einvoice.25"
    _description = 'Códigos de Producto SUNAT'
    _inherit = 'einvoice.tmpl'
