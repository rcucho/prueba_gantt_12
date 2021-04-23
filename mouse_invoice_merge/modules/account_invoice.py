from odoo import models,fields,api,_
from odoo.exceptions import UserError
import base64

class AccountInvoice(models.Model) :
    _inherit = 'account.invoice'

    @api.onchange('partner_id')
    def cambio_partner_id(self) :
        if self.partner_id :
            if self.partner_id.x_studio_tipo == 'Paciente' :
                self.x_studio_paciente = self.partner_id
                self.partner_shipping_id = 38
    
    @api.onchange('signed_xml')
    def _onchange_signed_xml(self) :
        if self.signed_xml :
            self.x_studio_xml_firmado = base64.b64encode(self.signed_xml.encode()) if self.signed_xml else False
            self.x_studio_xml_firmado_filename = self.shop_id.company_id.partner_id.vat + '-' + self.journal_id.edocument_type.code + '-' + self.number.split('-')[0] + '-' + self.number.split('-')[1] + '.xml'
    
    @api.multi
    def action_invoice_open(self):
        #for record in self :
        #    if len(record.invoice_line_ids) :
        #        p = record.invoice_line_ids[0].price_unit
        #        record.invoice_line_ids[0].price_unit = p + 1
        #        self.env.cr.commit()
        #        record.invoice_line_ids[0].price_unit = p
        #        self.env.cr.commit()
        res = super(AccountInvoice, self).action_invoice_open()
        for record in self :
            tipo = record.journal_id.edocument_type.code

            if tipo == '01' and ((not record.partner_id.catalog_06_id) or record.partner_id.catalog_06_id.code != '6') :
                #Factura con DNI
                raise UserError(_("No puede validar una factura con un cliente que no posea RUC"))

            if tipo in ['01', '03'] :
                unsigned_invoice_dictionary = record.crear_xml_factura()
            elif tipo in ['07'] :
                #raise UserError(_("Es nota de credito"))
                unsigned_invoice_dictionary = record.crear_xml_nota_credito()
            elif tipo in ('08') :
                #raise UserError(_("Es nota de debito"))
                unsigned_invoice_dictionary = record.crear_xml_nota_debito()
            else :
                return res

            record.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml']})

            invoice_company = record.shop_id.company_id

            sign_path = invoice_company.digital_certificate[:] #Very long string like b'0\x82\x0br\x02\x01\x030\x82\x0b<\x06\t...'
            sign_pass = invoice_company.digital_password[:] #'123456'
            signed_invoice_dictionary = record.signature_xml(unsigned_invoice_dictionary['unsigned_xml'], sign_path, sign_pass)
            record.write({'signed_xml': signed_invoice_dictionary['signed_xml'],'x_studio_xml_firmado':base64.b64encode(signed_invoice_dictionary['signed_xml'].encode()),'x_studio_xml_firmado_filename':invoice_company.partner_id.vat + '-' + tipo + '-' + record.number + '.xml'})
            #record.write({'digest_value': signed_invoice_dictionary['hash_cpe']})

        return res
