# -*- coding: utf-8 -*-

from zipfile import ZipFile 
import os
import base64
from io import BytesIO
import requests
from xml.dom.minidom import parse, parseString
import signxml
from lxml import etree
from OpenSSL import crypto

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class AccountInvoice(models.Model): 
    
    _inherit = 'account.invoice'
    
    amount_base = fields.Monetary(string='Subtotal',store=True, readonly=True, compute='_compute_amount', track_visibility='always', help='Total without discounts and taxes')
    amount_discount = fields.Monetary(string='Discount', store=True, readonly=True, compute='_compute_amount',track_visibility='always')
    credit_note_type = fields.Many2one('einvoice.catalog.01', string='Credit note type', help='Catalog 01: Type of electronic document', store=True)
    debit_note_type = fields.Many2one('einvoice.catalog.01', string='Debit note type', help='Catalog 01: Type of electronic document', store=True)
    edocument_type = fields.Many2one('einvoice.catalog.01', string='Electronic document type', help='Catalog 01: Type of electronic document', store=True)
    einv_amount_base = fields.Monetary(string='Base Amount', store=True, readonly=True, compute='_compute_amount', track_visibility='always', help='Total with discounts and before taxes')
    einv_amount_exonerated = fields.Monetary(string='Exonerated  Amount', store=True, compute='_compute_amount', track_visibility='always')
    einv_amount_free = fields.Monetary(string='Free Amount', store=True, compute='_compute_amount', track_visibility='always')
    einv_amount_unaffected = fields.Monetary(string='Unaffected Amount', store=True, compute='_compute_amount', track_visibility='always')
    einv_amount_igv = fields.Monetary(string='IGV Amount', store=True, compute='_compute_amount', track_visibility='always')
    einv_amount_others = fields.Monetary(string='Other charges', store=True, compute='_compute_amount', track_visibility='always')
    einv_amount_untaxed = fields.Monetary(string='Total before taxes', store=True, compute='_compute_amount', track_visibility='always', help='Total before taxes, all discounts included')
    einv_serie = fields.Char(string='E-invoice Serie', compute='_get_einvoice_number', store=True)
    einv_number = fields.Integer(string='E-invoice Number', compute='_get_einvoice_number', store=True)
    global_discount = fields.Monetary(string='Global discount', store=True, readonly=True, compute='_compute_amount',track_visibility='always')
    igv_percent = fields.Integer(string="Percentage IGV", compute='_get_percentage_igv')
    origin_document_id = fields.Many2one('account.invoice', string='Origin document', help='Used for Credit an debit note')
    origin_document_serie = fields.Char(string='Document serie', help='Used for Credit an debit note', store=True)
    origin_document_number = fields.Char(string='Document number', help='Used for Credit an debit note', store=True)
    picking_number = fields.Char(string='Picking number')
    shop_id = fields.Many2one('einvoice.shop', string='Shop', default=1, store=True)
    
    unsigned_xml = fields.Text(string='XML representation of the invoice', help='XML representation of the invoice', default="")
    signed_xml = fields.Text(string='Signed invoice XML', help='XML representation of the invoice with signature', default="")
    digest_value = fields.Text(string='DSig digest value', help='Digest value of the XML digital signature', default="")
    sunat_answer = fields.Char(string='Respuesta de la SUNAT', help='Respuesta recibida de la SUNAT', default="")
    cod_sunat = fields.Char(string='Codigo de respuesta de la SUNAT', help='Codigo de respuesta recibido de la SUNAT', default="")
    sent_sunat = fields.Boolean(string='¿Enviado a la SUNAT?', default=False)
    einvoice_journal_id = fields.Many2one('account.journal', string='Journal', required=True, states={'draft': [('readonly', False)]}, default=lambda self: self._default_journal(), domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), ('shop_id', '=', shop_id)]")
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, states={'draft': [('readonly', False)]}, default=lambda self: self._default_journal(), domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), ('shop_id', '=', shop_id)]")
    
    ###################################################################
    
    @api.onchange('shop_id')
    def onchange_shop_id(self) :
        self.einvoice_journal_id = self.env['account.journal'].search([('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(self.type, [])),('shop_id','=',self.shop_id.id),('edocument_type.code','=',self.einvoice_journal_id.edocument_type.code)])
    
    @api.onchange('einvoice_journal_id')
    def onchange_einvoice_journal_id(self) :
        self.journal_id = self.einvoice_journal_id
    
    @api.model
    def _default_credit_edocument(self):
        return self.env['einvoice.catalog.01'].search([('code','in',['07','87','97'])], limit=1)
    
    @api.model
    def create(self, vals):
        #raise UserError(_(str(vals)))
        if not vals.get('einvoice_journal_id') :
            vals['einvoice_journal_id'] = vals['journal_id']
        current_journal = self.env['account.journal'].browse(vals['journal_id'])
        if not vals.get('edocument_type') :
            vals['edocument_type'] = current_journal.edocument_type.id
        if current_journal.edocument_type.code == '07' and (not vals.get('credit_note_type')) :
            vals['credit_note_type'] = current_journal.edocument_credit.id
        if current_journal.edocument_type.code == '08' and (not vals.get('debit_note_type')) :
            vals['debit_note_type'] = current_journal.edocument_debit.id
        
        return super(AccountInvoice, self).create(vals)

    @api.multi
    def write(self, values):
        if values.get('journal_id') :
            values['einvoice_journal_id'] = values['journal_id']
        else :
            if values.get('einvoice_journal_id') :
                values['journal_id'] = values['einvoice_journal_id']
        
        current_journal = self.env['account.journal'].browse(values['journal_id']) if values.get('journal_id') else self.journal_id
        
        if (not values.get('edocument_type')) or (not values['edocument_type']) :
            values['edocument_type'] = current_journal.edocument_type.id
        if current_journal.edocument_type.code == '07' and ((not values.get('credit_note_type')) or (not values['credit_note_type'])) :
            values['credit_note_type'] = current_journal.edocument_credit.id
        if current_journal.edocument_type.code == '08' and ((not values.get('debit_note_type')) or (not values['debit_note_type'])) :
            values['debit_note_type'] = current_journal.edocument_debit.id
        #a=1/0
        return super(AccountInvoice, self).write(values)
    
    def cifras_a_letras(self, numero, sw) :
        lista_centena = ["",("CIEN","CIENTO"),"DOSCIENTOS","TRESCIENTOS","CUATROCIENTOS","QUINIENTOS","SEISCIENTOS","SETECIENTOS","OCHOCIENTOS","NOVECIENTOS"]
        lista_decena = ["",("DIEZ","ONCE","DOCE","TRECE","CATORCE","QUINCE","DIECISEIS","DIECISIETE","DIECIOCHO","DIECINUEVE"),
                        ("VEINTE","VEINTI"),("TREINTA","TREINTA Y "),("CUARENTA" , "CUARENTA Y "),
                        ("CINCUENTA" , "CINCUENTA Y "),("SESENTA" , "SESENTA Y "),
                        ("SETENTA" , "SETENTA Y "),("OCHENTA" , "OCHENTA Y "),
                        ("NOVENTA" , "NOVENTA Y ")
                    ]
        lista_unidad = ["",("UN" , "UNO"),"DOS","TRES","CUATRO","CINCO","SEIS","SIETE","OCHO","NUEVE"]
        centena = int(numero / 100)
        decena = int((numero - (centena * 100))/10)
        unidad = int(numero - (centena * 100 + decena * 10))
        
        texto_centena = ""
        texto_decena = ""
        texto_unidad = ""
        
        texto_centena = lista_centena[centena]
        if centena == 1 :
            if (decena + unidad) != 0 :
                texto_centena = texto_centena[1]
            else :
                texto_centena = texto_centena[0]
        
        texto_decena = lista_decena[decena]
        if decena == 1 :
            texto_decena = texto_decena[unidad]
        elif decena > 1 :
            if unidad != 0 :
                texto_decena = texto_decena[1]
            else:
                texto_decena = texto_decena[0]
        
        if decena != 1 :
            texto_unidad = lista_unidad[unidad]
            if unidad == 1 :
                texto_unidad = texto_unidad[sw]
        
        if decena == 0 :
            return texto_centena+" "+texto_unidad
        elif decena > 1 :
            return texto_centena+" "+texto_decena+texto_unidad
        else :
            return texto_centena+" "+texto_decena+" "+texto_unidad
    
    def monto_a_letras(self, numero):
        #asume no negativo con hasta dos decimales
        indicador = [("",""),("MIL","MIL"),("MILLON","MILLONES"),("MIL","MIL"),("BILLON","BILLONES")]
        entero = int(numero)
        decimal = int(100*numero - 100*entero)
        
        contador = 0
        numero_letras = ""
        while entero > 0 :
            millar = entero % 1000
            
            if contador == 0 :
                en_letras = self.cifras_a_letras(millar,1).strip()
            else :
                en_letras = self.cifras_a_letras(millar,0).strip()
            
            if millar == 0 :
                numero_letras = en_letras+" "+numero_letras
            elif millar == 1 :
                if contador %2 == 1:
                    numero_letras = indicador[contador][0] + " " + numero_letras
                
                else:
                    numero_letras = en_letras + " " + indicador[contador][0] + " " + numero_letras
            else:
                numero_letras = en_letras + " " + indicador[contador][1] + " " + numero_letras
            
            numero_letras = numero_letras.strip()
            contador = contador + 1
            entero = int(entero / 1000)
        
        if numero_letras == "" :
            numero_letras = "CERO"
        
        numero_letras = numero_letras + " CON " + str(decimal).rjust(2,"0") + "/100"
        return numero_letras
    
    def crear_xml_factura(self) :
        xml_doc = """<?xml version="1.0" encoding="utf-8"?>
<Invoice
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID schemeAgencyName="PE:SUNAT">2.0</cbc:CustomizationID>
    <cbc:ProfileID
        schemeName="Tipo de Operacion"
        schemeAgencyName="PE:SUNAT"
        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">"""
        xml_doc = xml_doc + """0101"""
        xml_doc = xml_doc + """</cbc:ProfileID>
    <cbc:ID>"""
        xml_doc = xml_doc + self.number
        xml_doc = xml_doc + """</cbc:ID>
    <cbc:IssueDate>"""
        xml_doc = xml_doc + str(self.date_invoice)
        xml_doc = xml_doc + """</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DueDate>"""
        xml_doc = xml_doc + str(self.date_due)
        xml_doc = xml_doc + """</cbc:DueDate>
    <cbc:InvoiceTypeCode
        listAgencyName="PE:SUNAT"
        listName="Tipo de Documento"
        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01"
        listID="0101"
        name="Tipo de Operacion"
        listSchemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51">"""
        xml_doc = xml_doc + self.journal_id.edocument_type.code #("""01""" if len(invoice.partner_id.vat) == 11 else """03""")
        xml_doc = xml_doc + """</cbc:InvoiceTypeCode>
    <cbc:Note
        languageLocaleID="1000">"""
        xml_doc = xml_doc + self.monto_a_letras(self.amount_total)
        xml_doc = xml_doc + """</cbc:Note>
    <cbc:DocumentCurrencyCode
        listID="ISO 4217 Alpha"
        listName="Currency"
        listAgencyName="United Nations Economic Commission for Europe">"""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """</cbc:DocumentCurrencyCode>
    <cbc:LineCountNumeric>"""
        xml_doc = xml_doc + str(len(self.invoice_line_ids))
        xml_doc = xml_doc + """</cbc:LineCountNumeric>"""
    
    #    if ("""$cabecera["NRO_OTR_COMPROBANTE"]""" != "") :
    #        xml_doc = xml_doc + """
    #<cac:OrderReference>
    #    <cbc:ID>""" + """$cabecera["NRO_OTR_COMPROBANTE"]""" + """</cbc:ID>
    #</cac:OrderReference>"""
    
    #    if ("""$cabecera["NRO_GUIA_REMISION"]""" != "") :
    #        xml_doc = xml_doc + """
    #<cac:DespatchDocumentReference>
    #    <cbc:ID>""" + """$cabecera["NRO_GUIA_REMISION"]""" + """</cbc:ID>
    #    <cbc:IssueDate>""" + """$cabecera["FECHA_GUIA_REMISION"]""" + """</cbc:IssueDate>
    #    <cbc:DocumentTypeCode
    #        listAgencyName="PE:SUNAT"
    #        listName="Tipo de Documento"
    #        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01">""" + """$cabecera["COD_GUIA_REMISION"]""" + """</cbc:DocumentTypeCode>
    #</cac:DespatchDocumentReference>"""
    
        xml_doc = xml_doc + """
    <cac:Signature>
        <cbc:ID>"""
        xml_doc = xml_doc + self.number
        xml_doc = xml_doc + """</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>"""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>"""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.name
        xml_doc = xml_doc + """</cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#"""
        xml_doc = xml_doc + self.number
        xml_doc = xml_doc + """</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.shop_id.company_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.commercial_company_name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID=\""""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID=\""""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI" />
                    <cbc:AddressTypeCode
                        listAgencyName="PE:SUNAT"
                        listName="Establecimientos anexos">0000</cbc:AddressTypeCode>
                    <cbc:CityName><![CDATA["""
        district_id = self.env['res.country.state'].search([('country_id','=',173),('name','=','LIMA'),('code','ilike','0101')])
        if not self.shop_id.company_id.partner_id.zip :
            self.shop_id.company_id.partner_id.country_id = district_id.country_id.id
            self.shop_id.company_id.partner_id.state_id = district_id.state_id.id
            self.shop_id.company_id.partner_id.province_id = district_id.province_id.id
            self.shop_id.company_id.partner_id.district_id = district_id.id
            self.shop_id.company_id.partner_id.zip = district_id.zip #default=LIMA
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.state_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA["""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.province_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:CountrySubentity>
                    <cbc:District><![CDATA["""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.district_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA["""
        xml_doc = xml_doc + (self.shop_id.company_id.partner_id.street.upper() if self.company_id.partner_id.street else "Unknown Address")
        xml_doc = xml_doc + """]]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">"""
        xml_doc = xml_doc + self.shop_id.company_id.partner_id.country_id.code #get_country_iso_code(invoice.company_id.country_id.id)
        xml_doc = xml_doc + """</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                    schemeName="Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.partner_id.name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cbc:CompanyID
                    schemeID=\""""
        xml_doc = xml_doc + self.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.partner_id.vat
        xml_doc = xml_doc + """</cbc:CompanyID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID=\""""
        xml_doc = xml_doc + self.partner_id.catalog_06_id.code
        xml_doc = xml_doc + """\"
                        schemeName="SUNAT:Identificador de Documento de Identidad"
                        schemeAgencyName="PE:SUNAT"
                        schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
                </cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID
                        schemeName="Ubigeos"
                        schemeAgencyName="PE:INEI">"""
        if not self.partner_id.zip :
            self.partner_id.country_id = district_id.country_id.id
            self.partner_id.state_id = district_id.state_id.id
            self.partner_id.province_id = district_id.province_id.id
            self.partner_id.district_id = district_id.id
            self.partner_id.zip = district_id.code #default=LIMA
        xml_doc = xml_doc + self.partner_id.zip #"""$cabecera["COD_UBIGEO_CLIENTE"]"""
        xml_doc = xml_doc + """</cbc:ID>
                    <cbc:CityName><![CDATA["""
        xml_doc = xml_doc + self.partner_id.state_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:CityName>
                    <cbc:CountrySubentity><![CDATA["""
        xml_doc = xml_doc + self.partner_id.province_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:CountrySubentity>
                    <cbc:District><![CDATA["""
        xml_doc = xml_doc + self.partner_id.district_id.name.upper()
        xml_doc = xml_doc + """]]></cbc:District>
                    <cac:AddressLine>
                        <cbc:Line><![CDATA["""
        xml_doc = xml_doc + (self.partner_id.street.upper() if self.partner_id.street else "Unknown Address")
        xml_doc = xml_doc + """]]></cbc:Line>
                    </cac:AddressLine>
                    <cac:Country>
                        <cbc:IdentificationCode
                            listID="ISO 3166-1"
                            listAgencyName="United Nations Economic Commission for Europe"
                            listName="Country">"""
        xml_doc = xml_doc + self.partner_id.country_id.code #get_country_iso_code(invoice.partner_id.country_id.id)
        xml_doc = xml_doc + """</cbc:IdentificationCode>
                    </cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:AllowanceCharge>
        <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
        <cbc:AllowanceChargeReasonCode
            listName="Cargo/descuento"
            listAgencyName="PE:SUNAT"
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo53">02</cbc:AllowanceChargeReasonCode>
        <cbc:MultiplierFactorNumeric>0.00</cbc:MultiplierFactorNumeric>
        <cbc:Amount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">0.00</cbc:Amount>
        <cbc:BaseAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">0.00</cbc:BaseAmount>
    </cac:AllowanceCharge>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + """</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID
                    schemeID="UN/ECE 5305"
                    schemeName="Tax Category Identifier"
                    schemeAgencyName="United Nations Economic Commission for Europe">S</cbc:ID>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>"""
    
    #TOTAL=GRAVADA+IGV+EXONERADA
    #NO ENTRA GRATUITA(INAFECTA) NI DESCUENTO
    #SUB_TOTAL=PRECIO(SIN IGV) * CANTIDAD
    
        xml_doc = xml_doc + """
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + """</cbc:LineExtensionAmount>
        <cbc:TaxInclusiveAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + """</cbc:TaxInclusiveAmount>
        <cbc:AllowanceTotalAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">""" + """0.00""" + """</cbc:AllowanceTotalAmount>
        <cbc:ChargeTotalAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">0.00</cbc:ChargeTotalAmount>
        <cbc:PayableAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + """</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>"""
        
        i = 0
        for line in self.invoice_line_ids.filtered(lambda r: r.product_id.id>0) :
            i = i + 1
            xml_doc = xml_doc + """
    <cac:InvoiceLine>
        <cbc:ID>"""
            xml_doc = xml_doc + str(i) #str(line.id)
            xml_doc = xml_doc + """</cbc:ID>
        <cbc:InvoicedQuantity
            unitCode=\""""
            xml_doc = xml_doc + line.uom_id.unece_code #get_uom_code(line.uom_id.id)
            xml_doc = xml_doc + """\"
            unitCodeListID="UN/ECE rec 20"
            unitCodeListAgencyName="United Nations Economic Commission for Europe">"""
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + """</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount
            currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
                <cbc:PriceTypeCode
                    listName="Tipo de Precio"
                    listAgencyName="PE:SUNAT"
                    listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16">"""
            xml_doc = xml_doc + """01"""
            xml_doc = xml_doc  + """</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:ID
                        schemeID="UN/ECE 5305"
                        schemeName="Tax Category Identifier"
                        schemeAgencyName="United Nations Economic Commission for Europe">"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.un_5103 #a1.invoice_line_tax_ids[0].unece_categ_id.code #"""S"""
            xml_doc = xml_doc + """</cbc:ID>
                    <cbc:Percent>"""
            xml_doc = xml_doc + str(int(line.invoice_line_tax_ids[0].amount + 0.5)) #"""18"""
            xml_doc = xml_doc + """</cbc:Percent>
                    <cbc:TaxExemptionReasonCode
                        listAgencyName="PE:SUNAT"
                        listName="SUNAT:Codigo de Tipo de Afectación del IGV"
                        listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07">"""
            xml_doc = xml_doc + line.igv_type.code #"""10"""
            xml_doc = xml_doc + """</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID
                            schemeID="UN/ECE 5153"
                            schemeName="Tax Scheme Identifier"
                            schemeAgencyName="United Nations Economic Commission for Europe">"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.code #"""1000"""
            xml_doc = xml_doc + """</cbc:ID>
                        <cbc:Name>"""
            xml_doc = xml_doc + """IGV"""
            xml_doc = xml_doc + """</cbc:Name>
                        <cbc:TaxTypeCode>"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.un_5153 #"""VAT"""
            xml_doc = xml_doc + """</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA["""
            xml_doc = xml_doc + (line.product_id.name.strip() if line.product_id.name else "CONSTANT")
            xml_doc = xml_doc + """]]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA["""
            xml_doc = xml_doc + (line.product_id.default_code.strip() if line.product_id.default_code else "C000")
            xml_doc = xml_doc + """]]></cbc:ID>
            </cac:SellersItemIdentification>
            <cac:CommodityClassification>
                <cbc:ItemClassificationCode
                    listID="UNSPSC"
                    listAgencyName="GS1 US"
                    listName="Item Classification">"""
            
            product_code = ('l10n_pe_sunat_product_code' in line.product_id._fields) and line.product_id.l10n_pe_sunat_product_code.code or '85101500' #needs a default code
            xml_doc = xml_doc + product_code
            
            xml_doc = xml_doc + """</cbc:ItemClassificationCode>
            </cac:CommodityClassification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>"""
        
        xml_doc = xml_doc + """
</Invoice>"""
        
        #with open(ruta+".XML", "wb") as f :
        #    f.write(xml_doc.encode("utf-8"))
        #
        #resp = {'respuesta': 'ok', 'url_xml': ruta+".XML"}
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_credito(self) :
        xml_doc = """<?xml version="1.0" encoding="utf-8"?>
<CreditNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>"""
        xml_doc = xml_doc + self.number
        xml_doc = xml_doc + """</cbc:ID>
    <cbc:IssueDate>"""
        xml_doc = xml_doc + str(self.date_invoice)
        xml_doc = xml_doc + """</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>"""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>"""
        xml_doc = xml_doc + self.origin_document_id.number
        xml_doc = xml_doc + """</cbc:ReferenceID>
        <cbc:ResponseCode>"""
        xml_doc = xml_doc + """10"""
        xml_doc = xml_doc + """</cbc:ResponseCode>
        <cbc:Description><![CDATA["""
        xml_doc = xml_doc + (self.name if self.name else "Nota de crédito a "+self.origin_document_id.number)
        xml_doc = xml_doc + """]]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>"""
        xml_doc = xml_doc + self.origin_document_id.number
        xml_doc = xml_doc + """</cbc:ID>
            <cbc:DocumentTypeCode>"""
        xml_doc = xml_doc + self.origin_document_id.journal_id.edocument_type.code #self.credit_note_type.code
        xml_doc = xml_doc + """</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>"""
        xml_doc = xml_doc + self.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.company_id.partner_id.catalog_06_id.code #"""6"""
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.commercial_company_name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>0001</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.partner_id.catalog_06_id.code #("""6""" if len(client_partner['vat']) == 11 else """1""")
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + """</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:PayableAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + """</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>"""
        
        i = 0
        for line in self.invoice_line_ids :
            i = i + 1
            xml_doc = xml_doc + """
    <cac:CreditNoteLine>
        <cbc:ID>"""
            xml_doc = xml_doc + str(i) #str(line.id)
            xml_doc = xml_doc + """</cbc:ID>
        <cbc:CreditedQuantity
            unitCode=\""""
            xml_doc = xml_doc + line.uom_id.unece_code
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + """</cbc:CreditedQuantity>
        <cbc:LineExtensionAmount
            currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
                <cbc:PriceTypeCode>"""
            xml_doc = xml_doc + """01"""
            xml_doc = xml_doc + """</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>"""
            xml_doc = xml_doc + str(int(line.invoice_line_tax_ids[0].amount + 0.5)) #"""18"""
            xml_doc = xml_doc + """</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>"""
            xml_doc = xml_doc + line.igv_type.code #"""10"""
            xml_doc = xml_doc + """</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.code #"""1000"""
            xml_doc = xml_doc + """</cbc:ID>
                        <cbc:Name>"""
            xml_doc = xml_doc + """IGV"""
            xml_doc = xml_doc + """</cbc:Name>
                        <cbc:TaxTypeCode>"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.un_5153 #"""VAT"""
            xml_doc = xml_doc + """</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA["""
            xml_doc = xml_doc + (line.product_id.name.strip() if line.product_id.name else "CONSTANT")
            xml_doc = xml_doc + """]]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA["""
            xml_doc = xml_doc + (line.product_id.default_code.strip() if line.product_id.default_code else "C000")
            xml_doc = xml_doc + """]]></cbc:ID>
            </cac:SellersItemIdentification>
            <cac:CommodityClassification>
                <cbc:ItemClassificationCode
                    listID="UNSPSC"
                    listAgencyName="GS1 US"
                    listName="Item Classification">"""
            
            product_code = ('l10n_pe_sunat_product_code' in line.product_id._fields) and line.product_id.l10n_pe_sunat_product_code.code or '85101500' #needs a default code
            xml_doc = xml_doc + product_code
            
            xml_doc = xml_doc + """</cbc:ItemClassificationCode>
            </cac:CommodityClassification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
        </cac:Price>
    </cac:CreditNoteLine>"""
    
        xml_doc = xml_doc + """
</CreditNote>"""
        
        #with open(ruta+".XML", "wb") as f :
        #    f.write(xml_doc.encode("utf-8"))
        #
        #resp = {'respuesta': 'ok', 'url_xml': ruta+".XML"}
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def crear_xml_nota_debito(self) :
        xml_doc = """<?xml version="1.0" encoding="UTF-8"?>
<DebitNote
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ccts="urn:un:unece:uncefact:documentation:2"
    xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:qdt="urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2"
    xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1"
    xmlns:udt="urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent>
            </ext:ExtensionContent>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ID>"""
        xml_doc = xml_doc + self.number
        xml_doc = xml_doc + """</cbc:ID>
    <cbc:IssueDate>"""
        xml_doc = xml_doc + str(self.date_invoice)
        xml_doc = xml_doc + """</cbc:IssueDate>
    <cbc:IssueTime>00:00:00</cbc:IssueTime>
    <cbc:DocumentCurrencyCode>"""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """</cbc:DocumentCurrencyCode>
    <cac:DiscrepancyResponse>
        <cbc:ReferenceID>"""
        xml_doc = xml_doc + self.origin_document_id.number
        xml_doc = xml_doc + """</cbc:ReferenceID>
        <cbc:ResponseCode>"""
        xml_doc = xml_doc + """02"""
        xml_doc = xml_doc + """</cbc:ResponseCode>
        <cbc:Description><![CDATA["""
        xml_doc = xml_doc + (self.name if self.name else "Nota de débito a "+self.origin_document_id.number)
        xml_doc = xml_doc + """]]></cbc:Description>
    </cac:DiscrepancyResponse>
    <cac:BillingReference>
        <cac:InvoiceDocumentReference>
            <cbc:ID>"""
        xml_doc = xml_doc + self.origin_document_id.number
        xml_doc = xml_doc + """</cbc:ID>
            <cbc:DocumentTypeCode>"""
        xml_doc = xml_doc + self.origin_document_id.journal_id.edocument_type.code #self.debit_note_type.code
        xml_doc = xml_doc + """</cbc:DocumentTypeCode>
        </cac:InvoiceDocumentReference>
    </cac:BillingReference>
    <cac:Signature>
        <cbc:ID>IDSignST</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>"""
        xml_doc = xml_doc + self.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#SignatureSP</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.company_id.partner_id.catalog_06_id.code #"""6"""
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.company_id.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.commercial_company_name
        xml_doc = xml_doc + """]]></cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.company_id.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:AddressTypeCode>0001</cbc:AddressTypeCode>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID
                    schemeID=\""""
        xml_doc = xml_doc + self.partner_id.catalog_06_id.code #("""6""" if len(client_partner['vat']) == 11 else """1""")
        xml_doc = xml_doc + """\"
                    schemeName="SUNAT:Identificador de Documento de Identidad"
                    schemeAgencyName="PE:SUNAT"
                    schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06">"""
        xml_doc = xml_doc + self.partner_id.vat
        xml_doc = xml_doc + """</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA["""
        xml_doc = xml_doc + self.partner_id.name
        xml_doc = xml_doc + """]]></cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:TaxTotal>
        <cbc:TaxAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_untaxed, '.2f')
        xml_doc = xml_doc + """</cbc:TaxableAmount>
            <cbc:TaxAmount
                currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_tax, '.2f')
        xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxCategory>
                <cac:TaxScheme>
                    <cbc:ID
                        schemeID="UN/ECE 5153"
                        schemeAgencyID="6">1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:RequestedMonetaryTotal>
        <cbc:PayableAmount
            currencyID=\""""
        xml_doc = xml_doc + self.currency_id.name
        xml_doc = xml_doc + """\">"""
        xml_doc = xml_doc + format(self.amount_total, '.2f')
        xml_doc = xml_doc + """</cbc:PayableAmount>
    </cac:RequestedMonetaryTotal>"""
        
        i = 0
        for line in self.invoice_line_ids :
            i = i + 1
            xml_doc = xml_doc + """
    <cac:DebitNoteLine>
        <cbc:ID>"""
            xml_doc = xml_doc + str(i) #str(line.id)
            xml_doc = xml_doc + """</cbc:ID>
        <cbc:DebitedQuantity
            unitCode=\""""
            xml_doc = xml_doc + line.uom_id.unece_code
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.quantity, '.2f')
            xml_doc = xml_doc + """</cbc:DebitedQuantity>
        <cbc:LineExtensionAmount
            currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
                <cbc:PriceTypeCode>""" + """01""" + """</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>        
            <cbc:TaxAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_subtotal, '.2f')
            xml_doc = xml_doc + """</cbc:TaxableAmount>
                <cbc:TaxAmount
                    currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.igv_amount, '.2f')
            xml_doc = xml_doc + """</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>"""
            xml_doc = xml_doc + str(int(line.invoice_line_tax_ids[0].amount + 0.5)) #"""18"""
            xml_doc = xml_doc + """</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>"""
            xml_doc = xml_doc + line.igv_type.code #"""10"""
            xml_doc = xml_doc + """</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.code #"""1000"""
            xml_doc = xml_doc + """</cbc:ID>
                        <cbc:Name>"""
            xml_doc = xml_doc + """IGV"""
            xml_doc = xml_doc + """</cbc:Name>
                        <cbc:TaxTypeCode>"""
            xml_doc = xml_doc + line.invoice_line_tax_ids[0].einv_type_tax.un_5153 #"""VAT"""
            xml_doc = xml_doc + """</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        
        <cac:Item>
            <cbc:Description><![CDATA["""
            xml_doc = xml_doc + (line.product_id.name.strip() if line.product_id.name else "CONSTANT")
            xml_doc = xml_doc + """]]></cbc:Description>
            <cac:SellersItemIdentification>
                <cbc:ID><![CDATA["""
            xml_doc = xml_doc + (line.product_id.default_code.strip() if line.product_id.default_code else "C000")
            xml_doc = xml_doc + """]]></cbc:ID>
            </cac:SellersItemIdentification>
            <cac:CommodityClassification>
                <cbc:ItemClassificationCode
                    listID="UNSPSC"
                    listAgencyName="GS1 US"
                    listName="Item Classification">"""
            
            product_code = ('l10n_pe_sunat_product_code' in line.product_id._fields) and line.product_id.l10n_pe_sunat_product_code.code or '85101500' #needs a default code
            xml_doc = xml_doc + product_code
            
            xml_doc = xml_doc + """</cbc:ItemClassificationCode>
            </cac:CommodityClassification>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount
                currencyID=\""""
            xml_doc = xml_doc + line.currency_id.name
            xml_doc = xml_doc + """\">"""
            xml_doc = xml_doc + format(line.price_unit, '.2f')
            xml_doc = xml_doc + """</cbc:PriceAmount>
        </cac:Price>
    </cac:DebitNoteLine>"""
        
        xml_doc = xml_doc + """
</DebitNote>"""
    
        #with open(ruta+".XML", "wb") as f:
        #    f.write(xml_doc.encode("utf-8"))
        #
        #resp = {'respuesta': 'ok', 'url_xml': ruta+".XML"}
        resp = {'respuesta': 'ok', 'unsigned_xml': xml_doc}
        return resp
    
    def signature_xml(self, path, sign_path, sign_pass) :
        parser = etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
        path = path.encode('utf-8')
        lxml_doc = etree.fromstring(path, parser=parser)

        signer = signxml.XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha1", digest_algorithm="sha1", c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        
        verif_letra = sign_path[-1:]
        
        if verif_letra.decode() == "=" :
            sign_path = base64.b64decode(sign_path)
        sign_pkcs12 = crypto.load_pkcs12(sign_path, sign_pass)

        sign_cert = sign_pkcs12.get_certificate()
        sign_cert_cryptography = crypto.dump_certificate(crypto.FILETYPE_PEM, sign_cert).decode()
        #sign_cert_cryptography = sign_cert_cryptography.replace("-----END CERTIFICATE-----","").replace("-----BEGIN CERTIFICATE-----", "").replace("\n","")
        #sign_certs_cryptography = [sign_cert]

        sign_privatekey = sign_pkcs12.get_privatekey()
        sign_privatekey_cryptography = sign_privatekey.to_cryptography_key()

        signed_xml = signer.sign(lxml_doc, key=sign_privatekey_cryptography, cert=sign_cert_cryptography, passphrase=sign_pass)

        signed_string = etree.tostring(signed_xml).decode()
        ze = signed_string.find("<ds:Sign")
        ko = signed_string.rfind("</")
        signature_string = signed_string[ze:ko].replace("\n", "")

        doc = path.decode('utf-8') #etree.tostring(lxml_doc).decode()
        chu = doc.find("</ext:ExtensionContent>")
        xml_doc = doc[:chu] + signature_string + doc[chu:]
        if "xml version" not in xml_doc :
            xml_doc = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + xml_doc

        ze = signature_string.find("<ds:DigestValue>")
        ko = signature_string.find("</ds:DigestValue>")
        chu = len("</ds:DigestValue>")
        digest_value = signature_string[ze+chu-1:ko]

        resp= {'respuesta': 'ok', 'hash_cpe': digest_value, 'signed_xml': xml_doc}

        return resp

    def enviar_documento_prueba(self, ruc, user_sol, pass_sol, filepath, filepath_resp_code, file, path_ws) :
        #filepath debe ser el XML como string
        zip_buffer = BytesIO()

        soapURL = path_ws #"https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"

        soapUser = user_sol
        soapPass = pass_sol
        xml_doc = """<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
    xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:ser="http://service.sunat.gob.pe" 
    xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <soapenv:Header>
        <wsse:Security>
            <wsse:UsernameToken>
                <wsse:Username>"""
        xml_doc = xml_doc + ruc + soapUser
        xml_doc = xml_doc + """</wsse:Username>
                <wsse:Password>"""
        xml_doc = xml_doc + soapPass
        xml_doc = xml_doc + """</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendBill>
            <fileName>"""
        xml_doc = xml_doc + file
        xml_doc = xml_doc + """.zip</fileName>
            <contentFile>"""

        with ZipFile(zip_buffer, "a") as zip_file:
            zip_file.writestr(file+".XML", filepath.encode())
        
        zip_buffer.seek(0)
        xml_doc = xml_doc + base64.b64encode(zip_buffer.read()).decode("latin-1")

        xml_doc = xml_doc + """</contentFile>
        </ser:sendBill>
    </soapenv:Body>
    </soapenv:Envelope>"""

        headers = {"Content-type": "text/xml;charset=\"utf-8\"",
                    "Accept": "text/xml",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "SOAPAction": "",
                    "Content-length": str(len(xml_doc))}

        resp_code = requests.post(soapURL, data=xml_doc, headers=headers)
        content = parseString(resp_code.text)

        if len(content.getElementsByTagNameNS("*", "applicationResponse")) > 0 :
            content = content.getElementsByTagNameNS("*", "applicationResponse")[0].childNodes[0].nodeValue.strip()

            with ZipFile(BytesIO(base64.b64decode(content))) as thezip :
                for zipinfo in thezip.infolist() :
                    with thezip.open(zipinfo) as thefile:
                        respuesta_xml = thefile.read().decode()

            #Hash CDR
            content = parseString(respuesta_xml)
            mensaje = {"cod_sunat": content.getElementsByTagNameNS("*", "ResponseCode")[0].childNodes[0].nodeValue,
                        "msj_sunat": content.getElementsByTagNameNS("*", "Description")[0].childNodes[0].nodeValue,
                        "hash_cdr": content.getElementsByTagNameNS("*", "DigestValue")[0].childNodes[0].nodeValue}
        else :
            mensaje = {"cod_sunat": content.getElementsByTagNameNS("*", "faultcode")[0].childNodes[0].nodeValue,
                        "msj_sunat": content.getElementsByTagNameNS("*", "faultstring")[0].childNodes[0].nodeValue,
                        "hash_cdr": ""}

        return mensaje
    
    #@api.multi
    #def action_invoice_open(self):
    #    opened_invoice = super(AccountInvoice, self).action_invoice_open()
    #    
    #    #B042-00000001 self.env['account.move'].search([], order='id desc')[0].line_ids[0].ref.split('/')[0]
    #    acc_move = self.env['account.move'].search([], order='id desc')[0].line_ids[0]
    #    if not acc_move.invoice_id :
    #        return opened_invoice
    #    
    #    #raise UserError(_("Hello."))
    #    
    #    new_invoice = self.env['account.move'].search([], order='id desc')[0].line_ids[0].invoice_id
    #    tipo = new_invoice.journal_id.edocument_type.code
    #    
    #    if tipo in ('01', '03') :
    #        unsigned_invoice_dictionary = new_invoice.crear_xml_factura()
    #    elif tipo in ('07') :
    #        #raise UserError(_("Es nota de credito"))
    #        unsigned_invoice_dictionary = new_invoice.crear_xml_nota_credito()
    #    elif tipo in ('08') :
    #        #raise UserError(_("Es nota de debito"))
    #        unsigned_invoice_dictionary = new_invoice.crear_xml_nota_debito()
    #    
    #    new_invoice.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml']})
    #    
    #    sign_path = b'VERYLONGBYTESTRING'
    #    sign_pass = '123456'
    #    signed_invoice_dictionary = new_invoice.signature_xml(unsigned_invoice_dictionary['unsigned_xml'], sign_path, sign_pass)
    #    new_invoice.write({'signed_xml': signed_invoice_dictionary['signed_xml']})
    #    #new_invoice.write({'digest_value': signed_invoice_dictionary['hash_cpe']})
    #    
    #    ruc = new_invoice.company_id.partner_id.vat
    #    serie, correlativo = new_invoice.number.split("-")
    #    filename = ruc + "-" + tipo + "-" + serie + "-" + correlativo
    #    path_ws = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"
    #    respuesta = new_invoice.enviar_documento_prueba(ruc, "MODDATOS", "MODDATOS", signed_invoice_dictionary['signed_xml'], "R-" + filename, filename, path_ws) #enviar_documento_prueba(self, ruc, user_sol, pass_sol, filepath, filepath_resp_code, file, path_ws)
    #    if respuesta['cod_sunat'] == '0' :
    #        new_invoice.write({
    #                            'sunat_answer': respuesta['msj_sunat'],
    #                            'digest_value': respuesta['hash_cdr'],
    #                            'cod_sunat' : respuesta['cod_sunat'],
    #                          })
    #    else :
    #        raise UserError(_(respuesta['cod_sunat']+" - "+respuesta['msj_sunat']))
    #    
    #    return opened_invoice
    @api.multi
    def action_invoice_open(self):
        for record in self :
            if not record.date_invoice :
                record.date_invoice = fields.Date.today()
        #a = 1/0
        res = super(AccountInvoice, self).action_invoice_open()
        #for record in self :
        #    tipo = record.journal_id.edocument_type.code
        #    
        #    if tipo == '01' and ((not record.partner_id.catalog_06_id) or record.partner_id.catalog_06_id.code != '6') :
        #        #Factura con DNI
        #        raise UserError(_("No puede validar una factura con un cliente que no posea RUC"))
        #    
        #    if tipo in ['01', '03'] :
        #        unsigned_invoice_dictionary = record.crear_xml_factura()
        #    elif tipo in ['07'] :
        #        #raise UserError(_("Es nota de credito"))
        #        unsigned_invoice_dictionary = record.crear_xml_nota_credito()
        #    elif tipo in ('08') :
        #        #raise UserError(_("Es nota de debito"))
        #        unsigned_invoice_dictionary = record.crear_xml_nota_debito()
        #    else :
        #        return res
        #    
        #    record.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml']})
        
        #invoice_company = self.shop_id.company_id
        
        #sign_path = invoice_company.digital_certificate #Very long string like b'0\x82\x0br\x02\x01\x030\x82\x0b<\x06\t...'
        #sign_pass = invoice_company.digital_password #'123456'
        #signed_invoice_dictionary = self.signature_xml(unsigned_invoice_dictionary['unsigned_xml'], sign_path, sign_pass)
        #self.write({'signed_xml': signed_invoice_dictionary['signed_xml']})
        ##self.write({'digest_value': signed_invoice_dictionary['hash_cpe']})
        
        return res
    
    @api.multi
    def action_invoice_send_sunat(self):
        self.ensure_one()
        
        if self.state in ['draft','cancel'] :
            raise UserError(_("Solo se puede enviar a SUNAT comprobantes validados")) 
        
        tipo = self.journal_id.edocument_type.code
        
        if tipo in ('01', '03') :
            unsigned_invoice_dictionary = self.crear_xml_factura()
        elif tipo in ('07') :
            #raise UserError(_("Es nota de credito"))
            unsigned_invoice_dictionary = self.crear_xml_nota_credito()
        elif tipo in ('08') :
            #raise UserError(_("Es nota de debito"))
            unsigned_invoice_dictionary = self.crear_xml_nota_debito()
        
        self.write({'unsigned_xml': unsigned_invoice_dictionary['unsigned_xml']})
        
        invoice_company = self.shop_id.company_id
        
        sign_path = invoice_company.digital_certificate #Very long string like b'0\x82\x0br\x02\x01\x030\x82\x0b<\x06\t...'
        if invoice_company.user_sol == 'MODDDATOS' :
            sign_path = invoice_company._default_digital_certificate()
        sign_pass = invoice_company.digital_password #'123456'
        signed_invoice_dictionary = self.signature_xml(unsigned_invoice_dictionary['unsigned_xml'], sign_path, sign_pass)
        self.write({'signed_xml': signed_invoice_dictionary['signed_xml']})
        #self.write({'digest_value': signed_invoice_dictionary['hash_cpe']})
        
        ruc = self.shop_id.company_id.partner_id.vat
        serie, correlativo = self.number.split("-")
        filename = ruc + "-" + tipo + "-" + serie + "-" + correlativo
        path_ws = "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService?wsdl"
        if invoice_company.user_sol == 'MODDDATOS' :
            path_ws = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService?wsdl"
        respuesta = self.enviar_documento_prueba(ruc, invoice_company.user_sol, invoice_company.pass_sol, signed_invoice_dictionary['signed_xml'], "R-" + filename, filename, path_ws) #enviar_documento_prueba(self, ruc, user_sol, pass_sol, filepath, filepath_resp_code, file, path_ws)
        if respuesta['cod_sunat'] == '0' :
            self.write({
                        'sunat_answer': respuesta['msj_sunat'],
                        'digest_value': respuesta['hash_cdr'],
                        'cod_sunat' : respuesta['cod_sunat'],
                        'sent_sunat' : True,
                      })
        else :
            raise UserError(_(respuesta['cod_sunat']+" - "+respuesta['msj_sunat']))
        
        return True
    
    ###################################################################
    
    # Onchange created for getting the default edocument type from the journal
    @api.onchange('journal_id')
    def onchange_edocument_type(self) :
        if self.journal_id:
            self.edocument_type = self.journal_id.edocument_type
            if self.journal_id.edocument_credit :
                self.credit_note_type = self.journal_id.edocument_credit
            if self.journal_id.edocument_debit :
                self.debit_note_type = self.journal_id.edocument_debit
    
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'invoice_line_ids.price_base', 'tax_line_ids.amount',
                 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        super(AccountInvoice, self)._compute_amount()
        self.global_discount = sum(line.price_base for line in self.invoice_line_ids.filtered(lambda r: r.price_base * sign < 0)) * sign * -1
        self.amount_discount = sum((line.price_base * line.discount)/100 for line in self.invoice_line_ids.filtered(lambda r: r.free_product == False))
        self.amount_base = sum(line.price_base for line in self.invoice_line_ids.filtered(lambda r: r.price_total > 0))
        #~ E-invoice amounts
        self.einv_amount_free = sum(line.amount_free for line in self.invoice_line_ids)
        self.einv_amount_base = sum(line.base for line in self.tax_line_ids.filtered(lambda r: any(x in (r.einv_type_tax.name if r.einv_type_tax else 'igv') for x in ('igv','isc'))))
        self.einv_amount_exonerated = sum(line.base for line in self.tax_line_ids.filtered(lambda r: (r.einv_type_tax.name if r.einv_type_tax else 'igv') == 'exonerated'))
        self.einv_amount_unaffected = sum(line.base for line in self.tax_line_ids.filtered(lambda r: (r.einv_type_tax.name if r.einv_type_tax else 'igv') == 'unaffected'))
        self.einv_amount_igv = sum(line.amount_total for line in self.tax_line_ids.filtered(lambda r: (r.einv_type_tax.name if r.einv_type_tax else 'igv') == 'igv'))
        self.einv_amount_others = sum(line.amount_total for line in self.tax_line_ids.filtered(lambda r: (r.einv_type_tax.name if r.einv_type_tax else 'igv') == 'others'))
        self.einv_amount_untaxed = self.einv_amount_base - self.einv_amount_free
    
    @api.multi
    @api.depends('move_id.name','move_name')
    def _get_einvoice_number(self):
        for inv in self:
            if inv.move_name and inv.type in ['out_invoice','out_refund']:
                inv_number = inv.move_name.split('-')
                if len(inv_number) == 2:
                     inv.einv_serie = inv_number[0]
                     inv.einv_number = inv_number[1]
        return True
    
    @api.depends('tax_line_ids')
    def _get_percentage_igv(self):
        for inv in self:
            igv = 0.0
            if inv.tax_line_ids:
                for tax in inv.tax_line_ids.filtered(lambda r: r.einv_type_tax.code == 'igv' and r.tax_id.amount_type == 'percent') :
                    igv = int(tax.tax_id.amount)
            inv.igv_percent = igv
        return True
    
    @api.onchange('origin_document_id')
    def onchange_origin_document(self):
        if self.origin_document_id:
            if self.type == 'out_refund':
                self.origin_document_serie = self.origin_document_id.einv_serie
                self.origin_document_number = self.origin_document_id.einv_number
            else:
                if self.origin_document_id and self.origin_document_id.number:
                    numero_origen = self.origin_document_id.number.split('-')
                    if len(numero_origen) == 2:
                        self.origin_document_serie = numero_origen[0]
                        self.origin_document_number = numero_origen[1]
                    
    def _prepare_tax_line_vals(self, line, tax):
        #~ Adding Type of tax IGV, ISC and others
        vals = super(AccountInvoice, self)._prepare_tax_line_vals(line, tax)
        vals.update({'einv_type_tax':self.env['account.tax'].browse(tax['id']).einv_type_tax})
        return vals

    ###################################################################
    
    @api.model
    def _prepare_refund(self, invoice, date_invoice=None, date=None, description=None, journal_id=None):
        """ Prepare the dict of values to create the new credit note from the invoice.
            This method may be overridden to implement custom
            credit note generation (making sure to call super() to establish
            a clean extension chain).

            :param record invoice: invoice as credit note
            :param string date_invoice: credit note creation date from the wizard
            :param integer date: force date from the wizard
            :param string description: description of the credit note from the wizard
            :param integer journal_id: account.journal from the wizard
            :return: dict of value to create() the credit note
        """
        values = super(AccountInvoice, self)._prepare_refund(invoice, date_invoice=date_invoice, date=date, description=description, journal_id=journal_id)
        new_journal = self.env['account.journal'].search([('edocument_type','in',[8]),('edocument_credit','in',[invoice.journal_id.edocument_type.id]),('active','=',True)])
        if new_journal :
            values.update({'origin_document_id': invoice.id,
                           'origin_document_serie': invoice.number.split('-')[0],
                           'origin_document_number': invoice.number.split('-')[1],
                           'journal_id': new_journal[0].id,
                           'edocument_type': 8,
                           'credit_note_type': invoice.journal_id.edocument_type.id})
        else :
            raise UserError(_("Debe crear un diario para notas de credito"))
        
        return values

    ###################################################################
    
    @api.multi
    def action_create_customer_debit_note(self):
        #Method to open create customer invoice form
        #Get the client id from transport form
        default_partner_id = self.partner_id.id
        default_journal_id = self.env['account.journal'].search([('edocument_type','in',[9]),('shop_id','in',[self.shop_id.id]),('active','=','True')], limit=1).id
        default_origin_document_id = self.id
        
        #Initialize required parameters for opening the form view of invoice
        #Get the view ref. by paasing module & name of the required form
        view_id = self.env.ref('account.invoice_form').id

        #Let's prepare a dictionary with all necessary info to open create invoice form with          
        #customer/client pre-selected
        res = { 'type': 'ir.actions.act_window',
                'name': _('Customer Invoice'),
                'res_model': 'account.invoice',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': view_id,
                'target': 'current',
                'context': {'default_partner_id': default_partner_id,
                            'default_shop_id': self.shop_id.id,
                            'default_journal_id': default_journal_id,
                            'default_einvoice_journal_id': default_journal_id,
                            'default_origin_document_id': default_origin_document_id
                            }
                }

        return res
        
class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"
    
    def _get_igv_type(self):
        return self.env['einvoice.catalog.07'].search([('code','=','10')], limit=1)
    
    amount_discount = fields.Monetary(string='Amount discount before taxes', readonly=True, compute='_compute_price')
    amount_free = fields.Monetary(string='Amount free', readonly=True, compute='_compute_price')
    free_product = fields.Boolean('Free', compute='_compute_price', store=True, default=False)
    igv_type = fields.Many2one('einvoice.catalog.07', string="Type of IGV", default=_get_igv_type)
    igv_amount = fields.Monetary(string='IGV amount',readonly=True, compute='_compute_price', help="Total IGV amount")
    price_base = fields.Monetary(string='Subtotal without discounts', readonly=True, compute='_compute_price', help="Total amount without discounts and taxes", store=True)
    price_total = fields.Monetary(string='Amount (with Taxes)', store=True, readonly=True, compute='_compute_price', help="Total amount with taxes")
    price_unit_excluded = fields.Monetary(string='Price unit excluded', readonly=True, compute='_compute_price', help="Price unit without taxes")
    price_unit_included = fields.Monetary(string='Price unit IGV included', readonly=True, compute='_compute_price', help="Price unit with IGV included")
    
    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        '''
        return price_base = price_subtotal whitout discounts
        '''
        super(AccountInvoiceLine, self)._compute_price()      
        if self.display_type == False:
            currency = self.invoice_id and self.invoice_id.currency_id or None
            price = self.price_unit        
            # without all taxes
            taxes = False
            if self.invoice_line_tax_ids:
                taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
            if self.quantity == 0:
                raise UserError('The quantity cannot be 0')
            else:
                self.price_unit_excluded = price_unit_excluded_signed = taxes['total_excluded']/self.quantity if taxes else price
                self.price_base = price_base_signed = taxes['total_excluded'] if taxes else self.quantity * price 
            #~ With IGV taxes
            igv_taxes = False
            igv_taxes_ids = self.invoice_line_tax_ids.filtered(lambda r: 'igv' in (r.einv_type_tax.name.lower() if r.einv_type_tax.name else 'igv'))
            if igv_taxes_ids:
                igv_taxes = igv_taxes_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
            self.price_unit_included = price_unit_included_signed = igv_taxes['total_included']/self.quantity if igv_taxes else price
            #~ IGV amount after discount
            if igv_taxes_ids:
                igv_taxes_discount = igv_taxes_ids.compute_all(price * (1 - (self.discount or 0.0) / 100.0), currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
                self.igv_amount = sum( r['amount'] for r in igv_taxes_discount['taxes'])        
            
            self.price_total = taxes['total_included'] if taxes else self.price_subtotal
            sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
            self.price_base = price_base_signed * sign       
            self.price_unit_excluded = price_unit_excluded_signed * sign       
            self.price_unit_included = price_unit_included_signed * sign    
            #~ Discount line
            #~ Free amount
            if self.discount >= 100.0:  
                self.igv_amount = 0.0   # When the product is free, igv = 0
                self.amount_discount = 0.0  # Although the product has 100% discount, the amount of discount in a free product is 0 
                self.igv_type = self.env['einvoice.catalog.07'].search([('code','=','15')], limit=1)
                self.free_product = True
                self.amount_free = self.price_unit_excluded * self.quantity
            else:
                self.amount_discount = (self.price_unit_excluded * self.discount * self.quantity) / 100
                self.igv_amount = abs(self.igv_amount) > 0.01 and abs(self.igv_amount) or 0.02 # The IGV must be > 0.01, i't mandatory in Odoofact
                self.igv_type = self.env['einvoice.catalog.07'].search([('code','=','10')], limit=1)
                self.free_product = False
    
    @api.onchange('igv_type')
    def onchange_igv_type(self):
        if self.igv_type:
            company_id = self.company_id or self.env.user.company_id
            taxes = self.env['account.tax'].search([('company_id','=',company_id.id)])
            if self.igv_type.type == 'gravado':
                taxes = taxes.filtered(lambda r: 'igv' in (r.einv_type_tax.name.lower() if r.einv_type_tax.name else 'igv'))[0]
            elif self.igv_type.type == 'inafecto':
                taxes = taxes.filtered(lambda r: 'inafecto' in (r.einv_type_tax.name.lower() if r.einv_type_tax.name else 'inafecto'))[0]
            else:
                taxes = taxes.filtered(lambda r: 'exonerado' in (r.einv_type_tax.name.lower() if r.einv_type_tax.name else 'exonerado'))[0]
            self.invoice_line_tax_ids = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)

class AccountInvoiceTax(models.Model):
    _inherit = "account.invoice.tax"
    
    einv_type_tax = fields.Many2one('einvoice.catalog.05', string='Tax type code', help='Catalog 05: Tax type code', default=1) #fields.Selection(related='tax_id.einv_type_tax', string="Tax type")
    
    @api.model
    def create(self, vals) :
        if ('einv_type_tax' in vals) and (type(vals['einv_type_tax']) is not int) :
            vals['einv_type_tax'] = vals['einv_type_tax'].id
        return super(AccountInvoiceTax, self).create(vals)
