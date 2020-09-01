# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    session_format_id = fields.Many2one('report.custom.format', string='Formato de reporte de sesión', )
