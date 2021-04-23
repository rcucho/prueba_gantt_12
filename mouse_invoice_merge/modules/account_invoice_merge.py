from odoo import models,fields,api,_
from odoo.exceptions import UserError

class AccountInvoiceMerge(models.TransientModel):
    _name = 'account.invoice.merge'
    
    merge = fields.Boolean(string='Merge',default=False)
    date_invoice = fields.Date(string='Invoice Date')
    journal_id = fields.Many2one('account.journal', string='Journal', domain="[('active', '=', True),('edocument_type','in',[2,4])]")
    company_id = fields.Many2one('res.company', string='Company', readonly=True, default=lambda self: self.env['res.company']._company_default_get('account.invoice'))
    
    @api.multi
    def merge_account_invoice(self):
        context = dict(self._context or {})
        invoice_ids = self.env['account.invoice'].browse(context.get('active_ids'))
        if len(invoice_ids) <= 1:
            raise UserError(_('Please select multiple Invoices to merge in the list view.... '))
        self.merge = True
        for invoice_id in invoice_ids:
            if invoice_id.state not in 'draft':
                raise UserError(_('The Invoices must be in draft state..'))
            if invoice_ids[0].type != invoice_id.type or invoice_id.partner_id.x_studio_tipo != 'Aseguradora' or invoice_ids[0].partner_id.id != invoice_id.partner_id.id :
                self.merge = False
        
        if self.merge :
            partner_id = invoice_ids[0].partner_id.id
            invoice_obj = self.env['account.invoice']
            vals= {
                'partner_id': partner_id,
                'date_invoice': self.date_invoice,
                'type': invoice_ids[0].type,
                'journal_id': self.journal_id.id,
                'x_company_id': self.company_id.id
            }
            ac = invoice_obj.create(vals)
            # call theonchange
            ac._onchange_partner_id()
            ac._onchange_journal_id()
            ac._onchange_payment_term_date_invoice()
            #self.env.cr.commit()
            
            for invoice_id in invoice_ids:
                patient_name = invoice_id.x_studio_sale_order.partner_invoice_id.name if invoice_id.x_studio_sale_order else invoice_id.partner_id.name
                for invoice_line in invoice_id.invoice_line_ids:
                    #p = invoice_line.price_unit
                    invoice_line.copy({
                                        'invoice_id':ac.id,
                                        'name':patient_name + " - " + invoice_line.name,
                                        'x_company_id':self.company_id.id,
                                     })
                    monto_imp = ac.amount_tax + invoice_line.igv_amount
                    monto_tot = ac.amount_total + invoice_line.igv_amount
                    #ac.write({'amount_tax': monto_imp, 'amount_tax_unsigned': monto_imp, 'amount_total': monto_tot, 'amount_total_signed': monto_tot, 'amount_total_company_signed': monto_tot})
                invoice_id.action_cancel()
                #invoice_id.unlink()
            self.env.cr.commit()
            ac._compute_amount()
            ac._compute_sign_taxes()
            ac._onchange_payment_term_date_invoice()
            if ac.invoice_line_ids.ids :
                p = ac.invoice_line_ids[0].price_subtotal
                ac.invoice_line_ids[0].price_subtotal = p + 1
                self.env.cr.commit()
                ac.invoice_line_ids[0].price_subtotal = p
            self.env.cr.commit()
        else:
            raise UserError(_('No es posible mergear los documentos\nLa aseguradora debe ser la misma en todas las facturas'))
        
        #return True
        action = self.env.ref('account.action_invoice_tree').read()[0]
        action['domain'] = [('id','=',ac.id)]
        #action['res_id'] = ac.id
        return action
