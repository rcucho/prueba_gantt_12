# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import Warning, UserError

import requests

def get_data_doc_number(tipo_doc, numero_doc, format='json'):
    '''
    user, password = 'demorest', 'demo1234'
    url = 'http://py-devs.com/api'
    url = '%s/%s/%s' % (url, tipo_doc, str(numero_doc))
    res = {'error': True, 'message': None, 'data': {}}
    try:
        response = requests.get(url, auth=(user, password), timeout=5)
    except:
        res['message'] = 'Error en la conexion'
        return res
    
    if response.status_code == 200:
        res['error'] = False
        res['data'] = response.json()
    else:
        try:
            res['message'] = response.json()['detail']
        except Exception as e:
            res['error'] = True
    return res
    '''
    #DNI
    url = 'https://api.reniec.cloud/dni/%s' % (numero_doc,)
    res = {
        'error': True,
        'message': None,
        'data': dict(),
    }
    try :
        response = requests.get(url, verify=False, timeout=10)
    except :
        res.update({
            'message': 'Error en la conexion',
        })
    if not res.get('message') :
        if response.status_code == 200 :
            datos = dict()
            try :
                datos = response.json()
            except :
                res.update({
                    'message': 'Error en el servicio',
                })
            if datos :
                try :
                    datos.update({
                        'digito': datos.get('cui'),
                        'ape_paterno': datos.get('apellido_paterno'),
                        'ape_materno': datos.get('apellido_materno'),
                        'nombres': datos.get('nombres'),
                    })
                    res.get('data').update(datos)
                except :
                    res.update({
                        'message': 'Error en los datos',
                    })
                if (not res.get('message')) and (len(str(datos.get('digito', '01'))) == 1) :
                    res.update({
                        'error': False,
                    })
            elif not res.get('message') :
                res.update({
                    'message': 'Error en los datos',
                })
        else :
            res.update({
                'message': 'Error en la respuesta',
            })
    return res

def new_get_data_doc_number(tipo_doc, numero_doc, format='json'):
    '''
    user, password = 'Hf526gujsgerd12', 'Hf526gujsgerd12'
    url = 'https://sistemadefacturacionelectronicasunat.com/api'
    url = '%s/%s/%s/%s' % (url, tipo_doc, str(numero_doc), password)
    res = {'error': True, 'message': None, 'data': {}}
    try:
        response = requests.get(url, timeout=5)
    except:
        res['message'] = 'Error en la conexion'
        return res
    
    if response.status_code == 200:
        res['error'] = False
        data = response.json()
        if len(numero_doc) == 8 :
            if not (data['nombres'] or data['ap_paterno'] or data['ap_materno']) :
                data['nombre'] = "".join(e for e in data['nombre'] if e.isalpha() or e in [" ","-","_"] or e.isdigit())
                nombres = data['nombre'].rsplit(" ",2)
                data['nombres'] = nombres[0]
                data['ape_paterno'] = nombres[1]
                data['ape_materno'] = nombres[2]
        else :
            data['provincia'] = 'LIMA'
            data['distrito'] = 'LIMA'
            data['condicion_contribuyente'] = data['condicion']
            data['nombre'] = data['razon_social']
            data['domicilio_fiscal'] = data['direccion']
        res['data'] = data
    else:
        try:
            res['message'] = response.json()['respuesta']
        except Exception as e:
            res['error'] = True
    return res
    '''
    #RUC
    url = 'https://api.sunat.cloud/ruc'
    url = '%s/%s' % (url, str(numero_doc))
    res = {
        'error': True,
        'message': None,
        'data': dict(),
    }
    try:
        response = requests.get(url, verify=False, timeout=10)
    except:
        res.update({
            'message': 'Error en la conexion',
        })
    if not res.get('message') :
        if response.status_code == 200 :
            res_data = res.get('data')
            try :
                res_data.update(response.json())
            except :
                res.update({
                    'message': 'Error en los datos',
                })
            if not res.get('message') :
                if 'razon_social' not in res_data :
                    res.update({
                        'message': 'Error en los datos',
                    })
                else :
                    res.update({
                        'error': False,
                    })
        else :
            res.update({
                'message': 'Error en la respuesta',
            })
    return res

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    registration_name = fields.Char('Registration Name', size=128, index=True, )
    catalog_06_id = fields.Many2one('einvoice.catalog.06','Tipo Doc.', index=True)
    state = fields.Selection([('habido','Habido'),('nhabido','No Habido')],'State')
    
    #~ tipo_contribuyente = fields.Char('Tipo de contribuyente')
    #~ fecha_inscripcion = fields.Date('Fecha de inscripción')
    #~ estado_contribuyente = fields.Char('Estado del contribuyente')
    #~ agente_retencion = fields.Boolean('Agente de Retención')
    #~ agente_retencion_apartir_del = fields.Date('A partir del')
    #~ agente_retencion_resolucion = fields.Char('Resolución')
    #~ sistema_emision_comprobante = fields.Char('Sistema emisión')
    #~ sistema_contabilidad = fields.Char('Sistema contabilidad')
    #~ ultima_actualizacion_sunat = fields.Date('Última actualización')
    
    @api.onchange('catalog_06_id','vat')
    def vat_change(self):
        self.update_document()
    
    @api.one
    def update_document(self):
        if not self.vat:
            return False
        if self.catalog_06_id and self.catalog_06_id.code == '1':
           #Valida DNI
            if self.vat and len(self.vat) != 8:
                raise Warning('El DNI debe tener 8 caracteres')
            else:
                d = get_data_doc_number('dni', self.vat, format='json')
                #d = new_get_data_doc_number('persona', self.vat, format='json')
                ################################################################
                d.update({
                    'error': True,
                })
                ################################################################
                if not d['error']:
                    d = d['data']
                    self.name = '%s %s %s' % (d['nombres'],
                                               d['ape_paterno'],
                                               d['ape_materno'])
                    
                dist_id = self.env['res.country.state'].search([('country_id','=',173),('name','=','LIMA'),('code','ilike','0101')])  #default=LIMA
                    
                self.country_id = dist_id.country_id.id
                self.state_id = dist_id.state_id.id
                self.province_id = dist_id.province_id.id
                self.street = 'Unknown 123'
                self.district_id = dist_id.id
        elif self.catalog_06_id and self.catalog_06_id.code == '6':
            # Valida RUC
            if self.vat and len(self.vat) != 11:
                raise Warning('El RUC debe tener 11 caracteres')
            else:
                #d = get_data_doc_number('ruc', self.vat, format='json')
                d = new_get_data_doc_number('empresa', self.vat, format='json')
                
                dist_id = self.env['res.country.state'].search([('country_id','=',173),('name','=','LIMA'),('code','ilike','0101')])  #default=LIMA
                
                self.country_id = dist_id.country_id.id
                self.state_id = dist_id.state_id.id
                self.province_id = dist_id.province_id.id
                self.district_id = dist_id.id
                self.street = 'Unknown 123'
                ################################################################
                d.update({
                    'error': True,
                })
                ################################################################
                
                if d['error']:
                    return True
                d = d['data']
                #~ Busca el distrito
                ditrict_obj = self.env['res.country.state']
                prov_ids = ditrict_obj.search([('name', '=', d['provincia']),
                                               ('province_id', '=', False),
                                               ('state_id', '!=', False)])
                dist_id = ditrict_obj.search([('name', '=', d['distrito']),
                                              ('province_id', '!=', False),
                                              ('state_id', '!=', False),
                                              ('province_id', 'in', [x.id for x in prov_ids])], limit=1)
                dist_id = dist_id or self.env['res.country.state'].search([('country_id','=',173),('name','=','LIMA'),('code','ilike','0101')])  #default=LIMA
                
                self.country_id = dist_id.country_id.id
                self.state_id = dist_id.state_id.id
                self.province_id = dist_id.province_id.id
                self.district_id = dist_id.id

                # Si es HABIDO, caso contrario es NO HABIDO
                tstate = d['condicion_contribuyente']
                if tstate == 'HABIDO':
                    tstate = 'habido'
                else:
                    tstate = 'nhabido'
                self.state = tstate
            
                self.name = d['nombre_comercial'] != '-' and d['nombre_comercial'] or d['nombre']
                self.registration_name = d['nombre']
                self.street = d['domicilio_fiscal']
                self.vat_subjected = True
                self.is_company = True
        else:
            return True
