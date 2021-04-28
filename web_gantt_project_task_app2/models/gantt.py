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

		event_ids = self.env['calendar.event'].search([])
		for event in event_ids.filtered(lambda event_fil: event_fil.start > datetime.datetime.now()):
			all_dates = []
			actualStart = ''
			actualEnd = ''
			if event_fil.start:
				actualStart = event_fil.start.strftime("%Y-%m-%d")
				all_dates.append(actualStart)

			if event_fil.stop:
				actualEnd = event_fil.stop.strftime("%Y-%m-%d")
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
