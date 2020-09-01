# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .es_num2word import to_word


class AccountRegisterPayments(models.TransientModel):
    _inherit = "account.register.payments"

    payment_slip_number = fields.Char("Número de comprobante de pago")
    payment_slip_file = fields.Binary("Archivo comprobante de pago", attachment=True)
    secuencial = fields.Integer("Nro. Preimpreso")

    check_city = fields.Char(string="Ciudad")
    check_receiver = fields.Char(
        string="Beneficiario",
        help="Ingrese el nombre de la persona que cobrará el cheque en caso de ser distinta al proveedor o cliente.",
    )
    check_usetradename = fields.Boolean(
        string="Usar nombre comercial",
        help="Seleccione para imprimir el cheque usando el nombre comercial en lugar de la razón social.",
    )

    bank_id = fields.Many2one(
        "res.bank",
        string="Emisor",
        domain="[('credit_card_issuer','=',True)]",
        help="Entidad emisora de la tarjeta de crédito.",
    )

    @api.onchange("amount")
    def _onchange_amount(self):
        self.check_amount_in_words = to_word(self.amount)

    def get_payment_vals(self):
        res = super(AccountRegisterPayments, self).get_payment_vals()
        res.update(
            {
                'payment_slip_number': self.payment_slip_number,
                'payment_slip_file': self.payment_slip_file,
                'check_amount_in_words': self.check_amount_in_words,
                'check_city': self.check_city,
                'check_receiver': self.check_receiver,
                'check_usetradename': self.check_usetradename,
                'secuencial': self.secuencial,
            }
        )
        return res


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _default_city(self):
        return self.env.user.company_id.city or ""

    payment_slip_number = fields.Char("Comprobante Nro.")
    payment_slip_file = fields.Binary("Archivo del comprobante", attachment=True)
    secuencial = fields.Integer("Nro. Preimpreso")
    check_city = fields.Char(string="Ciudad", default=_default_city)
    check_receiver = fields.Char(
        string="Beneficiario",
        help="Ingrese el nombre de la persona que cobrará el cheque en caso de ser distinta al proveedor o cliente.",
    )
    check_usetradename = fields.Boolean(
        string="Usar nombre comercial",
        help="Seleccione para imprimir el cheque usando el nombre comercial en lugar de la razón social.",
    )
    bank_id = fields.Many2one(
        "res.bank",
        string="Emisor",
        domain="[('credit_card_issuer','=',True)]",
        help="Entidad emisora de la tarjeta de crédito.",
    )
    efectivizado = fields.Boolean("Efectivizado")
    contrapartida_id = fields.Many2one(
        "account.account",
        string="Contrapartida",
        domain="[('deprecated','=',False)]",
        help="Contrapartida para el registro del asiento contable. Ejm: Anticipo de proveedores, Anticipo de clientes.",
    )
    prepayment = fields.Boolean("¿es anticipo?")

    # METODOS REDEFINIDOS

    @api.multi
    def cancel(self):
        for rec in self:
            if rec.payment_type == 'transfer':
                return super(AccountPayment, self).cancel()

            aml = rec.move_line_ids
            has_bank_statement = any(aml.filtered(lambda x: x.statement_id))
            if has_bank_statement:
                raise UserError(_("You can't cancel payments on a bank statement."))
            reconciled = any(aml.filtered(lambda x: x.reconciled))
            if reconciled:
                raise UserError(_("You can't cancel reconciled payments."))
            for move in aml.mapped('move_id'):
                move.button_cancel()
                # No eliminamos el asiento para utilizar la misma
                # secuencial a volver a validarlo.
                #move.unlink()
            rec.state = "draft"

    @api.multi
    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _("You can not delete a payment that is already posted")
                )
            # Como el asiento no se elmina al cancelar, debemos eliminarlo
            # en caso de que el pago sea eliminado.
            if rec.move_line_ids:
                rec.move_line_ids.mapped("move_id").unlink()
        return super(AccountPayment, self).unlink()

    """
    def _create_payment_entry(self, amount):
        aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
        invoice_currency = False
        if self.invoice_ids and all([x.currency_id == self.invoice_ids[0].currency_id for x in self.invoice_ids]):
            # if all the invoices selected share the same currency, record the paiement in that currency too
            invoice_currency = self.invoice_ids[0].currency_id
        debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(
            amount, self.currency_id, self.company_id.currency_id, invoice_currency)

        move = self.env['account.move'].create(self._get_move_vals())

        # Write line corresponding to invoice payment
        counterpart_aml_dict = self._get_shared_move_line_vals(
            debit, credit, amount_currency, move.id, False)
        counterpart_aml_dict.update(self._get_counterpart_move_line_vals(self.invoice_ids))
        counterpart_aml_dict.update({'currency_id': currency_id})
        counterpart_aml = aml_obj.create(counterpart_aml_dict)

        # Reconcile with the invoices
        if self.payment_difference_handling == 'reconcile' and self.payment_difference:
            writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
            amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date).compute_amount_fields(
                self.payment_difference, self.currency_id, self.company_id.currency_id, invoice_currency)[2:]
            # the writeoff debit and credit must be computed from the invoice residual in company currency
            # minus the payment amount in company currency, and not from the payment difference in the payment currency
            # to avoid loss of precision during the currency rate computations. See revision 20935462a0cabeb45480ce70114ff2f4e91eaf79 for a detailed example.
            total_residual_company_signed = sum(
                invoice.residual_company_signed for invoice in self.invoice_ids)
            total_payment_company_signed = self.currency_id.with_context(
                date=self.payment_date).compute(self.amount, self.company_id.currency_id)
            if self.invoice_ids[0].type in ['in_invoice', 'out_refund']:
                amount_wo = total_payment_company_signed - total_residual_company_signed
            else:
                amount_wo = total_residual_company_signed - total_payment_company_signed
            debit_wo = amount_wo > 0 and amount_wo or 0.0
            credit_wo = amount_wo < 0 and -amount_wo or 0.0
            writeoff_line['name'] = _('Counterpart')
            writeoff_line['account_id'] = self.writeoff_account_id.id
            writeoff_line['debit'] = debit_wo
            writeoff_line['credit'] = credit_wo
            writeoff_line['amount_currency'] = amount_currency_wo
            writeoff_line['currency_id'] = currency_id
            writeoff_line = aml_obj.create(writeoff_line)
            if counterpart_aml['debit']:
                counterpart_aml['debit'] += credit_wo - debit_wo
            if counterpart_aml['credit']:
                counterpart_aml['credit'] += debit_wo - credit_wo
            counterpart_aml['amount_currency'] -= amount_currency_wo
        self.invoice_ids.register_payment(counterpart_aml)

        # Write counterpart lines
        if not self.currency_id != self.company_id.currency_id:
            amount_currency = 0
        liquidity_aml_dict = self._get_shared_move_line_vals(
            credit, debit, -amount_currency, move.id, False)
        liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
        aml_obj.create(liquidity_aml_dict)

        move.post()
        return move
    """

    @api.one
    @api.depends(
        "payment_method_code",
        "invoice_ids",
        "payment_type",
        "partner_type",
        "partner_id",
        "prepayment",
    )
    def _compute_destination_account_id(self):
        """
        En caso de ser prepago, la contraparte es la marcada por
        el usuario.
        """
        if not self.contrapartida_id:
            return super(AccountPayment, self)._compute_destination_account_id()
        else:
            self.destination_account_id = self.contrapartida_id.id

    @api.multi
    def post(self):
        """
        Super to this function to avoid new name generation.
        """
        for rec in self:
            move = self.env['account.move.line'].search(
                [
                    ('payment_id','=',rec.id),
                    ('move_id.state','=','draft')
                ]
            ).mapped('move_id')
            if not move:
                return super(AccountPayment, rec).post()
            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_(
                    "The payment cannot be processed because the invoice is not open!"
                ))
            # Tomamos el movimiento generado primero.
            move = move[-1]
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            # Volvemos a regenerar las líneas.
            move = rec._create_payment_entry(amount)
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(
                    lambda r: r.account_id == rec.company_id.transfer_account_id
                )
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()
            rec.state = 'posted'

    def _get_move_vals(self, journal=None):
        """ Return dict to create the payment move
        """
        move = self.env['account.move.line'].search(
            [
                ('payment_id', '=', self.id),
                ('move_id.state', '=', 'draft')
            ]
        ).mapped('move_id')
        if not move:
            return super(AccountPayment, self)._get_move_vals(journal=journal)
        journal = journal or self.journal_id
        # Tomamos el movimiento generado primero.
        move = move[-1]
        vals = {
            'name': move.name,
            'date': self.payment_date,
            'ref': self.communication or '',
            'company_id': self.company_id.id,
            'journal_id': journal.id,
        }
        # Eliminamos el asiento anterior para permitir el flujo
        # normal de Odoo, usando create al validar.
        move.unlink()
        return vals

    @api.multi
    @api.onchange("amount")
    def _onchange_amount(self):
        self.check_amount_in_words = to_word(self.amount)

    @api.multi
    @api.onchange("prepayment")
    def _onchange_prepayment(self):
        if not self.prepayment:
            self.contrapartida_id = False
        else:
            domain = {'domain':{'contrapartida_id': [('advance', '=', True)]}}
            return domain

