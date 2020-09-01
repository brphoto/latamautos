# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import _, api, exceptions, fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def _default_invoicing_session_ids(self):
        if self._context.get('active_model') == 'account.invoice':
            invoices = self.env['account.invoice'].browse(
                self._context.get('active_ids'))
            if invoices:
                res = self.env['account.invoicing.session']
                for inv in invoices:
                    if inv.invoicing_session_ids:
                        res += inv.invoicing_session_ids
                if len(res) == 1:
                    return res

    invoicing_session_ids = fields.Many2many(
        'account.invoicing.session', 'payment_session_rel', 'invoicing_session_ids',
        'payment_ids', string="Session", default=_default_invoicing_session_ids,)

    @api.multi
    @api.constrains('invoicing_session_ids')
    def _check_invoicing_session_ids(self):
        for r in self:
            if len(r.invoicing_session_ids) > 1:
                raise exceptions.ValidationError(
                    _('The payment should belong to only one invoicing session'))


class AccountPaymentSummary(models.Model):
    _name = 'account.payment.summary'

    invoicing_session_id = fields.Many2one(
        'account.invoicing.session', string='Session', )
    journal_id = fields.Many2one(
        'account.journal', string='Journal', )
    inbound = fields.Float('Inbound', digits=(9, 2), )
    outbound = fields.Float('Outbound', digits=(9, 2), )

    balance = fields.Float(
        'Balance', compute='_compute_balance', digits=(9, 2), )

    @api.multi
    @api.depends('inbound', 'outbound')
    def _compute_balance(self):
        for r in self:
            r.balance = r.inbound - r.outbound
