#!/usr/bin/env python
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    @api.multi
    def name_get(self):
        reads = self.read(['name', 'department_id'])
        res = []
        for record in reads:
            name = record['name']
            if record['department_id']:
                name = str(record['department_id'][1]) + ' / ' + name
            res.append((record['id'], name))
        return res

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string=_('Analytic Account'))

