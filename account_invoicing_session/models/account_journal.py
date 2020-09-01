# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    invoicing_session_sequence_id = fields.Many2one('ir.sequence', string='Session Sequence',
        help="This field contains the information related to the numbering of the invoicing sessions of this journal.",
        copy=False)

    require_invoicing_session = fields.Boolean('Require invoicing Session?', )
