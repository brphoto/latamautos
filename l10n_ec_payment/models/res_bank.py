# -*- coding: utf-8 -*-
from odoo import models, fields


class ResBank(models.Model):
    _inherit = "res.bank"

    credit_card_issuer = fields.Boolean(
        '¿Is a credit card emisor?',
        help="Seleccionar si la institución financiera emite tarjetas de crédito", )

