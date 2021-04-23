# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CountryState(models.Model):
    _description = "Country state"
    _inherit = 'res.country.state'
    
    code = fields.Char('Country Code', size=9, help='''The ISO country code in two chars.
You can use this field for quick search.''')
    state_id = fields.Many2one('res.country.state', 'Departamento')
    province_id = fields.Many2one('res.country.state', 'Provincia')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
