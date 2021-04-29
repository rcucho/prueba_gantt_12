# -*- coding: utf-8 -*-

from odoo import fields, models, api, _ , tools
from openerp.exceptions import Warning
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import random
import base64
from datetime import datetime, timedelta,date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT


class GanttView(models.Model):
	_inherit = 'calendar.event'

	def get_gantt_data(self):
		min_date_start = []
		max_date_stop = []
		all_date_filtereds = []
		all_dates = []

		today = datetime.now() 
		event_ids = self.env['calendar.event'].search([])
		for event in event_ids.filtered(lambda event: event.start > today):
			all_dates = []
			actualStart = ''
			actualEnd = ''
			if event.start:
				actualStart = event.start.strftime("%Y-%m-%d")
				all_dates.append(actualStart)

			if event.stop:
				actualEnd = event.stop.strftime("%Y-%m-%d")
				all_dates.append(actualEnd)

			if actualStart and actualEnd :
				all_date_filtereds.append({
					'id': event.id,
					'name': event.name,
					'actualStart': min(all_dates),
					'actualEnd'  : max(all_dates),
				})
		print("waaaaaaa",all_date_filtereds)
		return all_date_filtereds
