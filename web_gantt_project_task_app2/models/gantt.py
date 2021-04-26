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
		for event in event_ids:
			children = []
			all_dates = []
			for event_fil in event.id.filtered(lambda event_fil: event_fil.start > datetime.datetime.now()):
				actualStart = ''
				actualEnd = ''
				if event_fil.start:
					actualStart = event_fil.start.strftime("%Y-%m-%d")
					all_dates.append(actualStart)

				if event_fil.stop:
					#child_date_stop = datetime.strptime(event_fill.stop.strftime("%Y-%m-%d"),  "%Y-%m-%d").date()
					#final_date_deadline = child_date_deadline + timedelta(days=1)
					actualEnd = event_fil.stop.strftime("%Y-%m-%d")
					all_dates.append(actualEnd)

				if actualStart and actualEnd :
					children.append({
						'id': event_fil.id,
						'name': event_fil.name,
						'actualStart': actualStart,
						'actualEnd': actualEnd,
					})
			if children :
				all_date_filtereds.append({
					'id': event.id,
					'name': event.name,
					'actualStart': min(all_dates),
					'actualEnd'  : max(all_dates),
					'children': children
				})
		print("njjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj",all_date_filtereds)
		return all_date_filtereds
