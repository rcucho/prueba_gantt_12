# -*- coding: utf-8 -*-

from . import models
from odoo import api, SUPERUSER_ID

def _create_shop(cr, registry):
    """ This hook is used to add a shop on existing companies
    when module l10n_pe is installed.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    company_ids = env['res.company'].search([])
    company_with_shop = env['einvoice.shop'].search([]).mapped('company_id')
    company_without_shop = company_ids - company_with_shop
    for company in company_without_shop:
        # Getting internal users
        user_ids = env['res.users'].search([('company_id', '=', company.id),('share','=',False)]).ids
        print('Usuarios de compañia', user_ids)
        shop_id = env['einvoice.shop'].create({
            'name': '%s %s' % (company.name, company.id),
            'code': '0000',
            'company_id': company.id,
            'partner_id': company.partner_id.id,
            'user_ids': [(6, 0, user_ids)],
        })
        
        # Assigning shop to the sale journals
        sale_journal_ids = env['account.journal'].search([('company_id','=',company.id),('type','=','sale')])
        for journal in sale_journal_ids:
            journal.write({'shop_id': shop_id.id})
