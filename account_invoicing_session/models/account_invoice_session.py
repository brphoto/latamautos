# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, exceptions, _

import logging
_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    invoicing_session_ids = fields.Many2many(
        'account.invoicing.session',
        'invoice_session_rel',
        'invoicing_session_ids',
        'invoice_ids',
        string="Session",
    )

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            session = self.env['account.invoicing.session']
            session = session.search(
                [
                    ('user_id', '=', self.env.user.id),
                    ('state', '=', 'opened'),
                    ('journal_id', '=', self.journal_id.id)
                ]
            )
            if session:
                self.invoicing_session_ids = session[0]
            else:
                self.invoicing_session_ids = session
                journal = self.journal_id
                if journal.require_invoicing_session and len(session) == 0:
                    journal_type = journal.type
                    if journal_type == 'purchase':
                        action = self.env.ref(
                            'account_invoicing_session.purchase_list_action')
                        raise exceptions.RedirectWarning(
                            _(
                                'At least one purchase session should be open for this user.'
                            ), action.id, _('Go to the sessions menu'))
                    if journal_type == 'sale':
                        action = self.env.ref(
                            'account_invoicing_session.sale_list_action'
                        )
                        raise exceptions.RedirectWarning(_(
                            'At least one sale session should be open for this user.'
                        ), action.id, _('Go to the sessions menu'))

    @api.multi
    @api.constrains('invoicing_session_ids')
    def _check_invoicing_session_ids(self):
        for r in self:
            if len(r.invoicing_session_ids) > 1:
                raise exceptions.ValidationError(
                    _(
                        "The invoice should belong to only "
                        "one invoicing session"
                    )
                )

    @api.multi
    def invoice_validate(self):
        for invoice in self:
            res = super(AccountInvoice, invoice).invoice_validate()
            session = invoice.invoicing_session_ids and invoice.invoicing_session_ids[0]
            cash_journal = session.cash_journal_id
            automatic_payment = session.automatic_payment
            if session and cash_journal and automatic_payment:
                lines = False
                payment = self.env['account.payment'].search(
                    [
                        ('partner_id','=', self.partner_id.id),
                        ('communication','=',self.number)
                    ]
                )
                if payment:
                    lines = payment.mapped('move_line_ids').filtered(lambda x: x.account_id == self.account_id)

                if lines:
                    for line in lines:
                        invoice.register_payment(
                            line,
                            writeoff_acc_id=False,
                            writeoff_journal_id=False
                        )
                else:
                    invoice.pay_and_reconcile(
                        cash_journal,
                        pay_amount=self.residual,
                        date=self.date,
                        writeoff_acc=None
                    )
                    payments = invoice.payment_move_line_ids.mapped('payment_id')
                    session.payment_ids += payments
            return res


class AccountInvoicingSession(models.Model):
    _name = 'account.invoicing.session'

    invoice_amount = fields.Float(string='Invoice amount', compute='compute_amounts', )
    refund_amount = fields.Float(string='Refund amount', compute='compute_amounts', )
    session_amount = fields.Float(string='Session amount', compute='compute_amounts', )

    name = fields.Char('Name', required=True, copy=False, )
    communication = fields.Char('Communication', )
    date_from = fields.Datetime('Date from', default=fields.Datetime.now(),)
    date_to = fields.Datetime('Date to', )

    state = fields.Selection([
        ('new', 'New'),
        ('opened', 'In progress'),
        ('closed', 'Closed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='new')

    journal_id = fields.Many2one(
        'account.journal', string='Journal',
        domain=[('type', 'in', ('sale','purchase'))],
        required=True, )

    cash_journal_id = fields.Many2one(
        'account.journal', string='Cash journal',
        domain=[('type', '=', 'cash')],
    )

    automatic_payment = fields.Boolean(string='Automatic payment', )

    user_id = fields.Many2one(
        'res.users', string='User',
        default=lambda self: self.env.user,
        readonly=False, )
    invoice_ids = fields.Many2many(
        'account.invoice', 'invoice_session_rel', 'invoice_ids',
        'invoicing_session_ids', string="Invoices", )

    # *************   RELATED FIELDS ******************************************************

    type = fields.Selection(string='Type',
                            store=True,
                            related='journal_id.type',
                            readonly=True, )

    payment_ids = fields.Many2many(
        'account.payment', 'payment_session_rel', 'payment_ids',
        'invoicing_session_ids', string="Payments", )

    summary_ids = fields.One2many(
        'account.payment.summary', inverse_name='invoicing_session_id',
        ondelete='restrict', string="Payment sumary", )

    # ***************************************************************************************

    @api.multi
    def button_session_opened(self):
        for s in self:
            s.state = 'opened'

    @api.multi
    def button_session_closed(self):
        for s in self:
            s.state = 'closed'
            s.get_account_payment_summary()
            s.date_to = fields.Datetime.now()

    @api.multi
    def button_session_cancelled(self):
        for s in self:
            s.state = 'cancelled'
            s.invoice_ids = False

    @api.multi
    def button_session_new(self):
        for s in self:
            s.state = 'new'

    @api.multi
    def button_session_done(self):
        for s in self:
            s.state = 'done'
            s.get_account_payment_summary()

    @api.onchange('journal_id')
    def _onchange_journal_id(self):
        if self.journal_id:
            if not self.journal_id.invoicing_session_sequence_id:
                raise exceptions.UserError(_('There is no sequence configured for this journal. Add a session name manually'))
            self.name = self.journal_id.invoicing_session_sequence_id._next()

    @api.multi
    def button_get_session_payments(self):
        for s in self:
            invoices = s.invoice_ids
            payments = invoices.mapped('payment_ids')
            s.payment_ids += payments

    @api.multi
    def get_account_payment_summary(self):
        for s in self:
            s.summary_ids.unlink()
            summaries = {}
            for p in s.payment_ids:

                inbound = 0.0
                outbound = 0.0
                if p.payment_type == 'inbound':
                    inbound = p.amount
                elif p.payment_type in ('outbound','transfer'):
                    outbound = p.amount

                j_val = {
                    'invoicing_session_id': s.id,
                    'journal_id': p.journal_id.id,
                    'outbound': outbound,
                    'inbound': inbound,
                }

                key = str(p.journal_id.id)

                if key not in summaries:
                    summaries[key] = j_val
                else:
                    summaries[key]['inbound'] += j_val['inbound']
                    summaries[key]['outbound'] += j_val['outbound']

                if p.payment_type == 'transfer':
                    key = str(p.destination_journal_id.id)

                    d_val = {
                        'invoicing_session_id': s.id,
                        'journal_id': p.destination_journal_id.id,
                        'outbound': 0.0,
                        'inbound': p.amount,
                    }

                    if key not in summaries:
                        summaries[key] = d_val
                    else:
                        summaries[key]['inbound'] += d_val['inbound']

            for summary in summaries.values():
                _logger.info('summary ', summary)
                self.env['account.payment.summary'].create(summary)

    @api.multi
    def compute_amounts(self):
        for s in self:
            invoices = s.invoice_ids.filtered(lambda x: x.state in ('open','paid'))
            inv = invoices.filtered(lambda x: 'invoice' in x.type)
            ref = invoices.filtered(lambda x: 'refund' in x.type)

            invoice_amount = sum(i.total for i in inv)
            refund_amount = sum(r.total for r in ref)

            # Valores no declarados
            no_declarado_invoice = sum(i.no_declarado for i in inv)
            no_declarado_refund = sum(r.no_declarado for r in ref)

            s.invoice_amount = invoice_amount + no_declarado_invoice
            s.refund_amount = refund_amount + no_declarado_refund
            s.session_amount = invoice_amount + no_declarado_invoice - refund_amount - no_declarado_refund

    @api.multi
    @api.onchange('cash_journal_id')
    def _onchange_cash_journal_id(self):
        for r in self:
            if r.cash_journal_id:
                r.automatic_payment = True

    @api.constrains('cash_journal_id', 'automatic_payment')
    def _check_automatic_payment(self):
        if not self.cash_journal_id and self.automatic_payment:
            raise exceptions.UserError(
                _(
                    "You need a cash journal in order "
                    "to generate automatic payments."
                )
            )

    @api.multi
    def pay_and_reconcile(self):
        for r in self:
            for inv in self.invoice_ids:
                if inv.state == 'open':
                    inv.pay_and_reconcile(
                        r.cash_journal_id,
                        pay_amount=inv.residual,
                        date=inv.date,
                        writeoff_acc=None
                    )
                payments = inv.payment_move_line_ids.mapped('payment_id')
                r.payment_ids += payments

