# -*- coding: utf-8 -*-
import json
import time

from odoo import _, api, fields, models
from odoo.tools import float_is_zero, float_compare


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    """
            if invoice.type == 'out_invoice':
                # Check to get invoice residual or aml
                aml_amount = abs(credit_aml.amount_residual) or credit_aml.credit
                if invoice.residual > aml_amount:
                    total_amount = aml_amount
                else:
                    total_amount = invoice.residual
                move = self.pool.get('account.move').create(cr, uid, {
                    'name': 'Prepago de %s' % (invoice.number),
                    'date': time.strftime('%Y-%m-%d'),
                    'ref': '',
                    'company_id': invoice.company_id.id,
                    'journal_id': credit_aml.payment_id.journal_id.id,
                    'partner_id': credit_aml.payment_id.partner_id.id,
                })
                debit_line = move_line_obj.create(cr, uid, {
                    'name': 'Prepago de %s' % (invoice.number),
                    'partner_id': credit_aml.payment_id.partner_id.id,
                    'move_id': move,
                    'debit': total_amount,
                    'credit': 0,
                    'account_id': credit_aml.account_id.id,
                    'payment_id': credit_aml.payment_id.id,
                }, context=context)
                credit_line = move_line_obj.create(cr, uid, {
                    'name': 'Prepago de %s' % (invoice.number),
                    'partner_id': credit_aml.payment_id.partner_id.id,
                    'move_id': move,
                    'credit': total_amount,
                    'debit': 0,
                    'account_id': invoice.account_id.id,
                    'payment_id': credit_aml.payment_id.id,
                }, context=context)
                # Reconcile the prepayment then the invoice
                move_line_obj.reconcile(cr, uid, [debit_line, credit_aml.id])
                # Post the entries
                self.pool.get('account.move').post(cr, uid, move)
                return self.browse(cr, uid, id, context=context).register_payment(move_line_obj.browse(cr, uid, credit_line))
            elif invoice.type == 'in_invoice':
                aml_amount = abs(credit_aml.amount_residual) or credit_aml.debit
                if invoice.residual > aml_amount:
                    total_amount = aml_amount
                else:
                    total_amount = invoice.residual
                move = self.pool.get('account.move').create(cr, uid, {
                    'name': 'Prepayment',
                    'date': time.strftime('%Y-%m-%d'),
                    'ref': '',
                    'company_id': invoice.company_id.id,
                    'journal_id': credit_aml.payment_id.journal_id.id,
                    'partner_id': credit_aml.payment_id.partner_id.id,
                })
                credit_line = move_line_obj.create(cr, uid, {
                    'name': 'Prepago de %s' % (invoice.number),
                    'partner_id': credit_aml.payment_id.partner_id.id,
                    'move_id': move,
                    'credit': total_amount,
                    'debit': 0,
                    'account_id': credit_aml.account_id.id,
                    'payment_id': credit_aml.payment_id.id,
                }, context=context)
                debit_line = move_line_obj.create(cr, uid, {
                    'name': 'Prepago de %s' % (invoice.number),
                    'partner_id': credit_aml.payment_id.partner_id.id,
                    'move_id': move,
                    'debit': total_amount,
                    'credit': 0,
                    'account_id': invoice.account_id.id,
                    'payment_id': credit_aml.payment_id.id,
                }, context=context)
                # Reconcile the prepayment then the invoice
                move_line_obj.reconcile(cr, uid, [credit_line, credit_aml.id])
                # Post the entries
                self.pool.get('account.move').post(cr, uid, move)
                return self.browse(cr, uid, id, context=context).register_payment(move_line_obj.browse(cr, uid, debit_line))

        else:
            return self.browse(cr, uid, id, context=context).register_payment(credit_aml)
    """
    """
    @api.multi
    def register_payment(self, payment_line, writeoff_acc_id=False, writeoff_journal_id=False):
        if not payment_line.account_id.advance:
            return super(AccountInvoice, self).register_payment(
                payment_line,
                writeoff_acc_id=writeoff_acc_id,
                writeoff_journal_id=writeoff_journal_id
            )
        else:
            # Si la cuenta es de prepagos, no hacemos nada
            pass
    """

    @api.v7
    def assign_outstanding_credit(self, cr, uid, id, credit_aml_id, context=None):
        """
        If the account of the aml is prepayment, we need to create another move
        to reconcile.
        """
        advance = self.pool.get('account.move.line').browse(
            cr, uid, credit_aml_id, context=context
        ).account_id.advance

        if not advance:
            return super(AccountInvoice, self).assign_outstanding_credit(
                cr,
                uid,
                id,
                credit_aml_id=credit_aml_id,
                context=context
            )
        else:
            vals = {'invoice': id, 'credit_aml': credit_aml_id}
            return self.assign_prepayment_move(cr, uid, vals)

    @api.model
    def assign_prepayment_move(self, vals):
        """
        This function must be called only when the account of the aml
        is prepayment, in order to generate the assignation move and
        reconcile the transactions.

        Here we don't do any validation, the function must be called
        only when this process should be executed.

        """
        invoice = self.env['account.invoice'].sudo().browse(vals['invoice'])
        credit_aml = self.env['account.move.line'].sudo().browse(vals['credit_aml'])
        invoice_account = invoice.account_id.id
        aml_account = credit_aml.account_id.id
        aml_amount = credit_aml.credit if invoice.type == 'out_invoice' else credit_aml.debit
        amount = invoice.residual if invoice.residual <= aml_amount else aml_amount

        move_line_obj = self.env['account.move.line']
        it = invoice.type

        journal = credit_aml.payment_id.journal_id

        name = journal.with_context(
            ir_sequence_date=fields.Date.today()).sequence_id.next_by_id()
        move = self.env['account.move'].create(
            {
                'name': name,
                'date': fields.Date.today(),
                'ref': credit_aml.move_id.name,
                'company_id': invoice.company_id.id,
                'journal_id': journal.id,
                'partner_id': credit_aml.payment_id.partner_id.id,
            }
        )
        payable_receivable_line = move_line_obj.with_context(
            check_move_validity=False).create(
            {
                'name': _('Prepayment assignation of %s') % (credit_aml.move_id.name),
                'partner_id': credit_aml.payment_id.partner_id.id,
                'move_id': move.id,
                'credit': amount if it == 'out_invoice' else 0,
                'debit': 0 if it == 'out_invoice' else amount,
                'account_id': invoice_account,
                'payment_id': credit_aml.payment_id.id,
            }
        )
        prepayment_line = move_line_obj.create(
            {
                'name': _('Prepayment assignation of %s') % (credit_aml.move_id.name),
                'partner_id': credit_aml.payment_id.partner_id.id,
                'move_id': move.id,
                'credit': 0 if it == 'out_invoice' else amount,
                'debit': amount if it == 'out_invoice' else 0,
                'account_id': aml_account,
                'payment_id': credit_aml.payment_id.id,
            }
        )
        move.post()
        # Reconciliamos los asientos de la cuenta de prepagos.
        (prepayment_line + credit_aml).reconcile()
        invoice.register_payment(
            payable_receivable_line,
            writeoff_acc_id=False,
            writeoff_journal_id=False
        )
        return True

    """
    @api.one
    def _get_outstanding_info_JSON(self):
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            # Allow add button to show on invoice during prepayment
            domain = [('journal_id.type', 'in', ('bank', 'cash')),
                      ('account_id.reconcile', '=', True),
                      ('partner_id', '=', self.env['res.partner']._find_accounting_partner(
                          self.partner_id).id),
                      ('reconciled', '=', False),
                      ('amount_residual', '!=', 0.0)]
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                type_payment = _('Outstanding credits')
            else:
                domain.extend([('credit', '=', 0), ('debit', '>', 0)])
                type_payment = _('Outstanding debits')
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            lines = self.env['account.move.line'].search(domain)
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    # get the outstanding residual value in its currency. We don't want to show it
                    # in the invoice currency since the exchange rate between the invoice date and
                    # the payment date might have changed.
                    if line.currency_id:
                        currency_id = line.currency_id
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        currency_id = line.company_id.currency_id
                        amount_to_show = abs(line.amount_residual)
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True
    """

    @api.one
    @api.depends('payment_move_line_ids.amount_residual')
    def _get_outstanding_info_JSON(self):
        super(AccountInvoice, self)._get_outstanding_info_JSON()
        if self.state != 'open':
            return True

        # Agregamos las líneas no conciliadas de prepagos.
        domain = [
            ('account_id.advance', '=', True),
            ('account_id.reconcile', '=', True),
            ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id),
            ('reconciled', '=', False),
            ('amount_residual', '!=', 0.0),
            ]
        if self.type in ('out_invoice', 'in_refund'):
            domain.extend([('credit', '>', 0), ('debit', '=', 0)])
            type_payment = _('Outstanding credits')
        else:
            domain.extend([('credit', '=', 0), ('debit', '>', 0)])
            type_payment = _('Outstanding debits')

        lines = self.env['account.move.line'].search(domain)
        if not lines:
            return True

        if self.outstanding_credits_debits_widget != u'false':
            info = json.loads(self.outstanding_credits_debits_widget)
        else:
            info = {
                'title': type_payment,
                'outstanding': True,
                'content': [],
                'invoice_id': self.id
            }

        currency_id = self.currency_id
        for line in lines:
            if line.currency_id and line.currency_id == self.currency_id:
                amount_to_show = abs(line.amount_residual_currency)
            else:
                amount_to_show = line.company_id.currency_id.with_context(
                    date=line.date).compute(
                        abs(line.amount_residual),
                        self.currency_id
                    )
            if float_is_zero(
                amount_to_show,
                precision_rounding=self.currency_id.rounding
            ):
                continue

            info['content'].append(
                {
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount_to_show,
                    'currency': currency_id.symbol,
                    'id': line.id,
                    'position': currency_id.position,
                    'digits': [69, self.currency_id.decimal_places],
                }
            )
        self.outstanding_credits_debits_widget = json.dumps(info)
        self.has_outstanding = True

    @api.multi
    def button_supplier_payments(self):
        context = {'tree_view_ref': 'account.view_account_supplier_payment_tree'}
        return {
            'name': _('PAGOS'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', [x.id for x in self.payment_ids])],
            'context': context,
        }

    @api.multi
    def button_customer_payments(self):
        context = {'tree_view_ref': 'account.view_account_payment_tree'}
        return {
            'name': _('COBROS'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', [x.id for x in self.payment_ids])],
            'context': context,
        }
