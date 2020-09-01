#!/usr/bin/env python
# -*- coding: utf-8 -*-
import base64
import sys
import unicodedata
from io import StringIO
from datetime import datetime

from odoo import _, api, fields, models
from odoo.addons.l10n_ec_payment.models.es_num2word import to_word
from odoo.exceptions import UserError

# reload(sys)
# sys.setdefaultencoding("utf-8")


class WizradHrPayslipPayment(models.TransientModel):
    _name = "wizard.hr.payslip.payment"

    payslip_run_id = fields.Many2one("hr.payslip.run", "Payslip run")
    date = fields.Date(string='Date', )
    line_ids = fields.One2many(
        'wizard.hr.payslip.payment.line',
        'wizard_id',
        string='Lines',
    )
    journal_id = fields.Many2one(
        'account.journal',
        domain="[('type','in',('bank', 'cash'))]",
        string='Journal',
    )
    payment_method_id = fields.Many2one(
        "account.payment.method",
        string="Payment Type",
    )

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        if self.journal_id:
            methods = self.journal_id.outbound_payment_method_ids
            methods = methods.filtered(lambda x: x.payment_type == 'outbound')
            return {
                "domain": {"payment_method_id": [('id', 'in', methods.ids)]}
            }
        return {}

    @api.multi
    def button_create_lines(self):
        for slip in self.payslip_run_id.slip_ids:
            due_amount = slip.due_amount
            if round(due_amount, 2) == 0.00:
                continue
            line_obj = self.env['wizard.hr.payslip.payment.line']
            line_obj.create(
                {
                    'wizard_id': self.id,
                    'payslip_id': slip.id,
                    'journal_id': self.journal_id.id,
                    'payment_method_id': self.payment_method_id.id,
                    'amount': due_amount,
                }
            )
        return {
            "name": _("Generate Payments"),
            "view_mode": "form",
            "view_type": "form",
            "res_model": "wizard.hr.payslip.payment",
            "res_id": self.id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    @api.multi
    def button_generate_payments(self):
        payment_obj = self.env["account.payment"]
        for line in self.line_ids:
            if line.amount > line.payslip_id.due_amount:
                raise UserError(
                    _("El valor a pagar {} es mayor que el valor pendiente de pago {} para {}".format(
                        line.amount,
                        line.payslip_id.due_amount,
                        line.payslip_id.employee_id.name
                    ))
                )
            account_move_lines_to_reconcile = self.env["account.move.line"]
            home = line.payslip_id.employee_id.address_home_id
            mml_ids = line.payslip_id.move_id.line_ids.filtered(
                lambda x: x.account_id.internal_type == "payable"
                    and x.partner_id == home
                )

            account = mml_ids.mapped('account_id')
            if len(account) > 1:
                raise UserError(_(
                    "Una sola cuenta del rol debe ser una cuenta 'A pagar', "
                    "y debe ser la cuenta de sueldos por pagar del departamento."
                    "las cuentas: {} están marcadas como cuentas por pagar.".format(
                        ', '.join(account.mapped('code')))
                ))
            account_move_lines_to_reconcile |= mml_ids
            payment_dict = line.get_payment_dict(account=account)
            payment = payment_obj.create(payment_dict)
            payment.post()
            aml_ids = payment.move_line_ids.filtered(
                lambda x: x.account_id.internal_type == "payable"
            )
            account_move_lines_to_reconcile |= aml_ids
            account_move_lines_to_reconcile.reconcile()
            line.payslip_id._compute_pay_amount()
        self.payslip_run_id._get_slip_pay_amount()
        return True


class WizradHrPayslipPaymentLine(models.TransientModel):
    _name = "wizard.hr.payslip.payment.line"

    wizard_id = fields.Many2one(
        'wizard.hr.payslip.payment',
        string='Wizard',
        required=True,
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=True,
    )

    @api.onchange("payslip_id")
    def _onchange_payslip_id(self):
        if not self.payslip_id:
            slips = self.wizard_id.payslip_run_id.slip_ids
            # used_slips = self.wizard_id.line_ids.mapped('payslip_id')
            return {
                "domain": {"payslip_id": [('id', 'in', slips.ids)]}
            }
        else:
            self.amount = self.payslip_id.due_amount

    journal_id = fields.Many2one(
        'account.journal',
        domain="[('type','in',('bank', 'cash'))]",
        string='Journal',
        required=True,
    )
    payment_method_id = fields.Many2one(
        "account.payment.method",
        string="Payment Type",
        required=True,
    )

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        if self.journal_id:
            methods = self.journal_id.outbound_payment_method_ids
            methods = methods.filtered(lambda x: x.payment_type == 'outbound')
            return {
                "domain": {"payment_method_id": [('id', 'in', methods.ids)]}
            }
        return {}

    amount = fields.Float(
        string='Amount',
        required=True,
    )

    @api.multi
    def get_payment_dict(self, account=False):
        slip = self.payslip_id
        payment_dict = {
            "partner_type": "supplier",
            "payment_type": "outbound",
            "partner_id": slip.employee_id.address_home_id.id,
            "journal_id": self.journal_id.id,
            "company_id": slip.company_id.id,
            "payroll_slip_id": slip.id,
            "payroll_slip_run_id": slip.payslip_run_id.id,
            "payment_method_id": self.payment_method_id.id,
            "amount": self.amount,
            "payment_date": self.wizard_id.date,
            "communication": slip.number,
        }
        if account:
            payment_dict.update({
                "contrapartida_id": account.id
            })
        if self.payment_method_id.code == 'check_printing':
            payment_dict.update({
                    "check_amount_in_words": to_word(self.amount),
                })
        return payment_dict

