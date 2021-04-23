# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

class Users(models.Model):
    _inherit = "res.users"
    
    shop_ids = fields.Many2many('einvoice.shop', 'einvoice_shop_users_rel', 'user_id', 'shop_id', string='Shops')
