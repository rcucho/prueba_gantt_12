# -*- coding: utf-8 -*-
from lxml import etree
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class AccountInvoice(models.Model) :
    _inherit = 'account.invoice'
    
    def crear_nuevo_facturacion(self, data_string) :
        lxml_doc = etree.fromstring(data_string)
        
        fecha = lxml_doc[1][0][1].xpath("Fecha")[0].text.strip()
        date_invoice = datetime.datetime.strptime(fecha, '%Y-%m-%d')
        
        gran_total = float(lxml_doc[1][0][1].xpath("MontoTotal")[0].text)
        gran_subtotal = float(str(round(gran_total/1.18,2)))
        gran_igv = float(str(round(gran_total - gran_subtotal,2)))
        
        type_invoice = 'out_invoice'
        tipo_comprobante = lxml_doc[1][0][1].xpath("TipoComprobante")[0].text.strip()
        if tipo_comprobante not in ['01','03','07','08'] :
            return {'cod_sunat': '9999', 'sunat_answer': "El código de documento para facturación no es válido.", 'digest_value': ''}
        comprobante = self.env['einvoice.catalog.01'].search([('code','=',tipo_comprobante)],limit=1)
        serie = lxml_doc[1][0][1].xpath("Serie")[0].text.strip().upper()
        if len(serie) != 4 :
            return {'cod_sunat': '9999', 'sunat_answer': "La serie del documento para facturación debe tener 4 caracteres.", 'digest_value': ''}
        correlativo = lxml_doc[1][0][1].xpath("Correlativo")[0].text.strip()
        if not correlativo.isdigit() :
            return {'cod_sunat': '9999', 'sunat_answer': "El número de correlativo no es válido.", 'digest_value': ''}
        
        #ruc_empresa = lxml_doc[1][0][1].xpath("RUCEmpresa")[0].text.strip()
        #if len(ruc_empresa) != 11 :
        #    return {'cod_sunat': '9999', 'sunat_answer': "La RUC de la empresa debe tener 11 dígitos.", 'digest_value': ''}
        #partner_company = []
        if int(serie[3]) == 1 : #if int(correlativo[0]) <= 4 :
            ruc_empresa = '20526112963' #Resonorte
        else :
            ruc_empresa = '20603148119' #TC Scaner
        partner_company = self.env['res.partner'].search([('vat','=',ruc_empresa)],limit=1)
        if not partner_company :
            return {'cod_sunat': '9999', 'sunat_answer': "La RUC de la empresa no existe, comuníquese con el administrador.", 'digest_value': ''}
        
        company_id = partner_company.company_id.id
        print(company_id)
        shop = self.env['einvoice.shop'].search([('company_id','=',company_id)],limit=1)
        if not shop :
            return {'cod_sunat': '9999', 'sunat_answer': "Error en la configuración de la empresa, comuníquese con el administrador.", 'digest_value': ''}
        
        if tipo_comprobante in ['01','03'] :
            journal = self.env['account.journal'].search([('edocument_type','=',comprobante.id),('shop_id','=',shop.id),('active','=',True)],limit=1)
            if not journal :
                return {'cod_sunat': '9999', 'sunat_answer': "Error en la configuración de serie, comuníquese con el administrador.", 'digest_value': ''}
            
            if tipo_comprobante == '01' and serie[0] == 'B' : #!= 'F' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie para facturas debe empezar con 'F'.", 'digest_value': ''}
            if tipo_comprobante == '03' and serie[0] != 'B' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie para boletas debe empezar con 'B'.", 'digest_value': ''}
            
            if journal.code != serie :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie no está registrada en el sistema, comuníquese con el administrador.", 'digest_value': ''}
            
            refund_invoice = {'number': '0-0'}
            refund_invoice_id = False
        else :
            refund_invoice_serie = lxml_doc[1][0][1].xpath("SerieRectificar")[0].text.strip().upper()
            if len(serie) != 4 :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie del comprobante a rectificar debe tener 4 caracteres.", 'digest_value': ''}
            refund_invoice_correlativo = lxml_doc[1][0][1].xpath("CorrelativoRectificar")[0].text.strip()
            if not refund_invoice_correlativo.isdigit():
                return {'cod_sunat': '9999', 'sunat_answer': "El número de correlativo a rectificar no es válido.", 'digest_value': ''}
            refund_invoice_number = refund_invoice_serie + "-" + refund_invoice_correlativo.rjust(8,'0')
            refund_invoice_tipo_comprobante = lxml_doc[1][0][1].xpath("TipoComprobanteRectificar")[0].text.strip()
            if refund_invoice_tipo_comprobante not in ['01','03'] :
                return {'cod_sunat': '9999', 'sunat_answer': "El tipo de comprobante a rectificar no es válido.", 'digest_value': ''}
            if refund_invoice_tipo_comprobante == '01' and refund_invoice_serie[0] == 'B' : #!= 'F' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie de la factura a rectificar debe empezar con 'F'.", 'digest_value': ''}
            if refund_invoice_tipo_comprobante == '03' and refund_invoice_serie[0] != 'B' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie de la boleta a rectificar debe empezar con 'B'.", 'digest_value': ''}
            refund_invoice_comprobante = self.env['einvoice.catalog.01'].search([('code','=',refund_invoice_tipo_comprobante)],limit=1)
            
            refund_invoice = self.env['account.invoice'].search([('number','=',refund_invoice_number),('company_id','=',company_id),('active','=',True)],limit=1)
            if not refund_invoice :
                return {'cod_sunat': '9999', 'sunat_answer': "El documento a rectificar no existe.", 'digest_value': ''}
            refund_invoice_id = refund_invoice['id']
            
            if tipo_comprobante == '07' :
                type_invoice = 'out_refund'
                journal = self.env['account.journal'].search([('edocument_type','=',comprobante.id),('shop_id','=',shop.id),('active','=',True),('edocument_credit','=',refund_invoice_comprobante.id)],limit=1)
            else :
                journal = self.env['account.journal'].search([('edocument_type','=',comprobante.id),('shop_id','=',shop.id),('active','=',True),('edocument_debit','=',refund_invoice_comprobante.id)],limit=1)
            
            if not journal :
                return {'cod_sunat': '9999', 'sunat_answer': "Error en la configuración de series, comuníquese con el administrador.", 'digest_value': ''}
            
            if refund_invoice_tipo_comprobante == '01' and serie[0] == 'B' : #!= 'F' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie de la factura rectificativa debe empezar con 'F'.", 'digest_value': ''}
            if refund_invoice_tipo_comprobante == '03' and serie[0] != 'B' :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie de la boleta rectificativa debe empezar con 'B'.", 'digest_value': ''}
            
            if journal.code != serie :
                return {'cod_sunat': '9999', 'sunat_answer': "La serie rectificativa no está registrada en el sistema, comuníquese con el administrador.", 'digest_value': ''}
        
        #date_due = datetime.date.today() #.strftime("%Y-%m-%d")
        
        ruc_aseguradora = lxml_doc[1][0][1].xpath("RUCAseguradora")[0].text.strip() if lxml_doc[1][0][1].xpath("RUCAseguradora") else ""
        if len(ruc_aseguradora) == 11 :
            aseguradora = self.env['res.partner'].search([('vat','=',ruc_aseguradora)],limit=1)
            if not aseguradora :
                return {'cod_sunat': '9999', 'sunat_answer': "Debe especificar una RUC de aseguradora en el sistema o no especificar en caso el paciente no este asegurado.", 'digest_value': ''}
        else :
            aseguradora = False
        
        did_cliente = lxml_doc[1][0][1].xpath("DocIdentidadCliente")[0].text.strip().rjust(8,'0')
        if len(did_cliente) not in [8,11] :
            return {'cod_sunat': '9999', 'sunat_answer': "El documento de identidad del cliente no es válido.", 'digest_value': ''}
        if serie[0] == 'F' and len(did_cliente) != 11 :
            return {'cod_sunat': '9999', 'sunat_answer': "Para facturas es necesario solicitar la RUC.", 'digest_value': ''}
        nombre_cliente = lxml_doc[1][0][1].xpath("RazonSocialCliente")[0].text.strip().upper()
        if not nombre_cliente :
            return {'cod_sunat': '9999', 'sunat_answer': "Debe ingresar el nombre del cliente.", 'digest_value': ''}
        ubigeo_cliente = lxml_doc[1][0][1].xpath("UbigeoCliente")[0].text.strip()
        if len(ubigeo_cliente) != 6 or not ubigeo_cliente.isdigit() :
            ubigeo_cliente = '130101'
            #return {'cod_sunat': '9999', 'sunat_answer': "El código de ubigeo no es válido.", 'digest_value': ''}
        cliente = self.env['res.partner'].search([('vat','=',did_cliente)],limit=1)
        if cliente and did_cliente :
            commercial_partner_id = cliente.id
        else :
            country = self.env['res.country'].search([('code','=','PE')],limit=1)
            
            #district = self.env['res.country.state'].search([('country_id','=',country.id),('code','=',ubigeo_cliente)],limit=1)
            #if not district :
            #    return {'cod_sunat': '9999', 'sunat_answer': str(self.env['res.country.state'].search([])), 'digest_value': ''}
            
            cliente = self.env['res.partner'].create({
                                                        'zip': ubigeo_cliente,
                                                        'catalog_06_id': (4 if len(did_cliente)==11 else 2),
                                                        'vat': did_cliente,
                                                        'name': nombre_cliente,
                                                        'country_id': country.id,
                                                        'state_id': False, #district.state_id.id,
                                                        'province_id': False, #district.province_id.id,
                                                        'district_id': False, #district.id,
                                                        'street': 'Unknown Address',
                                                        'aseguradora': aseguradora.id if aseguradora else False,
                                                        'is_aseguradora': False,
                                                    })
            commercial_partner_id = cliente.id
        
        #for registro in detalle :
        #    registro[2]['company_id'] = company_id
        #    registro[2]['partner_id'] = commercial_partner_id
        #    registro[2]['invoice_type'] = type_invoice
        #    registro[2]['price_subtotal_signed'] = registro[2]['price_subtotal']*(-1) if refund_invoice_id else registro[2]['price_subtotal']
        
        if lxml_doc[1][0][1].xpath("DNIMedicoReferente") :
            dni_medico_referente = lxml_doc[1][0][1].xpath("DNIMedicoReferente")[0].text.strip()
            if dni_medico_referente.isdigit() :
                return {'cod_sunat': '9999', 'sunat_answer': "El DNI solo debe tener números.", 'digest_value': ''}
            if len(dni_medico_referente) != 8 :
                return {'cod_sunat': '9999', 'sunat_answer': "El DNI del médico referente debe tener 8 dígitos.", 'digest_value': ''}
            if lxml_doc[1][0][1].xpath("NombreMedicoReferente") :
                nombre_medico_referente = lxml_doc[1][0][1].xpath("NombreMedicoReferente")[0].text.strip()
                if nombre_medico_referente :
                    espacios_medico_referente = nombre_medico_referente.count(" ")
                    nombre_medico_referente = nombre_medico_referente.rsplit(" ", min(2,espacios_medico_referente))
                    ape_pat_medico_referente = ""
                    ape_mat_medico_referente = ""
                    nombres_medico_referente = nombre_medico_referente[0]
                    if len(nombre_medico_referente) > 1 :
                        ape_pat_medico_referente = nombre_medico_referente[1]
                        if len(nombre_medico_referente) > 2 :
                            ape_mat_medico_referente = nombre_medico_referente[2]
                    medico_referente = self.env['medicos.medicos'].search([('med_dni','=',dni_medico_referente)],limit=1)
                    if not medico_referente :
                        medico_referente = self.env['medicos.medicos'].create({
                                                                                'med_dni': dni_medico_referente,
                                                                                'med_dni_old': dni_medico_referente,
                                                                                'med_ape_pat': ape_pat_medico_referente,
                                                                                'med_ape_mat': ape_mat_medico_referente,
                                                                                'med_nombres': nombres_medico_referente,
                                                                             })
                    id_medico_referente = medico_referente.id
                else :
                    return {'cod_sunat': '9999', 'sunat_answer': "Debe ingresar los nombres completos del médico referente.", 'digest_value': ''}
            else :
                return {'cod_sunat': '9999', 'sunat_answer': "Debe ingresar los nombres completos del médico referente.", 'digest_value': ''}
        #else :
        #    return {'cod_sunat': '9999', 'sunat_answer': "Debe ingresar el DNI del médico referente.", 'digest_value': ''}
        
        detalle = []
        for cada_detalle in lxml_doc[1][0][1].xpath("Detalle") :
            cod_producto = cada_detalle.xpath("Codigo")[0].text.strip().upper() if cada_detalle.xpath("Codigo")[0].text else "SINCOD"
            nombre_producto = cada_detalle.xpath("Nombre")[0].text.strip()
            detalle_total_unit = float(cada_detalle.xpath("PrecioUnitario")[0].text.strip())
            detalle_subtotal_unit = float(str(round(detalle_total_unit/1.18,2)))
            detalle_igv_unit = float(str(round(detalle_total_unit - detalle_subtotal_unit,2)))
            detalle_cantidad = float(cada_detalle.xpath("Cantidad")[0].text)
            detalle_total = float(str(round(detalle_total_unit * detalle_cantidad,2)))
            detalle_subtotal = float(str(round(detalle_total/1.18,2)))
            detalle_igv = float(str(round(detalle_total - detalle_subtotal,2)))
            
            producto = self.env['product.product'].search([('default_code','=',cod_producto)],limit=1)
            
            if not producto :
                producto = self.env['product.product'].create({
                                                                'sale_ok': True,
                                                                'purchase_ok': False,
                                                                'default_code': cod_producto,
                                                                'name': nombre_producto,
                                                                'product_code_sunat': 21265,
                                                                'categ_id': 1,
                                                                'type': 'service',
                                                                'igv_type': 1,
                                                                'lst_price': detalle_total_unit,
                                                            })
            product_id = producto.id
            
            tax_id = 1
            tax = self.env['account.tax'].search([('company_id','=',company_id)],limit=1)
            if tax :
                tax_id = tax.id
            
            detalle.append((0,0,{
                                    'name': '['+cod_producto+'] '+nombre_producto,
                                    #'origin': False,
                                    'sequence': 10,
                                    #'invoice_id': (2, 'Invoice '),
                                    'uom_id': 1, #(1, 'Unit(s)'),
                                    'product_id': product_id, #(1, '[P001] Producto 1'),
                                    'account_id': 1234, #(1234, '70111.01 Ventas  - Mercaderías / mercaderías manufacturadas terceros - Categoria de productos 01'),
                                    'price_unit': detalle_subtotal_unit,
                                    'price_subtotal': detalle_subtotal,
                                    'price_subtotal_signed': detalle_subtotal*(-1) if refund_invoice_id else detalle_subtotal,
                                    'quantity': detalle_cantidad,
                                    'discount': 0.0,
                                    'invoice_line_tax_ids': [(4,tax_id,0)],
                                    #'account_analytic_id': False,
                                    #'analytic_tag_ids': [],
                                    'company_id': company_id,
                                    'partner_id': commercial_partner_id,
                                    'currency_id': 162, #(162, 'PEN'),
                                    #'is_rounding_line': False,
                                    #'display_type': False,
                                    #'free_product': False,
                                    'igv_type': 1, #(1, '10 - Gravado - Operación Onerosa'),
                                    'price_base': detalle_subtotal,
                                    'price_total': detalle_total,
                                    #'create_uid': (2, 'Administrator'),
                                    #'create_date': datetime.datetime(2019, 10, 12, 18, 24, 19, 78743),
                                    #'write_uid': (2, 'Administrator'),
                                    #'write_date': datetime.datetime(2019, 10, 12, 23, 48, 7, 378277),
                                    'invoice_type': type_invoice,
                                    #'product_image': False,
                                    'price_tax': detalle_igv_unit,
                                    'company_currency_id': 162, #(162, 'PEN'),
                                    'amount_discount': 0.0,
                                    'amount_free': 0.0,
                                    'igv_amount': detalle_igv_unit,
                                    'price_unit_excluded': detalle_subtotal_unit,
                                    'price_unit_included': detalle_total_unit,
                                    'display_name': '['+cod_producto+'] '+nombre_producto
                                    #'__last_update': datetime.datetime(2019, 10, 12, 18, 24, 19, 78743)
                                }))
        
        invoice_generated = self.env['account.invoice'].create({
                                                                'type': type_invoice,
                                                                'refund_invoice_id': refund_invoice_id,
                                                                #'number': False,
                                                                #'move_name': False,
                                                                #'reference': False,
                                                                #'comment': False,
                                                                'state': 'draft',
                                                                #'sent': False,
                                                                'date_invoice': str(date_invoice),
                                                                #'date_due': date_due.strftime("%Y-%m-%d"),
                                                                'partner_id': commercial_partner_id,
                                                                #'vendor_bill_id': False,
                                                                'payment_term_id': 1, #(1, 'Immediate Payment'),
                                                                #'date': False,
                                                                'account_id': 77, #(77, '121100 Cuentas por cobrar ...- Facturas, boletas y otros comprobantes por cobrar / no emitidas'),
                                                                'invoice_line_ids': detalle, #----------------------------------------------------------------
                                                                #'tax_line_ids': [2],
                                                                #'refund_invoice_ids': [],
                                                                #'move_id': False,
                                                                'amount_untaxed': gran_subtotal,
                                                                'amount_untaxed_signed': gran_subtotal*(-1) if refund_invoice_id else gran_subtotal,
                                                                'amount_tax': gran_igv,
                                                                'amount_total': gran_total,
                                                                'amount_total_signed': gran_total*(-1) if refund_invoice_id else gran_total,
                                                                'amount_total_company_signed': gran_total*(-1) if refund_invoice_id else gran_total,
                                                                'currency_id': 162, #(162, 'PEN'),
                                                                'journal_id': journal.id, #(8, 'Boleta B024 (PEN)'),
                                                                'company_id': company_id, #(1, 'MEDITECH SOLUTIONS S.R.L.'),
                                                                'user_id': 2,
                                                                'commercial_partner_id': commercial_partner_id, #(9, 'RENTABILIZADORA DE NEGOCIOS S.A.C.'),
                                                                'vendor_display_name': nombre_cliente, #'RENTABILIZADORA DE NEGOCIOS S.A.C.',
                                                                'amount_base': gran_subtotal,
                                                                'credit_note_type': journal.edocument_credit.id if journal.edocument_credit else False,
                                                                'debit_note_type': journal.edocument_debit.id if journal.edocument_debit else False,
                                                                'edocument_type': journal.edocument_type.id,
                                                                #'einv_amount_base': 0.0,
                                                                #'einv_amount_exonerated': 0.0,
                                                                #'einv_amount_free': 0.0,
                                                                #'einv_amount_unaffected': 0.0,
                                                                #'einv_amount_igv': 0.0,
                                                                #'einv_amount_others': 0.0,
                                                                #'einv_amount_untaxed': 0.0,
                                                                #'einv_serie': False,
                                                                #'einv_number': False,
                                                                #'global_discount': 0.0,
                                                                'origin_document_id': refund_invoice_id,
                                                                'origin_document_serie': refund_invoice_serie if refund_invoice_id else False,
                                                                'origin_document_number': refund_invoice_correlativo if refund_invoice_id else False,
                                                                'shop_id': shop.id,
                                                                #'sunat_answer': False,
                                                                #'activity_ids': [],
                                                                #'message_follower_ids': [15],
                                                                #'message_ids': [16],
                                                                #'message_main_attachment_id': False,
                                                                #'website_message_ids': [],
                                                                #'access_token': False,
                                                                #'create_uid': (2, 'Administrator'),
                                                                #'create_date': datetime.datetime(2019, 10, 11, 20, 39, 50, 942794),
                                                                #'write_uid': (1, 'OdooBot'),
                                                                #'write_date': datetime.datetime(2019, 10, 11, 20, 39, 50, 942794),
                                                                #'authorized_transaction_ids': [],
                                                                #'amount_by_group': [('IGV 18%', 43.2, 240.0, 'S/ 43.20', 'S/ 240.00', 1)],
                                                                'amount_untaxed_invoice_signed': gran_subtotal*(-1) if refund_invoice_id else gran_subtotal,
                                                                'amount_tax_signed': gran_igv*(-1) if refund_invoice_id else gran_igv,
                                                                'company_currency_id': 162, #(162, 'PEN'),
                                                                #'outstanding_credits_debits_widget': 'false',
                                                                #'payments_widget': 'false',
                                                                #'has_outstanding': False,
                                                                #'sequence_number_next': '',
                                                                #'sequence_number_next_prefix': False,
                                                                #'invoice_icon': '',
                                                                #'igv_percent': 0,
                                                                #'can_debit': 0,
                                                                #'activity_state': False,
                                                                #'activity_user_id': False,
                                                                #'activity_type_id': False,
                                                                #'activity_date_deadline': False,
                                                                #'activity_summary': False,
                                                                #'message_is_follower': False,
                                                                #'message_partner_ids': [3],
                                                                #'message_channel_ids': [],
                                                                #'message_unread': False,
                                                                #'message_unread_counter': 0,
                                                                #'message_needaction': False,
                                                                #'message_needaction_counter': 0,
                                                                #'message_has_error': False,
                                                                #'message_has_error_counter': 0,
                                                                #'message_attachment_count': 0,
                                                                #'access_url': '/my/invoices/2',
                                                                #'access_warning': '',
                                                                #'display_name': 'Invoice ',
                                                                #'__last_update': datetime.datetime(2019, 10, 11, 20, 39, 50, 942794),
                                                              })
        
        invoice_id = invoice_generated.id
        for line in invoice_generated.invoice_line_ids :
            if not line.invoice_id :
                lines.write({'invoice_id':invoice_id})
        
        respuesta_sunat = {'cod_sunat': '0000', 'sunat_answer': "El comprobante ha sido guardado con éxito.", 'digest_value': ''}
        
        return respuesta_sunat