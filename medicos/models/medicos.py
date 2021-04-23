# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT,DEFAULT_SERVER_TIME_FORMAT,DEFAULT_SERVER_DATE_FORMAT
import datetime

def nombreMes(numeroMes) :
    return {
            1: 'Enero',
            2: 'Febrero',
            3: 'Marzo',
            4: 'Abril',
            5: 'Mayo',
            6: 'Junio',
            7: 'Julio',
            8: 'Agosto',
            9: 'Setiembre',
            10: 'Octubre',
            11: 'Noviembre',
            12: 'Diciembre'
           }.get(numeroMes)

def ultimoDiaMes(fecha) :
    if type(fecha) == datetime.datetime :
        fecha = fecha.date()
    ultimo = fecha.replace(day=28) + datetime.timedelta(days=4)
    return ultimo - datetime.timedelta(days=ultimo.day)

class ResPartner(models.Model) :
    _inherit = 'res.partner'
    
    es_medico = fields.Boolean('Médico referente')
    es_visitador = fields.Boolean('Visitadora')
    es_paciente = fields.Boolean('Paciente')
    es_aseguradora = fields.Boolean('Aseguradora', default=False)
    es_changing = fields.Boolean('Cambiando...', default=False)
    vis_id = fields.Many2one('hr.employee', string='Visitadora actual', default=False)
    vis_ids = fields.One2many('res.partner.visitador', 'med_id', string='Visitadoras')
    porcentaje_honor = fields.Float('Honorarios (%)', default=10.0)
    
    @api.multi
    def write(self, values) :
        visitadora_line = self.vis_ids.filtered(lambda r: r.vis_id.id==self.vis_id.id and not r.vis_fin) if self.vis_id else False
        if visitadora_line :
            visitadora_line.write({'vis_fin':str(datetime.datetime.now())})
        if values.get('vis_id') :
            self.env['res.partner.visitador'].sudo().create({'med_id':self.id,
                                                             'vis_id':values.get('vis_id'),
                                                             'vis_ini':str(datetime.datetime.now())})
        
        return super(ResPartner, self).write(values)
    
    @api.model
    def create(self, vals) :
        the_partner_id = super(ResPartner, self).create(vals)
        if the_partner_id.vis_id :
            self.env['res.partner.visitador'].sudo().create({'med_id':the_partner_id.id,
                                                             'vis_id':the_partner_id.vis_id.id,
                                                             'vis_ini':str(datetime.datetime.now())})
        return the_partner_id

class VisitadoresLine(models.Model) :
    _name = 'res.partner.visitador'
    _description = 'Relación médico-visitador'
    
    vis_id = fields.Many2one('hr.employee', string='Visitador(a)', ondelete='cascade', index=True)
    med_id = fields.Many2one('res.partner', string='Médico', ondelete='cascade', index=True)
    vis_ini = fields.Datetime(string='Fecha de inicio', default=False)
    vis_fin = fields.Datetime(string='Fecha de fin', default=False)

class SaleOrder(models.Model) :
    _inherit = 'sale.order'
    
    @api.one
    def write(self, vals) :
        if self.state == 'done' and vals.get('x_studio_medico_referente') :
            honor = self.env['medicos.honorarios'].search([('sale_order_id','=',self.id)],limit=1)
            if honor and honor.honor_med_id and honor.honor_med_id.id != vals.get('x_studio_medico_referente') :
                honor.write({'honor_med_id':(vals.get('x_studio_medico_referente') or False)})
        return super(SaleOrder, self).write(vals)
    
    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        #Resulta que primero se aplican las acciones automaticas
        
        medi_id = self.x_studio_medico_referente.id if self.x_studio_medico_referente else False
        visi_id = self.x_studio_medico_referente.vis_id.id if self.x_studio_medico_referente and self.x_studio_medico_referente.vis_id else False
        
        monto_honor = 0.0
        num_estudios = 0
        for linea in self.order_line :
            monto_honor = monto_honor + linea.price_unit * linea.product_uom_qty
            num_estudios = num_estudios + int(linea.product_uom_qty)
        monto_honor = monto_honor*(self.x_studio_medico_referente.porcentaje_honor if medi_id else 10.0)/100.0
        
        self.env['medicos.honorarios'].sudo().create({'sale_order_id': self.id,
                                                      'honor_med_id': medi_id,
                                                      'honor_vis_id': visi_id,
                                                      'honor_med_monto': monto_honor,
                                                      'honor_vis_monto': 10.0*num_estudios,
                                                      'honor_fecha': str(datetime.datetime.now())})
        return res

class Honorarios(models.Model) :
    _name = 'medicos.honorarios'
    _description = 'Listado de honorarios médicos'
    
    sale_order_id = fields.Many2one('sale.order', string='Estudio')
    honor_med_id = fields.Many2one('res.partner', string='Médico')
    honor_vis_id = fields.Many2one('hr.employee', string='Visitador(a)')
    honor_med_monto = fields.Monetary(string='Monto de honorarios médicos', currency_field='currency_id', default=0.0)
    honor_vis_monto = fields.Monetary(string='Monto de honorarios visitadora', currency_field='currency_id', default=0.0)
    honor_fecha = fields.Datetime('Fecha de honorario', default=datetime.datetime.now())
    currency_id = fields.Many2one('res.currency', string='Moneda', default=162)
    
    @api.one
    def write(self, vals) :
        fecha_de_honor = self.honor_fecha.date().replace(day=15)
        
        medic_new = False
        medic_old = False
        if vals.get('honor_med_id') :
            medic_new = self.env['medicos.honorarios.medicos'].search([('med_id','=',vals.get('honor_med_id')),
                                                                       ('fecha_honor','=',fecha_de_honor)])
        if self.honor_med_id :
            medic_old = self.env['medicos.honorarios.medicos'].search([('med_id','=',self.honor_med_id.id),
                                                                       ('fecha_honor','=',fecha_de_honor)])
        
        visit_new = False
        visit_old = False
        if vals.get('honor_vis_id') :
            visit_new = self.env['medicos.honorarios.visitadoras'].search([('vis_id','=',vals.get('honor_vis_id')),
                                                                           ('fecha_honor','=',fecha_de_honor)])
        if self.honor_vis_id :
            visit_old = self.env['medicos.honorarios.visitadoras'].search([('vis_id','=',self.honor_vis_id.id),
                                                                           ('fecha_honor','=',fecha_de_honor)])
        
        res = super(Honorarios, self).write(vals)
        if vals.get('honor_med_id') :
            if not medic_new :
                medic_new = self.env['medicos.honorarios.medicos'].sudo().create({'med_id': vals.get('honor_med_id'),
                                                                                  'fecha_honor': str(fecha_de_honor),
                                                                                  'fecha_ini': str(fecha_de_honor.replace(day=1)),
                                                                                  'fecha_fin': str(ultimoDiaMes(fecha_de_honor)),
                                                                                  'year_honor': fecha_de_honor.year,
                                                                                  'honor_year': str(fecha_de_honor.year),
                                                                                  'month_honor': nombreMes(fecha_de_honor.month)})
            medic_new.actualizar()
        if vals.get('honor_vis_id') :
            if not visit_new :
                visit_new = self.env['medicos.honorarios.visitadoras'].sudo().create({'vis_id': vals.get('honor_vis_id'),
                                                                                      'fecha_honor': str(fecha_de_honor),
                                                                                      'fecha_ini': str(fecha_de_honor.replace(day=1)),
                                                                                      'fecha_fin': str(ultimoDiaMes(fecha_de_honor)),
                                                                                      'year_honor': fecha_de_honor.year,
                                                                                      'honor_year': str(fecha_de_honor.year),
                                                                                      'month_honor': nombreMes(fecha_de_honor.month)})
            visit_new.actualizar()
        
        if medic_old :
            medic_old.actualizar()
        if visit_old :
            visit_old.actualizar()
        
        return res
    
    @api.model
    def create(self, vals) :
        res = super(Honorarios, self).create(vals)
        fecha_de_honor = res.honor_fecha.date().replace(day=15)
        
        if res.honor_med_id :
            medic = self.env['medicos.honorarios.medicos'].search([('med_id','=',res.honor_med_id.id),
                                                                   ('fecha_honor','=',fecha_de_honor)])
            if not medic :
                medic = self.env['medicos.honorarios.medicos'].sudo().create({'med_id': res.honor_med_id.id,
                                                                              'fecha_honor': str(fecha_de_honor),
                                                                              'fecha_ini': str(fecha_de_honor.replace(day=1)),
                                                                              'fecha_fin': str(ultimoDiaMes(fecha_de_honor)),
                                                                              'year_honor': fecha_de_honor.year,
                                                                              'honor_year': str(fecha_de_honor.year),
                                                                              'month_honor': nombreMes(fecha_de_honor.month)})
            medic.actualizar()
        
        if res.honor_vis_id :
            visit = self.env['medicos.honorarios.visitadoras'].search([('vis_id','=',res.honor_vis_id.id),
                                                                       ('fecha_honor','=',fecha_de_honor)])
            if not visit :
                visit = self.env['medicos.honorarios.visitadoras'].sudo().create({'vis_id': res.honor_vis_id.id,
                                                                                  'fecha_honor': str(fecha_de_honor),
                                                                                  'fecha_ini': str(fecha_de_honor.replace(day=1)),
                                                                                  'fecha_fin': str(ultimoDiaMes(fecha_de_honor)),
                                                                                  'year_honor': fecha_de_honor.year,
                                                                                  'honor_year': str(fecha_de_honor.year),
                                                                                  'month_honor': nombreMes(fecha_de_honor.month)})
            visit.actualizar()
        
        return res

class HonorariosMedicos(models.Model) :
    _name = 'medicos.honorarios.medicos'
    _description = 'Honorarios mensuales de médicos'
    
    med_id = fields.Many2one('res.partner', string='Médico', ondelete='cascade', index=True)
    fecha_honor = fields.Date(string='Fecha del mes y año de cálculo de honorarios', default=lambda self: self._default_fecha_honor())
    fecha_ini = fields.Date(string='Fecha de inicio del cálculo de honorarios', compute=lambda self: self._compute_fecha_honor())
    fecha_fin = fields.Date(string='Fecha de término del cálculo de honorarios', compute=lambda self: self._compute_fecha_honor())
    year_honor = fields.Integer(string='Año', compute=lambda self: self._compute_fecha_honor())
    honor_year = fields.Char(string='Año', compute=lambda self: self._compute_fecha_honor())
    month_honor = fields.Char(string='Mes', compute=lambda self: self._compute_fecha_honor())
    honor_mes = fields.Monetary(string='Monto de honorarios del mes', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=162)
    
    def actualizar(self) :
        fecha = datetime.datetime(self.fecha_honor.year,self.fecha_honor.month,self.fecha_fin.day,23,59,59)
        registros = self.env['medicos.honorarios'].search([('honor_med_id','=',self.med_id.id),
                                                           ('honor_fecha','<=',fecha),
                                                           ('honor_fecha','>=',fecha.replace(day=1,hour=0,minute=0,second=0))])
        self.honor_mes = sum(registros.mapped('honor_med_monto'))
    
    @api.model
    def _default_fecha_honor(self) :
        return datetime.date.today().replace(day=15)
    
    @api.one
    @api.depends('fecha_honor')
    def _compute_fecha_honor(self) :
        self.year_honor = self.fecha_honor.year
        self.honor_year = str(self.fecha_honor.year)
        self.month_honor = nombreMes(self.fecha_honor.month)
        self.fecha_ini = self.fecha_honor.replace(day=1)
        self.fecha_fin = ultimoDiaMes(self.fecha_honor)

class HonorariosVisitadoras(models.Model) :
    _name = 'medicos.honorarios.visitadoras'
    _description = 'Honorarios mensuales de visitadoras'
    
    vis_id = fields.Many2one('hr.employee', string='Médico', ondelete='cascade', index=True)
    fecha_honor = fields.Date(string='Fecha del mes y año de cálculo de honorarios', default=datetime.date.today().replace(day=15))
    fecha_ini = fields.Date(string='Fecha de inicio del cálculo de honorarios', compute=lambda self: self._compute_fecha_honor())
    fecha_fin = fields.Date(string='Fecha de término del cálculo de honorarios', compute=lambda self: self._compute_fecha_honor())
    year_honor = fields.Integer(string='Año', compute=lambda self: self._compute_fecha_honor())
    honor_year = fields.Char(string='Año', compute=lambda self: self._compute_fecha_honor())
    month_honor = fields.Char(string='Mes', compute=lambda self: self._compute_fecha_honor())
    honor_mes = fields.Monetary(string='Monto de honorarios del mes', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=162)
    
    def actualizar(self) :
        fecha = datetime.datetime(self.fecha_honor.year,self.fecha_honor.month,self.fecha_fin.day,23,59,59)
        registros = self.env['medicos.honorarios'].search([('honor_vis_id','=',self.vis_id.id),
                                                           ('honor_fecha','<=',fecha),
                                                           ('honor_fecha','>=',fecha.replace(day=1,hour=0,minute=0,second=0))])
        self.honor_mes = sum(registros.mapped('honor_vis_monto'))
    
    @api.model
    def _default_fecha_honor(self) :
        return datetime.date.today().replace(day=15)
    
    @api.one
    @api.depends('fecha_honor')
    def _compute_fecha_honor(self) :
        self.year_honor = self.fecha_honor.year
        self.honor_year = str(self.fecha_honor.year)
        self.month_honor = nombreMes(self.fecha_honor.month)
        self.fecha_ini = self.fecha_honor.replace(day=1)
        self.fecha_fin = ultimoDiaMes(self.fecha_honor)
