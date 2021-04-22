# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, Warning
#from odoo.tools.misc import format_date, format_datetime
from odoo.tools.misc import format_date
import datetime
import pytz

DEFAULT_TIMEZONE = 'America/Lima'

#def local_datetime(untimed_datetime, timezone) :
#    return untimed_datetime.astimezone(pytz.timezone(timezone))

class PlannerProfessional(models.Model) :
    _name = 'planner.professional'
    _description = 'Sala'
    _rec_name = 'sala_id'
    
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Empleado')
    sala_id = fields.Many2one(comodel_name='x_sala', string='Sala')
    modalidad_id = fields.Many2one(comodel_name='x_modalidad', string='Modalidad')
    procedure_ids = fields.Many2many(comodel_name='product.product', string='Procedimientos', domain="[('type','=','consu'),('x_studio_modalidad','=',modalidad_id)]")

    _sql_constraints = [('unique_sala_id', 'unique(sala_id)', 'Solo puede existir una sala.')]

class PlannerSpot(models.Model) :
    _name = 'planner.spot'
    _description = 'Cupo'
    _order = 'professional_id asc, start asc, end asc'
    
    def _get_default_timezone(self) :
        #datetime.datetime.now(pytz.timezone('America/Lima')).utcoffset()
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Agenda', readonly=True, copy=False, default='/')
    active = fields.Boolean(string='Activo', default=True)
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Sala')
    date = fields.Date(string='Fecha', required=True)
    start = fields.Datetime(string='Inicio', required=True)
    end = fields.Datetime(string='Fin', required=True)
    spots = fields.Integer(string='Cupos', default=1, required=True)
    planner_ids = fields.Many2many(comodel_name='planner.planner', relation='planner_spot_planner_planner_table_1', column1='spot_id', column2='planner_id', string='Agendas', domain=[('state','!=','cancel')])
    available_spots = fields.Integer(string='Cupos Disponibles', compute='_compute_available_spots', store=True)
    
    @api.depends('spots', 'planner_ids')
    def _compute_available_spots(self) :
        for record in self :
            spots = record.spots - len(record.planner_ids)
            if spots >= 0 :
                record.available_spots = spots
    
    @api.depends('professional_id', 'date', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        for spot in self :
            name = '/'
            if spot.professional_id and spot.date and spot.start and spot.end :
                name = (spot.professional_id.display_name,
                        #format_date(self.env, spot.date, date_format='dd/MM/Y'),
                        spot.date.strftime('%d/%m/%Y'),
                        #format_datetime(self.env, spot.start, date_format='HH:mm:ss'),
                        #format_datetime(self.env, spot.end, date_format='HH:mm:ss'),
                        (spot.start + current_offset).strftime('%H:%M:%S'),
                        (spot.end + current_offset).strftime('%H:%M:%S'),
                       )
                name = ('%s: %s %s - %s') % name
            result.append((spot.id, name))
        return result

class PlannerProfessionalAvailability(models.Model) :
    _name = 'planner.professional.availability'
    _description = 'Disponibilidad'
    _order = 'professional_id asc, day asc'
    
    def _get_default_timezone(self) :
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Disponibilidad', readonly=True, copy=False, default='/')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Profesional', required=True)
    day = fields.Selection(selection=[('1','Lunes'),('2','Martes'),('3','Miércoles'),('4','Jueves'),('5','Viernes'),('6','Sábado'),('7','Domingo')],
                           string='Día', default='1', required=True)
    start = fields.Float(string='Inicio', default=8)
    end = fields.Float(string='Fin', default=18)
    duration = fields.Float(string='Duración', default=0.25, required=True)
    spots = fields.Integer(string='Cupos', default=1, required=True)
    
    @api.depends('professional_id', 'day', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        for avail in self :
            name = '/'
            if avail.professional_id and avail.day :
                start = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
                end = start + datetime.timedelta(hours=avail.end) - current_offset
                start = start + datetime.timedelta(hours=avail.start) - current_offset
                name = (avail.professional_id.display_name,
                        dict(self._fields['day'].selection)[avail.day],
                        #format_date(self.env, start, date_format='HH:mm'),
                        #format_date(self.env, end, date_format='HH:mm'),
                        (start + current_offset).strftime('%H:%M'),
                        (end + current_offset).strftime('%H:%M'),
                       )
                name = ('%s: %s %s - %s') % name
            result.append((avail.id, name))
        return result
    
    @api.multi
    def spot_creation(self, availability_record=False) :
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        aware_now = fields.Datetime.now().astimezone(pytz.timezone(current_tz))
        #aware_today = aware_now.date()
        spot = self.env['planner.spot'].sudo()
        for record in (availability_record or self.sudo().search([('day','=',str(aware_now.date().isoweekday()))])) :
            duration = record.duration
            duration_offset = datetime.timedelta(hours=duration)
            spots = record.spots
            aware_today = aware_now.date() + datetime.timedelta(days=int(record.day)-aware_now.date().isoweekday())
            for i in range(5) :
                actual = aware_today + datetime.timedelta(weeks=i)
                if actual >= aware_now.date() :
                    #spot_ids = spot.search([('professional_id','=',record.professional_id.id), ('date','=',str(actual))])
                    #if not spot_ids :
                    start = record.start
                    end = record.end
                    unaware_starts = []
                    while start < end :
                        unaware_start = datetime.datetime.combine(actual, datetime.datetime.min.time())
                        unaware_start = unaware_start + datetime.timedelta(hours=start) - current_offset
                        unaware_starts.append(unaware_start)
                        start = start + duration
                        if start > end :
                            record.end = start
                    for unaware_start in unaware_starts :
                        spot_ids = spot.search([('professional_id','=',record.professional_id.id), ('start','=',str(unaware_start)), ('end','<=',str(unaware_start+duration_offset))])
                        if not spot_ids :
                            spot.create({'professional_id': record.professional_id.id,
                                         'date': str(actual),
                                         'start': str(unaware_start),
                                         'end': str(unaware_start + duration_offset),
                                         'spots': spots})
                        else :
                            for spot_id in spot_ids :
                                if spot_id.available_spots >= spot_id.spots - spots :
                                    spot_id.spots = spots
    
    @api.model
    def create(self, values) :
        res = super(PlannerProfessionalAvailability, self).create(values)
        self.spot_creation(availability_record=res)
        return res
    
    @api.multi
    def write(self, values) :
        res = super(PlannerProfessionalAvailability, self).write(values)
        if values.get('spots') :
            spot = self.env['planner.spot'].sudo()
            for record in self :
                for spot_id in spot.search([('professional_id','=',record.professional_id.id)]) :
                    if spot_id.date.isoweekday() == int(record.day) and spot_id.available_spot >= spot_id.spots - values['spots'] :
                        spot_id.spots = values['spots']
    
    _sql_constraints = [('unique_professional_day', 'unique(professional_id, day)', 'Solo puede existir una disponibilidad para este profesional en este dia.')]

class SaleOrder(models.Model) :
    _inherit = 'sale.order'
    
    planner_ids = fields.One2many(comodel_name='planner.planner', inverse_name='sale_id', string='Agendas')

class PlannerPlanner(models.Model) :
    _name = 'planner.planner'
    _description = 'Agenda'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'patient_id asc, professional_id asc, start asc, end asc'
    
    def _get_default_timezone(self) :
        return DEFAULT_TIMEZONE
    
    name = fields.Char(string='Agenda', readonly=True, copy=False, default='/')
    state = fields.Selection(string='Estado', required=True, readonly=True, copy=False, tracking=True, default='planned',
                             selection=[('planned','Agendado'),('received','Recepcionado'),('attended','Atendido'),('cancel','Cancelado')], track_visibility='always')
    received = fields.Boolean(string='Recepcionado', compute='_compute_state', store=True, readonly=False)
    attended = fields.Boolean(string='Atendido', compute='_compute_state', store=True)
    aseguradora_id = fields.Many2one(comodel_name='res.partner', string='Aseguradora', tracking=True)
    plan_id = fields.Many2one(comodel_name='x_planes', string='Plan')
    patient_id = fields.Many2one(comodel_name='res.partner', string='Paciente', tracking=True, track_visibility='always')
    professional_id = fields.Many2one(comodel_name='planner.professional', string='Sala')
    radiologo_id = fields.Many2one(comodel_name='res.partner', string='Radiólogo')
    medico_referente_id = fields.Many2one(comodel_name='res.partner', string='Médico Referente')
    visitadora_id = fields.Many2one(comodel_name='hr.employee', string='Visitadora', related='medico_referente_id.vis_id')
    procedure_ids = fields.Many2many(comodel_name='product.product', relation='planner_procedure_ids', string='Procedimientos', compute='_compute_professional_id', store=True)
    sala_id = fields.Many2one(comodel_name='x_sala', string='Sala')
    line_ids = fields.One2many(comodel_name='planner.planner.line', inverse_name='planner_id', string='Líneas de Procedimiento')
    spot_id = fields.Many2one(comodel_name='planner.spot', string='Cupo', domain=[('available_spots','>',0)], tracking=True)
    spot_ids = fields.Many2many(comodel_name='planner.spot', relation='planner_spot_planner_planner_table_1', column1='planner_id', column2='spot_id', string='Cupos')
    date = fields.Date(string='Fecha', compute='_compute_date', store=True, readonly=False)
    start = fields.Datetime(string='Inicio', compute='_compute_spot_id', store=True, readonly=False)
    end = fields.Datetime(string='Fin', compute='_compute_spot_id', store=True, readonly=False)
    duracion = fields.Float(string='Duración', compute='_compute_duracion', store=True, readonly=True)
    sale_id = fields.Many2one(comodel_name='sale.order', string='Pedido de Venta', tracking=True, track_visibility='always')
    
    @api.multi
    def create_sale_order(self) :
        to_order = self.filtered(lambda r: r.id and (not r.sale_id) and r.patient_id and r.line_ids.ids)
        patients = to_order.mapped('patient_id')
        for patient in patients :
            records = to_order.filtered(lambda r: r.patient_id == patient)
            for record in records :
                sale_order = {
                    'partner_id': record.aseguradora_id.id,
                    'x_studio_field_r8GaD': record.plan_id.id,
                    'partner_invoice_id': patient.id,
                    'x_studio_agenda': record.start,
                    'x_studio_duracin_total': record.duracion, #(record.end - record.start).seconds/3600.0,
                    'x_studio_sala': record.sala_id.id,
                    'x_studio_radilogo': record.radiologo_id.id,
                    'x_studio_medico_referente': record.medico_referente_id.id,
                }
                sale_order = self.env['sale.order'].sudo().create(sale_order)
                sale_order.write({'user_id': self.env.uid})
                record.write({'sale_id': sale_order.id})
                for line in record.line_ids :
                    sale_order.write({'order_line': [(0,0,{'product_id': line.product_id.id,'x_studio_tiempo':line.duracion,'price_unit':line.precio})]})
                    sale_order_line = sale_order.order_line.filtered(lambda r: not r.planner_line_id)[0]
                    line.write({'sale_line_id': sale_order_line.id})
                    sale_order_line.write({'planner_line_id': line.id})
    
    @api.multi
    def receive_patient(self) :
        #self.filtered(lambda r: r.state=='planned').write({'state': 'received'})
        for record in self.filtered(lambda r: r.state=='planned' and (not r.sale_id) and r.patient_id and r.line_ids.ids) :
            record.state = 'received'
            record.create_sale_order()
            record.sale_id.action_confirm()
            spots = record.spot_id
            if record.duracion > (record.spot_id.end - record.spot_id.start).seconds//3600.0 :
                fecha = record.spot_id.start + datetime.timedelta(hours=record.duracion)
                for spot in self.env['planner.spot'].sudo().search([('professional_id','=',record.spot_id.professional_id.id),('date','=',str(record.spot_id.date)),('start','>=',str(record.spot_id.start)),('start','<',str(fecha)),('id','!=',record.spot_id.id)]) :
                    if spot.available_spots > 0 :
                        spots |= spot
            record.spot_ids = spots
    
    @api.multi
    def mark_attended(self) :
        #self.filtered(lambda r: r.state=='received').write({'state': 'attended'})
        for record in self.filtered(lambda r: r.state=='received') :
            record.state = 'attended'
    
    @api.multi
    def mark_cancel(self) :
        #self.filtered(lambda r: r.state not in ['attended','cancel']).write({'state': 'cancel'})
        for record in self.filtered(lambda r: r.state not in ['attended','cancel']) :
            record.state = 'cancel'
            record.spot_ids = False
            if record.sale_id :
                try :
                    record.sale_id.action_cancel()
                except :
                    pass
                for mrp in self.env['mrp.production'].sudo().search([('x_studio_origen','=',record.sale_id.id)]) :
                    try :
                        mrp.action_cancel()
                    except :
                        pass
    
    @api.multi
    def unlink(self) :
        res = True
        if self.env.context.get('force_unlink') :
            res = super(PlannerPlanner, self).unlink()
        else :
            attended = self.filtered(lambda r: r.attended)
            attended.mark_cancel()
            res = super(PlannerPlanner, self - attended).unlink()
        return res
    
    @api.multi
    def write(self, values) :
        res = super(PlannerPlanner, self).write(values)
        if values.get('received') :
            planned = self.filtered(lambda r: r.state=='planned')
            if planned :
                planned.receive_patient()
        return res
    
    @api.depends('state')
    def _compute_state(self) :
        #self.filtered(lambda r: r.state == 'received' and not r.received).write({'received': True})
        #self.filtered(lambda r: r.state == 'attended' and not r.attended).write({'attended': True})
        #self.filtered(lambda r: r.state not in ['received','attended'] and r.received).write({'received': False})
        #self.filtered(lambda r: r.state not in ['received','attended'] and r.attended).write({'attended': False})
        ##self.filtered(lambda r: r.received).create_sale_order() #only created through button or through action
        for record in self :
            if record.state == 'received' :
                if not record.received :
                    record.received = True
            elif record.state == 'attended' :
                if not record.attended :
                    record.attended = True
            elif record.state == 'planned' :
                record.attended = False
                record.received = False
            else :
                record.attended=True
                #if record.received :
                #    record.received = False
                #if record.attended :
                #    record.attended = False
    
    @api.depends('line_ids.duracion','spot_id')
    def _compute_duracion(self) :
        for record in self :
            if record.line_ids.ids :
                duracion = sum([line.duracion for line in record.line_ids])
                record.duracion = duracion
                if record.start :
                    record.end = record.start + datetime.timedelta(hours=duracion)
                elif record.spot_id :
                    record.end = record.spot_id.start + datetime.timedelta(hours=duracion)
            else :
                if record.spot_id :
                    record.start = record.spot_id.start
                    record.end = record.spot_id.end
                if record.start and record.end :
                    record.duracion = (record.end - record.start).seconds/3600.0
    
    @api.depends('spot_id')
    def _compute_spot_id(self) :
        for record in self :
            if record.spot_id :
                #record.date = record.spot_id.date
                record.start = record.spot_id.start
                record.end = record.spot_id.end
    
    @api.depends('start')
    def _compute_date(self) :
        current_tz = self.env.user.tz or self._get_default_timezone()
        for record in self :
            if record.start :
                record.date = record.start.astimezone(pytz.timezone(current_tz)).date()
    
    @api.depends('professional_id','plan_id')
    def _compute_professional_id(self) :
        for record in self :
            record.procedure_ids = (record.professional_id.procedure_ids & record.plan_id.mapped('x_producto_plan.x_product_id'))
    
    @api.onchange('sala_id')
    def _onchange_sala_id(self) :
        if self.line_ids.ids and ((not self.sala_id) or (self.sala_id not in self.line_ids.mapped('product_id.x_studio_field_16Qws'))) :
            self.line_ids = [(5,0,0)]
    
    @api.onchange('professional_id')
    def _onchange_professional_id(self) :
        if not self.professional_id :
            if self.spot_id :
                self.spot_id = False
            #if not self.radiologo_id :
                #self.radiologo_id = self.professional_id.employee_id.address_home_id
        self.sala_id = self.professional_id.sala_id
    
    @api.depends('patient_id', 'professional_id', 'date', 'start', 'end')
    def name_get(self) :
        result = []
        current_tz = self.env.user.tz or self._get_default_timezone()
        current_offset = datetime.datetime.now(pytz.timezone(current_tz)).utcoffset()
        for planner in self :
            name = '/'
            if planner.patient_id and planner.professional_id and planner.date and planner.start and planner.end :
                #local_start = local_datetime(planner.start, current_tz)
                #local_end = local_datetime(planner.end, current_tz)
                name = (planner.patient_id.name,
                        planner.professional_id.display_name,
                        ','.join(planner.line_ids.mapped('product_id.name')),
                        #format_date(self.env, planner.date, date_format='dd/MM/Y'),
                        planner.date.strftime('%d/%m/%Y'),
                        #format_date(self.env, planner.start, date_format='HH:mm:ss'),
                        #format_date(self.env, planner.end, date_format='HH:mm:ss'),
                        (planner.start + current_offset).strftime('%H:%M:%S'),
                        (planner.end + current_offset).strftime('%H:%M:%S'),
                       )
                name = _('Cita de %s con %s para %s el %s de %s a %s') % name
            result.append((planner.id, name))
        return result

class PlannerPlannerLine(models.Model) :
    _name = 'planner.planner.line'
    _description = 'Línea de Agenda'
    
    planner_id = fields.Many2one(comodel_name='planner.planner', string='Agenda')
    sale_line_id = fields.Many2one(comodel_name='sale.order.line', string='Línea de Pedido de Venta')
    product_ids = fields.Many2many(comodel_name='product.product', string='Exámenes')
    product_id = fields.Many2one(comodel_name='product.product', string='Examen')
    modalidad_id = fields.Many2one(comodel_name='x_modalidad', string='Modalidad', related='product_id.x_studio_modalidad')
    duracion = fields.Float(string='Duración', compute='_compute_product_id', store=True, readonly=False)
    precio = fields.Float(string='Precio', compute='_compute_product_id', store=True, readonly=False)
    
    @api.depends('product_id')
    def _compute_product_id(self) :
        for record in self :
            record.duracion = record.product_id.x_studio_duracin
            record.precio = record.product_id.lst_price

class SaleOrderLine(models.Model) :
    _inherit = 'sale.order.line'
    
    planner_line_id = fields.Many2one(comodel_name='planner.planner.line', string='Línea de Agenda')

