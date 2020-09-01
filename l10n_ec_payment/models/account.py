# -*- coding: utf-8 -*-
####################################################
# Parte del Proyecto LibreGOB: http://libregob.org #
# Licencia AGPL-v3                                 #
####################################################

from odoo import models, fields, api

class AccountAccount(models.Model):
    _inherit = 'account.account'

    advance = fields.Boolean(
        string='Is account for advance payments?',
    )

