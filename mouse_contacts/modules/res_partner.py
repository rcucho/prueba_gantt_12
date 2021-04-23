# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Partner(models.Model):
    _inherit = 'res.partner'

    name = fields.Char(track_visibility='always')
    vat = fields.Char(track_visibility='always')
    country_id = fields.Many2one(track_visibility='onchange')
    state_id = fields.Many2one(track_visibility='onchange')
    province_id = fields.Many2one(track_visibility='onchange')
    district_id = fields.Many2one(track_visibility='onchange')
    street = fields.Char(track_visibility='onchange')
    catalog_06_id = fields.Many2one(track_visibility='onchange')
    commercial_name = fields.Char(track_visibility='onchange')
